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

from varroa.common import rpc
from varroa.tests.unit import base


class TestGetNotifier(base.TestCase):
    def test_builds_publisher_id_from_service_and_host(self):
        with mock.patch.object(rpc, 'NOTIFIER') as mock_notifier:
            rpc.get_notifier(service='varroa', host='host1')

        mock_notifier.prepare.assert_called_once_with(
            publisher_id='varroa.host1'
        )

    def test_uses_explicit_publisher_id(self):
        with mock.patch.object(rpc, 'NOTIFIER') as mock_notifier:
            rpc.get_notifier(
                service='varroa', host='host1', publisher_id='custom-id'
            )

        mock_notifier.prepare.assert_called_once_with(publisher_id='custom-id')
