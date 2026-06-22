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

from unittest import mock

from varroa.cmd import manage
from varroa import models
from varroa.tests.unit import base


@mock.patch('varroa.cmd.manage.keystone')
@mock.patch('varroa.cmd.manage.clients')
class TestBackfillPorts(base.TestCase):
    def _port(self, **kwargs):
        defaults = dict(
            id='port-1',
            project_id='proj-1',
            device_id='dev-1',
            device_owner='compute:nova',
            created_at='2020-01-01T00:00:00Z',
            network_id='net-1',
            fixed_ips=[{'ip_address': '203.0.113.7'}],
        )
        defaults.update(kwargs)
        return mock.Mock(**defaults)

    def test_backfill_tracks_first_public_ip(
        self, mock_clients, mock_keystone
    ):
        conn = mock_clients.get_openstack.return_value
        conn.list_ports.return_value = [
            self._port(
                fixed_ips=[
                    {'ip_address': '192.168.0.5'},
                    {'ip_address': '203.0.113.7'},
                ]
            )
        ]
        conn.get_network.return_value = mock.Mock(is_router_external=True)

        manage.backfill_ports.callback.__wrapped__()

        ip_usage = models.IPUsage.query.filter_by(port_id='port-1').one()
        self.assertEqual('203.0.113.7', ip_usage.ip)
        self.assertEqual('dev-1', ip_usage.resource_id)
        self.assertEqual('instance', ip_usage.resource_type)

    def test_backfill_skips_internal_network(
        self, mock_clients, mock_keystone
    ):
        conn = mock_clients.get_openstack.return_value
        conn.list_ports.return_value = [self._port()]
        conn.get_network.return_value = mock.Mock(is_router_external=False)

        manage.backfill_ports.callback.__wrapped__()

        self.assertEqual(0, models.IPUsage.query.count())

    def test_backfill_skips_missing_network(self, mock_clients, mock_keystone):
        conn = mock_clients.get_openstack.return_value
        conn.list_ports.return_value = [self._port()]
        conn.get_network.return_value = None

        manage.backfill_ports.callback.__wrapped__()

        self.assertEqual(0, models.IPUsage.query.count())

    def test_backfill_skips_port_with_only_private_ips(
        self, mock_clients, mock_keystone
    ):
        conn = mock_clients.get_openstack.return_value
        conn.list_ports.return_value = [
            self._port(fixed_ips=[{'ip_address': '192.168.0.5'}])
        ]
        conn.get_network.return_value = mock.Mock(is_router_external=True)

        manage.backfill_ports.callback.__wrapped__()

        self.assertEqual(0, models.IPUsage.query.count())
        conn.get_network.assert_not_called()
