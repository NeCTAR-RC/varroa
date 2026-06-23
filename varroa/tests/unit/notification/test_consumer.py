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

from varroa.notification import consumer
from varroa.tests.unit import base


class TestConsumerService(base.TestCase):
    def setUp(self):
        super().setUp()
        self.conf = mock.Mock(host='test-host')
        self.service = consumer.ConsumerService(1, self.conf)

    def test_terminate_stops_listener(self):
        listener = mock.Mock()
        self.service.message_listener = listener

        self.service.terminate()

        listener.stop.assert_called_once_with()
        listener.wait.assert_called_once_with()

    def test_terminate_without_listener(self):
        # No listener was ever started; terminate must not raise.
        self.service.terminate()
