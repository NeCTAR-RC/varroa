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

from varroa.tests.unit import base
from varroa.worker import periodic


@mock.patch('varroa.app.create_app')
class TestPeriodicTaskService(base.TestCase):
    def setUp(self):
        super().setUp()
        self.mock_conf = mock.Mock()
        self.mock_conf.host = 'test-host'
        self.mock_manager = mock.Mock()
        self.service = periodic.PeriodicTaskService(
            1, self.mock_conf, self.mock_manager
        )

    def test_init(self, mock_create_app):
        self.assertEqual(self.service.conf, self.mock_conf)
        self.assertEqual(self.service.server, 'test-host')
        self.assertIsNone(self.service.worker)
        self.assertIsNone(self.service.t)
        self.assertEqual(self.service.endpoints, [])
        self.assertEqual(self.service.manager, self.mock_manager)

    def test_clean_expired_risks(self, mock_create_app):
        self.service.clean_expired_risks()
        self.mock_manager.clean_expired_risks.assert_called_once_with()

    @mock.patch('threading.Thread')
    @mock.patch('futurist.periodics.PeriodicWorker')
    def test_run(self, mock_periodic_worker, mock_thread, mock_create_app):
        mock_worker = mock.Mock()
        mock_periodic_worker.return_value = mock_worker
        mock_thread_instance = mock.Mock()
        mock_thread.return_value = mock_thread_instance

        self.service.run()

        # Verify PeriodicWorker was created with correct callables
        mock_periodic_worker.assert_called_once()
        callables = mock_periodic_worker.call_args[0][0]
        self.assertEqual(len(callables), 1)
        self.assertEqual(callables[0][0], self.service.clean_expired_risks)
        self.assertEqual(callables[0][1], ())
        self.assertEqual(callables[0][2], {})

        # Verify thread was created and started
        mock_thread.assert_called_once_with(
            target=mock_worker.start, daemon=True
        )
        mock_thread_instance.start.assert_called_once()

    def test_terminate(self, mock_create_app):
        mock_worker = mock.Mock()
        mock_thread = mock.Mock()
        self.service.worker = mock_worker
        self.service.t = mock_thread

        self.service.terminate()

        # Verify worker cleanup
        mock_worker.stop.assert_called_once()
        mock_worker.wait.assert_called_once()
        mock_thread.join.assert_called_once()

    def test_terminate_no_worker(self, mock_create_app):
        # Test terminate when worker and thread are None
        self.service.terminate()
        # Should not raise any exceptions
