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

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import timeutils
from sqlalchemy.orm import exc as sa_exc

from varroa import app
from varroa.common import clients
from varroa.common import keystone
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


class Manager:
    def __init__(self):
        self.app = app.create_app(init_config=False)

    @app_context
    def process_security_risk(self, security_risk_id):
        try:
            self._process_security_risk(security_risk_id)
        except Exception:
            # Roll back so the session is clean for the next message and the
            # risk stays NEW rather than being wrongly recorded as processed.
            # reprocess_new_risks retries it.
            LOG.exception(
                "Failed to process security risk %s, will retry",
                security_risk_id,
            )
            db.session.rollback()

    def _process_security_risk(self, security_risk_id):
        LOG.info("Processing security risk %s", security_risk_id)
        security_risk = (
            db.session.query(models.SecurityRisk)
            .filter_by(id=security_risk_id)
            # Lock the row so a concurrent reprocess (e.g. the reconciliation
            # task racing the original RPC cast) cannot process the same risk
            # twice. with_for_update is a no-op on the SQLite used in tests.
            .with_for_update()
            .first()
        )
        if security_risk is None:
            # The risk was deleted between the cast and now; nothing to do.
            LOG.warning(
                "Security risk %s no longer exists, skipping",
                security_risk_id,
            )
            return
        security_risk.status = models.SecurityRisk.PROCESSED

        try:
            ip_usage = (
                db.session.query(models.IPUsage)
                .filter_by(ip=security_risk.ipaddress)
                .filter(
                    db.or_(
                        db.and_(
                            models.IPUsage.start <= security_risk.time,
                            models.IPUsage.end >= security_risk.time,
                        ),
                        db.and_(
                            models.IPUsage.start <= security_risk.time,
                            models.IPUsage.end.is_(None),
                        ),
                    )
                )
                .one_or_none()
            )
        except sa_exc.MultipleResultsFound as e:
            security_risk.status = models.SecurityRisk.ERROR
            db.session.add(security_risk)
            db.session.commit()
            LOG.error("Found multiple records!")
            LOG.exception(e)
            return

        if ip_usage is None:
            ip_usage = self._find_and_create_ip_usage(security_risk)
        else:
            LOG.debug("Found existing IP usage record")

        if ip_usage is not None:
            security_risk.project_id = ip_usage.project_id
            security_risk.resource_id = ip_usage.resource_id
            security_risk.resource_type = ip_usage.resource_type
            LOG.info(
                "Matched %s to resource %s",
                security_risk.ipaddress,
                ip_usage.resource_id,
            )
        dupe_security_risk = (
            db.session.query(models.SecurityRisk)
            .filter_by(resource_id=security_risk.resource_id)
            .filter_by(type_id=security_risk.type_id)
            .filter(models.SecurityRisk.id != security_risk.id)
            .filter(models.SecurityRisk.project_id.isnot(None))
            .filter_by(status=models.SecurityRisk.PROCESSED)
            .first()
        )
        if dupe_security_risk:
            LOG.info(
                "Found duplicate security risk, updating %s",
                dupe_security_risk.id,
            )
            dupe_security_risk.time = security_risk.time
            dupe_security_risk.last_seen = security_risk.time
            dupe_security_risk.expires = security_risk.expires
            db.session.add(dupe_security_risk)
            db.session.delete(security_risk)
        else:
            db.session.add(security_risk)

        db.session.commit()

    def _find_and_create_ip_usage(self, security_risk):
        ipaddress = security_risk.ipaddress
        LOG.debug("Searching for port with ip=%s", ipaddress)

        k_session = keystone.KeystoneSession().get_session()

        openstack = clients.get_openstack(k_session)
        port = None
        ports = openstack.list_ports(
            filters={'fixed_ips': f'ip_address={ipaddress}'}
        )
        if len(ports) < 1:
            LOG.warning("No port found for IP %s", ipaddress)
            return None
        elif len(ports) > 1:
            LOG.warning("Found multiple ports for IP %s", ipaddress)
            return None
        else:
            port = ports[0]

        # get_network returns None when the network is missing. A transient
        # error (neutron/keystone) is deliberately NOT caught here so it
        # propagates and the risk is retried rather than being marked
        # processed with no resource attributed.
        network = openstack.get_network(port.network_id)
        if network is None:
            LOG.error(
                "Couldn't find network %s for port %s",
                port.network_id,
                port.id,
            )
            return None

        if not network.is_router_external:
            LOG.debug("Ignoring port %s on internal network", port.id)
            return None

        port_created = datetime.datetime.strptime(
            port.created_at, '%Y-%m-%dT%H:%M:%SZ'
        )
        if port_created > security_risk.time:
            LOG.debug("Port for %s created after security_risk", ipaddress)
            return None

        ip_usage = (
            db.session.query(models.IPUsage)
            .filter_by(port_id=port.id)
            .one_or_none()
        )
        if ip_usage is not None:
            return ip_usage

        if port.device_owner.startswith('compute:'):
            resource_type = 'instance'
        else:
            LOG.warning(
                "Port device owner %s not supported", port.device_owner
            )
            return

        ip_usage = models.IPUsage(
            ip=ipaddress,
            project_id=port.project_id,
            port_id=port.id,
            resource_id=port.device_id,
            resource_type=resource_type,
            start=port_created,
        )

        db.session.add(ip_usage)
        db.session.commit()
        LOG.debug("Created new IP usage for %s", ipaddress)
        return ip_usage

    @app_context
    def clean_expired_risks(self):
        LOG.info("Cleaning expired risks")
        # All datetimes in the system are stored as naive UTC (the API parses
        # expires as UTC and neutron created_at is UTC), so compare against
        # UTC now rather than the worker host's local wall-clock time.
        now = timeutils.utcnow()
        risks = (
            db.session.query(models.SecurityRisk)
            .filter(models.SecurityRisk.expires < now)
            # Never delete a risk that has not been processed yet. It may be
            # stranded behind a dropped RPC cast; reprocess_new_risks drives
            # those to PROCESSED/ERROR first so a real exposure is not
            # silently discarded before it is ever attributed to a tenant.
            .filter(models.SecurityRisk.status != models.SecurityRisk.NEW)
            .all()
        )
        for risk in risks:
            LOG.info(f"Deleting expired risk {risk}")
            db.session.delete(risk)
        db.session.commit()

    def reprocess_new_risks(self):
        """Re-drive security risks that were never processed.

        The API casts process_security_risk fire-and-forget, so a worker
        outage or a dropped message can leave a risk stranded in NEW forever
        (and clean_expired_risks no longer removes NEW risks). Periodically
        pick up NEW risks that are old enough not to still be in flight and
        reprocess them. process_security_risk is idempotent: it always moves
        the risk to PROCESSED or ERROR.
        """
        LOG.info("Reprocessing stranded new security risks")
        for risk_id in self._stranded_new_risk_ids():
            LOG.info("Reprocessing stranded security risk %s", risk_id)
            self.process_security_risk(risk_id)

    @app_context
    def _stranded_new_risk_ids(self):
        # Leave recently created risks alone; they may still be in flight in
        # the RPC handler. Only reclaim NEW risks older than one processing
        # interval.
        cutoff = timeutils.utcnow() - datetime.timedelta(
            seconds=CONF.worker.periodic_task_interval
        )
        risks = (
            db.session.query(models.SecurityRisk)
            .filter(models.SecurityRisk.status == models.SecurityRisk.NEW)
            .filter(models.SecurityRisk.first_seen < cutoff)
            .all()
        )
        return [risk.id for risk in risks]
