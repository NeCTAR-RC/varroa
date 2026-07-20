#!/usr/bin/env python
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

import click
from flask.cli import FlaskGroup
from oslo_log import log as logging

from varroa import app
from varroa.common import clients
from varroa.common import keystone
from varroa.common import utils
from varroa.extensions import db
from varroa import models


LOG = logging.getLogger(__name__)


@click.group(cls=FlaskGroup, create_app=app.create_app)
def cli():
    """Management script for the Warre application."""


@cli.command('backfill-ports')
def backfill_ports():
    k_session = keystone.KeystoneSession().get_session()
    openstack = clients.get_openstack(k_session)

    all_ports = openstack.list_ports()

    for port in all_ports:
        ip_usage = (
            db.session.query(models.IPUsage)
            .filter_by(port_id=port.id)
            .one_or_none()
        )
        if ip_usage is None:
            if port.device_owner.startswith("compute:"):
                resource_type = "instance"
            else:
                LOG.warning(
                    "Port %s device owner %s not supported",
                    port.id,
                    port.device_owner,
                )
                continue

            # Track the first public fixed IP rather than blindly
            # fixed_ips[0], matching the notification path.
            ipaddress = None
            for fixed_ip in port.fixed_ips or []:
                candidate = fixed_ip.get("ip_address")
                if candidate and not utils.is_private_ip(candidate):
                    ipaddress = candidate
                    break
            if ipaddress is None:
                LOG.debug("Port %s has no public IP to track", port.id)
                continue

            # Only track ports on external networks, matching the
            # notification and worker paths. get_network returns None when
            # the network is missing.
            network = openstack.get_network(port.network_id)
            if network is None:
                LOG.error(
                    "Couldn't find network %s for port %s",
                    port.network_id,
                    port.id,
                )
                continue
            if not network.is_router_external:
                LOG.debug("Ignoring port %s on internal network", port.id)
                continue

            try:
                port_created = datetime.datetime.strptime(
                    port.created_at, "%Y-%m-%dT%H:%M:%SZ"
                )
            except TypeError:
                LOG.exception("Port %s has an invalid created_at", port.id)
                continue

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
