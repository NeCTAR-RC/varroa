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

from freezegun import freeze_time

from varroa import models
from varroa.tests.unit import base


class TestModels(base.TestCase):
    @freeze_time('2021-01-27')
    def test_create_security_risk_defaults(self):
        sr_type = self.create_security_risk_type()
        sr = models.SecurityRisk(
            time=datetime.now(),
            type_id=sr_type.id,
            ipaddress='203.0.113.3',
            expires=datetime.now(),
        )
        self.assertEqual(models.SecurityRisk.NEW, sr.status)
        self.assertIsNone(sr.port)

    def test_security_risk_type_str(self):
        sr_type = self.create_security_risk_type()
        self.assertEqual(sr_type.__str__(), sr_type.name)
        sr_type.display_name = 'test_security_risk_type_str'
        self.assertEqual(sr_type.__str__(), sr_type.display_name)
