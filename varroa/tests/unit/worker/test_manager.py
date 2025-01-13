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
from unittest import mock

from freezegun import freeze_time

from varroa import models
from varroa.tests.unit import base
from varroa.worker import manager as worker_manager


@mock.patch('varroa.app.create_app')
class TestManager(base.TestCase):
    @mock.patch('varroa.worker.manager.clients.get_openstack')
    def test_process_security_risk_existing_ip_usage(
        self, mock_get_openstack, mock_create_app
    ):
        # Create a security risk and an existing IP usage
        manager = worker_manager.Manager()
        security_risk = self.create_security_risk()
        ip_usage = self.create_ip_usage()

        manager.process_security_risk(security_risk.id)

        # Check that the security risk was updated correctly
        updated_sr = models.SecurityRisk.query.get(security_risk.id)
        self.assertEqual(updated_sr.status, models.SecurityRisk.PROCESSED)
        self.assertEqual(updated_sr.project_id, ip_usage.project_id)
        self.assertEqual(updated_sr.resource_id, ip_usage.resource_id)
        self.assertEqual(updated_sr.resource_type, ip_usage.resource_type)

    @mock.patch('varroa.worker.manager.clients.get_openstack')
    def test_process_security_risk_new_ip_usage(
        self, mock_get_openstack, mock_create_app
    ):
        # Create a security risk without an existing IP usage
        manager = worker_manager.Manager()
        security_risk = self.create_security_risk()

        # Mock OpenStack client response
        mock_port = mock.Mock(
            id='fake-port-id',
            project_id='fake-project-id',
            device_id='fake-device-id',
            device_owner='compute:nova',
            created_at='2020-02-01T00:00:00Z',
        )
        mock_get_openstack.return_value.list_ports.return_value = [mock_port]

        manager.process_security_risk(security_risk.id)

        # Check that the security risk was updated correctly
        updated_sr = models.SecurityRisk.query.get(security_risk.id)
        self.assertEqual(updated_sr.status, models.SecurityRisk.PROCESSED)
        self.assertEqual(updated_sr.project_id, 'fake-project-id')
        self.assertEqual(updated_sr.resource_id, 'fake-device-id')
        self.assertEqual(updated_sr.resource_type, 'instance')

        # Check that a new IP usage was created
        new_ip_usage = models.IPUsage.query.filter_by(
            ip=security_risk.ipaddress
        ).one()
        self.assertEqual(new_ip_usage.project_id, 'fake-project-id')
        self.assertEqual(new_ip_usage.port_id, 'fake-port-id')
        self.assertEqual(new_ip_usage.resource_id, 'fake-device-id')
        self.assertEqual(new_ip_usage.resource_type, 'instance')

    @mock.patch('varroa.worker.manager.clients.get_openstack')
    def test_find_and_create_ip_usage_success(
        self, mock_get_openstack, mock_create_app
    ):
        manager = worker_manager.Manager()
        security_risk = self.create_security_risk()

        mock_port = mock.Mock(
            id='fake-port-id',
            project_id='fake-project-id',
            device_id='fake-device-id',
            device_owner='compute:nova',
            created_at='2020-01-01T00:00:00Z',
        )
        mock_get_openstack.return_value.list_ports.return_value = [mock_port]

        result = manager._find_and_create_ip_usage(security_risk)

        self.assertIsNotNone(result)
        self.assertEqual(result.ip, security_risk.ipaddress)
        self.assertEqual(result.project_id, 'fake-project-id')
        self.assertEqual(result.port_id, 'fake-port-id')
        self.assertEqual(result.resource_id, 'fake-device-id')
        self.assertEqual(result.resource_type, 'instance')

    @mock.patch('varroa.worker.manager.clients.get_openstack')
    def test_find_and_create_ip_usage_no_ports(
        self, mock_get_openstack, mock_create_app
    ):
        manager = worker_manager.Manager()
        security_risk = self.create_security_risk()

        mock_get_openstack.return_value.list_ports.return_value = []

        result = manager._find_and_create_ip_usage(security_risk)

        self.assertIsNone(result)

    @mock.patch('varroa.worker.manager.clients.get_openstack')
    def test_find_and_create_ip_usage_multiple_ports(
        self, mock_get_openstack, mock_create_app
    ):
        manager = worker_manager.Manager()
        security_risk = self.create_security_risk()

        mock_get_openstack.return_value.list_ports.return_value = [
            mock.Mock(),
            mock.Mock(),
        ]

        result = manager._find_and_create_ip_usage(security_risk)

        self.assertIsNone(result)

    @mock.patch('varroa.worker.manager.clients.get_openstack')
    def test_find_and_create_ip_usage_port_created_after_security_risk(
        self, mock_get_openstack, mock_create_app
    ):
        manager = worker_manager.Manager()
        security_risk = self.create_security_risk(
            time=datetime.datetime(2020, 1, 1)
        )

        mock_port = mock.Mock(
            created_at='2020-02-01T00:00:00Z',
        )
        mock_get_openstack.return_value.list_ports.return_value = [mock_port]

        result = manager._find_and_create_ip_usage(security_risk)

        self.assertIsNone(result)

    @mock.patch('varroa.worker.manager.clients.get_openstack')
    def test_find_and_create_ip_usage_unsupported_device_owner(
        self, mock_get_openstack, mock_create_app
    ):
        manager = worker_manager.Manager()
        security_risk = self.create_security_risk()

        mock_port = mock.Mock(
            id='fake-port-id',
            project_id='fake-project-id',
            device_id='fake-device-id',
            device_owner='unsupported:device',
            created_at='2020-01-01T00:00:00Z',
        )
        mock_get_openstack.return_value.list_ports.return_value = [mock_port]

        result = manager._find_and_create_ip_usage(security_risk)

        self.assertIsNone(result)

    @mock.patch('varroa.worker.manager.clients.get_openstack')
    def test_find_and_create_ip_usage_existing_ip_usage(
        self, mock_get_openstack, mock_create_app
    ):
        manager = worker_manager.Manager()
        security_risk = self.create_security_risk()
        existing_ip_usage = self.create_ip_usage(port_id='existing-port-id')

        mock_port = mock.Mock(
            id='existing-port-id',
            project_id='fake-project-id',
            device_id='fake-device-id',
            device_owner='compute:nova',
            created_at='2020-01-01T00:00:00Z',
        )
        mock_get_openstack.return_value.list_ports.return_value = [mock_port]

        result = manager._find_and_create_ip_usage(security_risk)

        self.assertEqual(result, existing_ip_usage)

    @freeze_time("2024-01-01")
    def test_clean_expired_risks(self, mock_create_app):
        expired_risk = self.create_security_risk(
            expires=datetime.datetime(2020, 1, 1)
        )
        non_expired_risk = self.create_security_risk(
            expires=datetime.datetime(2025, 1, 1)
        )

        manager = worker_manager.Manager()
        manager.clean_expired_risks()

        self.assertIsNone(models.SecurityRisk.query.get(expired_risk.id))
        self.assertIsNotNone(
            models.SecurityRisk.query.get(non_expired_risk.id)
        )
