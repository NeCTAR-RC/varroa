#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import datetime
import functools

import openstack
from oslo_config import cfg
from oslo_log import log as logging
import oslo_messaging as messaging
from sqlalchemy import exc as sa_exc

from varroa import app
from varroa.common import clients
from varroa.common import keystone
from varroa.common import rpc
from varroa.common import utils
from varroa.extensions import db
from varroa import models


CONF = cfg.CONF
LOG = logging.getLogger(__name__)


def app_context(f):
    @functools.wraps(f)
    def decorated(self, *args, **kwargs):
        with self.app.app_context():
            return f(self, *args, **kwargs)

    return decorated


class NotificationEndpoints:
    def __init__(self):
        self.app = app.create_app(init_config=False)
        self.notifier = rpc.get_notifier(service="varroa-notification")
        self._openstack = None

    def _get_openstack(self):
        # Build the keystone session and SDK connection once and reuse them;
        # keystoneauth refreshes the token as needed, so a fresh session per
        # notification only forced a re-authentication each time.
        if self._openstack is None:
            k_session = keystone.KeystoneSession().get_session()
            self._openstack = clients.get_openstack(k_session)
        return self._openstack

    def sample(self, ctxt, publisher_id, event_type, payload, metadata):
        LOG.debug("Processing notification for payload %s", payload)
        try:
            traits = {d[0]: d[2] for d in payload[0]["traits"]}
            event_type = payload[0].get("event_type")
            generated = payload[0].get("generated")
            port_id = traits.get("resource_id")
        except (IndexError, KeyError, TypeError) as e:
            # The payload is not shaped like a port event we understand.
            # Redelivery cannot fix it, so ack it rather than poison the queue.
            LOG.error("Discarding malformed notification: %s", payload)
            LOG.exception(e)
            return messaging.NotificationResult.HANDLED

        try:
            if event_type == "port.delete.end":
                self.handle_end(port_id, generated)
            elif event_type == "port.create.end":
                self.handle_create_update(port_id)
            elif event_type == "port.update.end":
                self.handle_create_update(port_id)
            else:
                LOG.debug("Received unhandled event %s", event_type)
        except Exception as e:
            # A handler failure is most likely transient (database, keystone
            # or neutron). Requeue so the event is redelivered rather than
            # silently dropped, which would corrupt the IP-ownership history
            # that security risk attribution depends on.
            LOG.error("Failed to handle notification, requeuing: %s", payload)
            LOG.exception(e)
            return messaging.NotificationResult.REQUEUE

        return messaging.NotificationResult.HANDLED

    @app_context
    def handle_end(self, port_id, generated):
        LOG.debug("Handle end for %s", port_id)
        try:
            end = datetime.datetime.strptime(generated, "%Y-%m-%dT%H:%M:%S.%f")
        except (ValueError, TypeError):
            # A malformed timestamp will never parse on redelivery, so log and
            # drop it instead of letting sample() requeue a poison message.
            LOG.error(
                "Discarding port.delete.end for %s: unparsable timestamp %s",
                port_id,
                generated,
            )
            return

        ip_usage = (
            db.session.query(models.IPUsage)
            .filter_by(port_id=port_id)
            .one_or_none()
        )
        if ip_usage is not None:
            ip_usage.end = end
            db.session.add(ip_usage)
            db.session.commit()

        # TODO(sorrison) Delete all security risks associated with resource ID

    @app_context
    def handle_create_update(self, port_id):
        LOG.debug("Handle start/update for %s", port_id)
        client = self._get_openstack()
        try:
            port = client.get_port_by_id(port_id)
        except openstack.exceptions.ResourceNotFound:
            LOG.error("Failed to find port with ID %s", port_id)
            return

        if port.device_owner.startswith("compute:"):
            resource_type = "instance"
        else:
            LOG.warning(
                "Port device owner %s not supported", port.device_owner
            )
            return

        # A port can have several fixed IPs (e.g. dual-stack v4/v6). Track the
        # first public one rather than blindly taking fixed_ips[0], which would
        # skip the whole port when a public IP sits behind a private one. The
        # port_id is unique, so only one IP per port can be recorded.
        ipaddress = None
        for fixed_ip in port.fixed_ips or []:
            candidate = fixed_ip.get("ip_address")
            if candidate and not utils.is_private_ip(candidate):
                ipaddress = candidate
                break
        if ipaddress is None:
            LOG.debug("Port %s has no public IP to track", port_id)
            return

        # Only track ports on external networks, matching the worker's
        # fallback path (_find_and_create_ip_usage). Without this the two
        # paths disagree about which ports are tracked. get_network returns
        # None when the network is missing; a transient lookup error
        # propagates so the notification is requeued.
        network = client.get_network(port.network_id)
        if network is None:
            LOG.error(
                "Couldn't find network %s for port %s",
                port.network_id,
                port_id,
            )
            return
        if not network.is_router_external:
            LOG.debug("Ignoring port %s on internal network", port_id)
            return

        port_created = datetime.datetime.strptime(
            port.created_at, "%Y-%m-%dT%H:%M:%SZ"
        )

        # Look for any existing ip_usage records with same IP that haven't ended
        # This would indicate a missed end notification so we should end that one now
        ip_usage_dupes = (
            db.session.query(models.IPUsage)
            .filter_by(ip=ipaddress)
            .filter(models.IPUsage.end.is_(None))
            .filter(models.IPUsage.port_id != port_id)
            .all()
        )

        for iu in ip_usage_dupes:
            LOG.error(
                "Found IP Usage with same IP (%s) and not ended, setting end",
                ipaddress,
            )
            iu.end = port_created - datetime.timedelta(seconds=1)
            db.session.add(iu)
            db.session.commit()

        ip_usage = (
            db.session.query(models.IPUsage)
            .filter_by(port_id=port_id)
            .one_or_none()
        )
        if ip_usage is None:
            ip_usage = models.IPUsage(
                ip=ipaddress,
                project_id=port.project_id,
                port_id=port.id,
                resource_id=port.device_id,
                resource_type=resource_type,
                start=port_created,
            )
            db.session.add(ip_usage)
            try:
                db.session.commit()
                return
            except sa_exc.IntegrityError:
                # A concurrent notification for the same port inserted
                # the record between our lookup and commit. Roll back and
                # fall through to update the existing row instead.
                db.session.rollback()
                LOG.info(
                    "IP usage for port %s created concurrently, updating",
                    port_id,
                )
                ip_usage = (
                    db.session.query(models.IPUsage)
                    .filter_by(port_id=port_id)
                    .one()
                )

        # Refresh all mutable fields from the live port. A create/update event
        # means the port is active, so clear any stale end (e.g. from a missed
        # or spurious delete). If the port's fixed IP changed, update ip too so
        # the ownership record tracks the current address; otherwise a risk
        # against the old IP would be misattributed to this resource and a risk
        # against the new IP would match no record at all.
        # (start is the port's immutable creation time, so it is left as is.)
        ip_usage.ip = ipaddress
        ip_usage.project_id = port.project_id
        ip_usage.resource_id = port.device_id
        ip_usage.resource_type = resource_type
        ip_usage.end = None
        db.session.add(ip_usage)
        db.session.commit()
