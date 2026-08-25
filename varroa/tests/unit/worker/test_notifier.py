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

from oslo_config import cfg

from varroa.tests.unit import base
from varroa.worker import notifier


CONF = cfg.CONF


class TestTaynacNotifier(base.TestCase):
    @mock.patch('varroa.worker.notifier.keystone.KeystoneSession')
    @mock.patch('varroa.worker.notifier.clients.get_taynacclient')
    def test_send(self, mock_get_taynac, mock_session):
        security_risk = self.create_security_risk(
            notify=True, project_id=base.PROJECT_ID
        )
        taynac = mock_get_taynac.return_value

        notifier.TaynacNotifier().send(security_risk)

        taynac.messages.send.assert_called_once()
        kwargs = taynac.messages.send.call_args.kwargs
        self.assertEqual(CONF.worker.notification_subject, kwargs['subject'])
        self.assertEqual(base.PROJECT_ID, kwargs['project_id'])
        self.assertEqual(['security'], kwargs['tags'])
        # The rendered body carries the risk details.
        self.assertIn(security_risk.ipaddress, kwargs['body'])

    @mock.patch('varroa.worker.notifier.keystone.KeystoneSession')
    @mock.patch('varroa.worker.notifier.clients.get_taynacclient')
    def test_send_resource_first(self, mock_get_taynac, mock_session):
        security_risk = self.create_resource_security_risk(notify=True)
        taynac = mock_get_taynac.return_value

        notifier.TaynacNotifier().send(security_risk)

        kwargs = taynac.messages.send.call_args.kwargs
        self.assertEqual(base.PROJECT_ID, kwargs['project_id'])
        self.assertIn(security_risk.resource_id, kwargs['body'])
        self.assertIn(security_risk.resource_type, kwargs['body'])

    @mock.patch('varroa.worker.notifier.keystone.KeystoneSession')
    @mock.patch('varroa.worker.notifier.clients.get_taynacclient')
    def test_client_is_cached(self, mock_get_taynac, mock_session):
        security_risk = self.create_security_risk(
            notify=True, project_id=base.PROJECT_ID
        )

        taynac_notifier = notifier.TaynacNotifier()
        taynac_notifier.send(security_risk)
        taynac_notifier.send(security_risk)

        mock_get_taynac.assert_called_once()


class TestLoggingNotifier(base.TestCase):
    @mock.patch('varroa.worker.notifier.clients.get_taynacclient')
    def test_send_does_not_message(self, mock_get_taynac):
        security_risk = self.create_security_risk(
            notify=True, project_id=base.PROJECT_ID
        )

        notifier.LoggingNotifier().send(security_risk)

        mock_get_taynac.assert_not_called()


class TestGetNotifier(base.TestCase):
    @mock.patch('varroa.worker.notifier.stevedore_driver.DriverManager')
    def test_get_notifier(self, mock_manager):
        result = notifier.get_notifier()

        mock_manager.assert_called_once_with(
            namespace='varroa.notifier',
            name=CONF.worker.notifier,
            invoke_on_load=True,
        )
        self.assertEqual(mock_manager.return_value.driver, result)
