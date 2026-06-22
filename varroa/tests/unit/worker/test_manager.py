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
from oslo_utils import timeutils

from varroa.extensions import db
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
    def test_process_security_risk_dupe_risk(
        self, mock_get_openstack, mock_create_app
    ):
        # Create a security risk and an existing IP usage
        manager = worker_manager.Manager()
        security_risk = self.create_security_risk()
        ip_usage = self.create_ip_usage()

        # Create an existing risk with same resource and type
        esr = self.create_security_risk(
            time=datetime.datetime(2019, 1, 1),
            expires=datetime.datetime(2019, 2, 1),
        )
        esr.resource_id = ip_usage.resource_id
        esr.project_id = ip_usage.project_id
        esr.type_id = security_risk.type_id
        esr.status = models.SecurityRisk.PROCESSED
        db.session.add(esr)
        db.session.commit()

        manager.process_security_risk(security_risk.id)

        # Check that the existing risk was updated
        updated_esr = models.SecurityRisk.query.get(esr.id)
        self.assertEqual(updated_esr.expires, security_risk.expires)
        self.assertEqual(updated_esr.time, security_risk.time)
        self.assertEqual(updated_esr.last_seen, security_risk.last_seen)
        self.assertEqual(updated_esr.first_seen, esr.first_seen)

        # Check that the security risk was deleted
        self.assertIsNone(models.SecurityRisk.query.get(security_risk.id))

    @mock.patch('varroa.worker.manager.clients.get_openstack')
    def test_negative_process_security_risk_dupe_risk_null_project(
        self, mock_get_openstack, mock_create_app
    ):
        # Create a security risk and an existing IP usage
        manager = worker_manager.Manager()
        security_risk = self.create_security_risk()
        # ip_usage = self.create_ip_usage()

        # Create an existing risk with same resource and type
        esr = self.create_security_risk()
        esr.status = models.SecurityRisk.PROCESSED
        esr.type = security_risk.type
        db.session.add(esr)
        db.session.commit()

        manager.process_security_risk(security_risk.id)

        # Check that the security risk wasn't deleted
        self.assertIsNotNone(models.SecurityRisk.query.get(security_risk.id))

    @mock.patch('varroa.worker.manager.clients.get_openstack')
    def test_process_security_risk_transient_error_leaves_new(
        self, mock_get_openstack, mock_create_app
    ):
        # A transient neutron failure while resolving the port/network must
        # not mark the risk PROCESSED; it is rolled back and left NEW so the
        # reconciliation task retries it.
        manager = worker_manager.Manager()
        security_risk = self.create_security_risk()
        mock_port = mock.Mock(
            id='fake-port-id',
            project_id='fake-project-id',
            device_id='fake-device-id',
            device_owner='compute:nova',
            created_at='2020-01-01T00:00:00Z',
            network_id='fake-network-id',
        )
        conn = mock_get_openstack.return_value
        conn.list_ports.return_value = [mock_port]
        conn.get_network.side_effect = Exception("neutron unavailable")

        manager.process_security_risk(security_risk.id)

        updated_sr = models.SecurityRisk.query.get(security_risk.id)
        self.assertEqual(models.SecurityRisk.NEW, updated_sr.status)
        self.assertIsNone(updated_sr.project_id)
        self.assertEqual(0, models.IPUsage.query.count())

    @mock.patch('varroa.worker.manager.clients.get_openstack')
    def test_process_security_risk_missing(
        self, mock_get_openstack, mock_create_app
    ):
        # The risk was deleted before the worker got to it; must not crash.
        manager = worker_manager.Manager()
        manager.process_security_risk('does-not-exist')
        mock_get_openstack.assert_not_called()

    @mock.patch('varroa.worker.manager.clients.get_openstack')
    def test_process_security_risk_multiple_ip_usage(
        self, mock_get_openstack, mock_create_app
    ):
        # Two IP usage records match the same IP and time window
        manager = worker_manager.Manager()
        security_risk = self.create_security_risk()
        self.create_ip_usage(port_id='port-1')
        self.create_ip_usage(port_id='port-2')

        manager.process_security_risk(security_risk.id)

        # The risk is flagged ERROR and left unmatched
        updated_sr = models.SecurityRisk.query.get(security_risk.id)
        self.assertEqual(updated_sr.status, models.SecurityRisk.ERROR)
        self.assertIsNone(updated_sr.project_id)
        self.assertIsNone(updated_sr.resource_id)

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
        # Only processed risks are eligible for cleanup.
        expired_risk.status = models.SecurityRisk.PROCESSED
        non_expired_risk.status = models.SecurityRisk.PROCESSED
        db.session.add_all([expired_risk, non_expired_risk])
        db.session.commit()

        manager = worker_manager.Manager()
        manager.clean_expired_risks()

        self.assertIsNone(models.SecurityRisk.query.get(expired_risk.id))
        self.assertIsNotNone(
            models.SecurityRisk.query.get(non_expired_risk.id)
        )

    @freeze_time("2024-01-01")
    def test_clean_expired_risks_keeps_unprocessed(self, mock_create_app):
        # A NEW risk that has expired must not be deleted; it has never been
        # attributed to a tenant and should be reprocessed instead.
        expired_new_risk = self.create_security_risk(
            expires=datetime.datetime(2020, 1, 1)
        )
        self.assertEqual(expired_new_risk.status, models.SecurityRisk.NEW)

        manager = worker_manager.Manager()
        manager.clean_expired_risks()

        self.assertIsNotNone(
            models.SecurityRisk.query.get(expired_new_risk.id)
        )

    @mock.patch('varroa.worker.manager.clients.get_openstack')
    def test_reprocess_new_risks(self, mock_get_openstack, mock_create_app):
        # A risk left in NEW (e.g. the worker was down when the API cast the
        # RPC) is picked up and matched against IP usage on reprocessing.
        manager = worker_manager.Manager()
        security_risk = self.create_security_risk()
        ip_usage = self.create_ip_usage()
        self.assertEqual(security_risk.status, models.SecurityRisk.NEW)

        manager.reprocess_new_risks()

        updated_sr = models.SecurityRisk.query.get(security_risk.id)
        self.assertEqual(updated_sr.status, models.SecurityRisk.PROCESSED)
        self.assertEqual(updated_sr.project_id, ip_usage.project_id)
        self.assertEqual(updated_sr.resource_id, ip_usage.resource_id)

    @mock.patch('varroa.worker.manager.clients.get_openstack')
    def test_reprocess_new_risks_skips_recent(
        self, mock_get_openstack, mock_create_app
    ):
        # A freshly created NEW risk may still be in flight in the RPC
        # handler, so it is left alone by the reconciliation task.
        manager = worker_manager.Manager()
        now = timeutils.utcnow()
        recent_risk = self.create_security_risk(
            time=now, expires=now + datetime.timedelta(days=1)
        )
        self.create_ip_usage()

        manager.reprocess_new_risks()

        updated_sr = models.SecurityRisk.query.get(recent_risk.id)
        self.assertEqual(updated_sr.status, models.SecurityRisk.NEW)

    @mock.patch('varroa.worker.manager.clients.get_openstack')
    def test_find_and_create_ip_usage_non_router_external(
        self, mock_get_openstack, mock_create_app
    ):
        manager = worker_manager.Manager()
        security_risk = self.create_security_risk()

        mock_port = mock.Mock(
            id='non-router-external-port-id',
            project_id='fake-project-id',
            device_id='fake-device-id',
            device_owner='compute:nova',
            created_at='2020-01-01T00:00:00Z',
            network_id='non-router-external-network-id',
        )
        mock_get_openstack.return_value.list_ports.return_value = [mock_port]

        # Simulate the network not being router_external
        mock_get_openstack.return_value.get_network.return_value = mock.Mock(
            is_router_external=False
        )

        result = manager._find_and_create_ip_usage(security_risk)

        self.assertIsNone(result)
