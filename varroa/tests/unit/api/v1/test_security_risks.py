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

from varroa import models
from varroa.tests.unit import base


class TestSecurityRisksAPI(base.ApiTestCase):
    ROLES = ['reader']

    def test_security_risks_list(self):
        self.create_security_risk(project_id=base.PROJECT_ID)
        response = self.client.get("/v1/security-risks/")

        self.assert200(response)
        results = response.get_json().get("results")
        self.assertEqual(1, len(results))

    def test_security_risks_list_all(self):
        self.create_security_risk()
        response = self.client.get("/v1/security-risks/?all_projects=true")

        self.assert200(response)
        results = response.get_json().get("results")
        self.assertEqual(0, len(results))

    def test_security_risk_detail(self):
        risk = self.create_security_risk()
        response = self.client.get(f"/v1/security-risks/{risk.id}/")

        self.assert404(response)

    def test_security_risk_detail_owner(self):
        risk = self.create_security_risk(project_id=base.PROJECT_ID)
        response = self.client.get(f"/v1/security-risks/{risk.id}/")

        self.assert200(response)
        data = response.get_json()
        self.assertEqual(risk.id, data['id'])

    def test_security_risk_create(self):
        sr_type = self.create_security_risk_type()
        data = {
            "ipaddress": "203.0.113.4",
            "time": "2024-02-29T12:00:00+00:00",
            "type_id": sr_type.id,
            'expires': '2024-03-01T12:00:00+00:00',
        }
        response = self.client.post("/v1/security-risks/", json=data)

        self.assert403(response)


class TestAdminSecurityRisksAPI(base.ApiTestCase):
    ROLES = ['admin']

    def test_security_risks_list(self):
        self.create_security_risk()
        response = self.client.get("/v1/security-risks/?all_projects=true")

        self.assert200(response)
        results = response.get_json().get("results")
        self.assertEqual(1, len(results))

    def test_security_risks_list_all_projects_false(self):
        # all_projects=false must not widen the query (it previously coerced
        # to True). The risk belongs to no project, so a scoped admin query
        # returns nothing.
        self.create_security_risk()
        response = self.client.get("/v1/security-risks/?all_projects=false")

        self.assert200(response)
        results = response.get_json().get("results")
        self.assertEqual(0, len(results))

    def test_security_risk_detail(self):
        risk = self.create_security_risk()
        response = self.client.get(f"/v1/security-risks/{risk.id}/")

        self.assert200(response)
        data = response.get_json()
        self.assertEqual(risk.id, data['id'])

    def test_security_risk_create(self):
        sr_type = self.create_security_risk_type()
        data = {
            "ipaddress": "203.0.113.4",
            "time": "2024-02-29T12:00:00+00:00",
            "type_id": sr_type.id,
            'expires': '2024-03-01T12:00:00+00:00',
        }
        response = self.client.post("/v1/security-risks/", json=data)

        self.assertStatus(response, 201)
        created_risk = response.get_json()
        self.assertEqual(data['ipaddress'], created_risk['ipaddress'])
        self.assertEqual(data['time'], created_risk['time'])
        self.assertEqual(sr_type.id, created_risk['type']['id'])
        self.assertEqual(data['expires'], created_risk['expires'])
        self.assertEqual(models.SecurityRisk.NEW, created_risk['status'])

    def test_security_risk_create_with_unknown_type(self):
        unknown_type_id = '999'  # Assuming this ID doesn't exist
        data = {
            "ipaddress": "203.0.113.5",
            "time": "2024-03-01T12:00:00+00:00",
            "type_id": unknown_type_id,
            'expires': '2024-03-02T12:00:00+00:00',
        }
        response = self.client.post("/v1/security-risks/", json=data)

        self.assert404(response)
        error_data = response.get_json()
        self.assertIn('Type does not exist', error_data['error_message'])

    def test_security_risk_create_with_private_ip(self):
        sr_type = self.create_security_risk_type()
        data = {
            "ipaddress": "192.168.1.100",  # Private IP address
            "time": "2024-03-01T12:00:00+00:00",
            "type_id": sr_type.id,
            'expires': '2024-03-02T12:00:00+00:00',
        }
        response = self.client.post("/v1/security-risks/", json=data)

        self.assert400(response)
        error_data = response.get_json()
        self.assertIn(
            'Private IP addresses are not allowed', error_data['error_message']
        )

    def test_security_risk_delete(self):
        risk = self.create_security_risk()
        response = self.client.delete(f"/v1/security-risks/{risk.id}/")

        self.assertStatus(response, 204)

        # Verify the risk is deleted
        deleted_risk = models.SecurityRisk.query.get(risk.id)
        self.assertIsNone(deleted_risk)
