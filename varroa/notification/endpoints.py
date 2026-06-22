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
        self.notifier = rpc.get_notifier()

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
        k_session = keystone.KeystoneSession().get_session()
        client = clients.get_openstack(k_session)
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

        try:
            ipaddress = port.fixed_ips[0].get("ip_address")
        except Exception:
            LOG.error("Port %s has no ipaddress", port.id)
            return

        if utils.is_private_ip(ipaddress):
            LOG.debug("Skipping private IP %s", ipaddress)
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

        ip_usage.resource_id = port.device_id
        ip_usage.resource_type = resource_type
        db.session.add(ip_usage)
        db.session.commit()
