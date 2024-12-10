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

from varroa.tests.unit import base


class TestSecurityRiskTypesAPI(base.ApiTestCase):
    def test_security_risk_types_list(self):
        self.create_security_risk_type()
        response = self.client.get("/v1/security-risk-types/")

        self.assert200(response)
        results = response.get_json().get("results")
        self.assertEqual(1, len(results))

    def test_security_risk_type_detail(self):
        risk_type = self.create_security_risk_type()
        response = self.client.get(f"/v1/security-risk-types/{risk_type.id}/")

        self.assert200(response)
        data = response.get_json()
        self.assertEqual(risk_type.id, data['id'])

    def test_security_risk_type_create(self):
        data = {
            "name": "Test Risk Type",
            "description": "This is a test security risk type",
        }
        response = self.client.post("/v1/security-risk-types/", json=data)

        self.assert403(response)


class TestAdminSecurityRiskTypesAPI(base.ApiTestCase):
    ROLES = ['admin']

    def test_security_risk_type_list(self):
        self.create_security_risk_type()
        response = self.client.get("/v1/security-risk-types/")

        self.assert200(response)
        results = response.get_json().get("results")
        self.assertEqual(1, len(results))

    def test_security_risk_type_detail(self):
        risk_type = self.create_security_risk_type()
        response = self.client.get(f"/v1/security-risk-types/{risk_type.id}/")

        self.assert200(response)
        data = response.get_json()
        self.assertEqual(risk_type.id, data['id'])

    def test_security_risk_type_create(self):
        data = {
            "name": "Test Risk Type",
            "description": "This is a test security risk type",
        }
        response = self.client.post("/v1/security-risk-types/", json=data)

        self.assertStatus(response, 201)
        created_risk_type = response.get_json()
        self.assertEqual(data['name'], created_risk_type['name'])
        self.assertEqual(data['description'], created_risk_type['description'])
        self.assertIsNone(created_risk_type['help_url'])
        self.assertIsNone(created_risk_type['display_name'])

    def test_security_risk_type_create_optionals(self):
        data = {
            "name": "test-risk-type",
            "description": "This is a test security risk type",
            "display_name": "Test Risk Type 2",
            "help_url": "http://example.org/security-help",
        }
        response = self.client.post("/v1/security-risk-types/", json=data)

        self.assertStatus(response, 201)
        created_risk_type = response.get_json()
        self.assertEqual(data['name'], created_risk_type['name'])
        self.assertEqual(data['description'], created_risk_type['description'])
        self.assertEqual(data['help_url'], created_risk_type['help_url'])
        self.assertEqual(
            data['display_name'], created_risk_type['display_name']
        )

    def test_security_risk_type_delete(self):
        risk_type = self.create_security_risk_type()
        response = self.client.delete(
            f"/v1/security-risk-types/{risk_type.id}/"
        )

        self.assertStatus(response, 204)

        # Verify the risk type has been deleted
        get_response = self.client.get(
            f"/v1/security-risk-types/{risk_type.id}/"
        )
        self.assert404(get_response)

    def test_security_risk_type_update(self):
        risk_type = self.create_security_risk_type(
            name="Original Name", description="Original Description"
        )
        update_data = {
            "name": "Updated Name",
            "description": "Updated Description",
        }
        response = self.client.patch(
            f"/v1/security-risk-types/{risk_type.id}/", json=update_data
        )

        self.assert200(response)
        updated_risk_type = response.get_json()
        self.assertEqual(update_data['name'], updated_risk_type['name'])
        self.assertEqual(
            update_data['description'], updated_risk_type['description']
        )

        # Verify the changes persist
        get_response = self.client.get(
            f"/v1/security-risk-types/{risk_type.id}/"
        )
        self.assert200(get_response)
        persisted_data = get_response.get_json()
        self.assertEqual(update_data['name'], persisted_data['name'])
        self.assertEqual(
            update_data['description'], persisted_data['description']
        )
