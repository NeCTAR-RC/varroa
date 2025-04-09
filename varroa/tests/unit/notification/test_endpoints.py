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

from datetime import datetime
from unittest import mock

from oslo_utils import uuidutils

from varroa.extensions import db
from varroa import models
from varroa.notification import endpoints
from varroa.tests.unit import base


@mock.patch("varroa.app.create_app")
class TestEndpoints(base.TestCase):
    def _get_payload(self, event, resource_id):
        return [
            {
                "event_type": event,
                "traits": [
                    ["resource_id", 1, resource_id],
                    ["user_id", 1, "615e48919bb94abba759e35c69cee01a"],
                    ["tenant_id", 1, "094ae1e2c08f4eddb444a9d9db71ab40"],
                    [
                        "request_id",
                        1,
                        "req-930eebd7-283f-4a72-9a7e-0cc41720e30c",
                    ],
                    ["project_id", 1, "094ae1e2c08f4eddb444a9d9db71ab40"],
                ],
                "message_signature": "1bf6be8b0a16a4040c4d3451028052a417e4a365b",  # noqa
                "raw": {},
                "generated": "2021-04-23T05:09:58.392627",
                "message_id": "9e1a8bbd-25d6-4db9-81eb-c142a8def002",
            }
        ]

    def test_port_delete(self, mock_app):
        ip_usage = self.create_ip_usage()
        self.assertIsNone(ip_usage.end)
        ep = endpoints.NotificationEndpoints()
        payload = self._get_payload("port.delete.end", base.PORT_ID)
        ep.sample(self.context, "pub-id", "event", payload, {})
        ip_usage = db.session.query(models.IPUsage).get(ip_usage.id)
        self.assertEqual(datetime(2021, 4, 23, 5, 9, 58, 392627), ip_usage.end)

    @mock.patch("varroa.notification.endpoints.clients")
    def test_port_create(self, mock_clients, mock_app):
        port_id = uuidutils.generate_uuid()
        client = mock_clients.get_openstack.return_value
        port = mock.Mock(
            device_owner="compute:cc1",
            fixed_ips=[{"ip_address": "203.0.113.2"}],
            created_at="2024-2-1T12:12:12Z",
            id=port_id,
            project_id=base.PROJECT_ID,
            device_id=base.RESOURCE_ID,
        )
        client.get_port_by_id.return_value = port
        ep = endpoints.NotificationEndpoints()
        payload = self._get_payload("port.create.end", port_id)
        ep.sample(self.context, "pub-id", "event", payload, {})

        mock_clients.get_openstack.assert_called_once()
        client.get_port_by_id.assert_called_once_with(port_id)
        self.assertEqual(1, db.session.query(models.IPUsage).count())
        ip_usage = (
            db.session.query(models.IPUsage).filter_by(ip="203.0.113.2").one()
        )
        self.assertEqual(base.RESOURCE_ID, ip_usage.resource_id)
        self.assertEqual(base.PROJECT_ID, ip_usage.project_id)
        self.assertEqual("instance", ip_usage.resource_type)
        self.assertEqual(datetime(2024, 2, 1, 12, 12, 12), ip_usage.start)
        self.assertEqual(port_id, ip_usage.port_id)
        self.assertIsNone(ip_usage.end)

    @mock.patch("varroa.notification.endpoints.clients")
    def test_port_create_duplicate_active_ip(self, mock_clients, mock_app):
        ip_usage_no_end = self.create_ip_usage()
        self.assertIsNone(ip_usage_no_end.end)
        port_id = uuidutils.generate_uuid()
        client = mock_clients.get_openstack.return_value
        port = mock.Mock(
            device_owner="compute:cc1",
            fixed_ips=[{"ip_address": "203.0.113.1"}],
            created_at="2024-2-1T12:12:12Z",
            id=port_id,
            project_id=base.PROJECT_ID,
            device_id=base.RESOURCE_ID,
        )
        client.get_port_by_id.return_value = port
        ep = endpoints.NotificationEndpoints()
        payload = self._get_payload("port.create.end", port_id)
        ep.sample(self.context, "pub-id", "event", payload, {})

        mock_clients.get_openstack.assert_called_once()
        client.get_port_by_id.assert_called_once_with(port_id)
        ip_usages = db.session.query(models.IPUsage).filter(
            models.IPUsage.end.is_(None)
        )
        self.assertEqual(1, ip_usages.count())
        ip_usage = ip_usages.one()
        self.assertEqual(base.RESOURCE_ID, ip_usage.resource_id)
        self.assertEqual(base.PROJECT_ID, ip_usage.project_id)
        self.assertEqual("instance", ip_usage.resource_type)
        self.assertEqual(datetime(2024, 2, 1, 12, 12, 12), ip_usage.start)
        self.assertEqual(port_id, ip_usage.port_id)
        self.assertIsNone(ip_usage.end)

        ip_usage_no_end = db.session.query(models.IPUsage).get(
            ip_usage_no_end.id
        )
        self.assertEqual(datetime(2024, 2, 1, 12, 12, 11), ip_usage_no_end.end)

    @mock.patch("varroa.notification.endpoints.clients")
    def test_port_create_unsupported_device_id(self, mock_clients, mock_app):
        client = mock_clients.get_openstack.return_value
        port = mock.Mock(device_owner="floatingip:")
        client.get_port_by_id.return_value = port
        ep = endpoints.NotificationEndpoints()
        port_id = uuidutils.generate_uuid()
        payload = self._get_payload("port.create.end", port_id)
        ep.sample(self.context, "pub-id", "event", payload, {})
        self.assertEqual(0, db.session.query(models.IPUsage).count())

    @mock.patch("varroa.notification.endpoints.clients")
    def test_port_create_private_ip(self, mock_clients, mock_app):
        client = mock_clients.get_openstack.return_value
        port = mock.Mock(
            device_owner="compute:cc1",
            fixed_ips=[{"ip_address": "192.168.1.1"}],
        )
        client.get_port_by_id.return_value = port
        ep = endpoints.NotificationEndpoints()
        port_id = uuidutils.generate_uuid()
        payload = self._get_payload("port.create.end", port_id)
        ep.sample(self.context, "pub-id", "event", payload, {})
        self.assertEqual(0, db.session.query(models.IPUsage).count())

    @mock.patch("varroa.notification.endpoints.clients")
    def test_port_update(self, mock_clients, mock_app):
        ip_usage = self.create_ip_usage(resource_id=None, resource_type=None)
        self.assertEqual(1, db.session.query(models.IPUsage).count())
        client = mock_clients.get_openstack.return_value
        port = mock.Mock(
            device_owner="compute:cc1",
            fixed_ips=[{"ip_address": "203.0.113.1"}],
            created_at="2024-2-1T12:12:12Z",
            id=base.PORT_ID,
            project_id=base.PROJECT_ID,
            device_id=base.RESOURCE_ID,
        )
        client.get_port_by_id.return_value = port
        ep = endpoints.NotificationEndpoints()
        payload = self._get_payload("port.update.end", base.PORT_ID)
        ep.sample(self.context, "pub-id", "event", payload, {})

        self.assertEqual(1, db.session.query(models.IPUsage).count())
        ip_usage = (
            db.session.query(models.IPUsage).filter_by(ip="203.0.113.1").one()
        )
        self.assertEqual(base.RESOURCE_ID, ip_usage.resource_id)
        self.assertEqual(base.PROJECT_ID, ip_usage.project_id)
        self.assertEqual("instance", ip_usage.resource_type)
        self.assertEqual(base.START, ip_usage.start)
        self.assertEqual(base.PORT_ID, ip_usage.port_id)
        self.assertIsNone(ip_usage.end)
