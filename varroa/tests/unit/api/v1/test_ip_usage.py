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


class TestIPUsageAPI(base.ApiTestCase):
    def test_ip_usage_list(self):
        self.create_ip_usage()
        response = self.client.get("/v1/ip-usage/")

        self.assert200(response)
        results = response.get_json().get("results")
        self.assertEqual(1, len(results))


class TestSystemAdminIPUsageAPI(base.ApiTestCase):
    ROLES = ["admin"]
    SYSTEM_SCOPE = True

    def test_ip_usage_list(self):
        # A system token has no project of its own, so listing spans all
        # projects without needing all_projects.
        self.create_ip_usage(ip="203.0.113.1", project_id=base.PROJECT_ID)
        self.create_ip_usage(
            ip="203.0.113.2",
            project_id=base.PROJECT_ID_2,
            port_id=base.PORT_ID_2,
        )
        response = self.client.get("/v1/ip-usage/")

        self.assert200(response)
        results = response.get_json().get("results")
        self.assertEqual(2, len(results))

    def test_ip_usage_list_project_filter(self):
        self.create_ip_usage(ip="203.0.113.1", project_id=base.PROJECT_ID)
        self.create_ip_usage(
            ip="203.0.113.2",
            project_id=base.PROJECT_ID_2,
            port_id=base.PORT_ID_2,
        )
        response = self.client.get(
            f"/v1/ip-usage/?project_id={base.PROJECT_ID_2}"
        )

        self.assert200(response)
        results = response.get_json().get("results")
        self.assertEqual(1, len(results))
        self.assertEqual(base.PROJECT_ID_2, results[0]["project_id"])


class TestSystemReaderIPUsageAPI(base.ApiTestCase):
    ROLES = ["reader"]
    SYSTEM_SCOPE = True

    def test_ip_usage_list(self):
        self.create_ip_usage(ip="203.0.113.1", project_id=base.PROJECT_ID)
        self.create_ip_usage(
            ip="203.0.113.2",
            project_id=base.PROJECT_ID_2,
            port_id=base.PORT_ID_2,
        )
        response = self.client.get("/v1/ip-usage/")

        self.assert200(response)
        results = response.get_json().get("results")
        self.assertEqual(2, len(results))


class TestSystemMemberIPUsageAPI(base.ApiTestCase):
    ROLES = ["member"]
    SYSTEM_SCOPE = True

    def test_ip_usage_list_forbidden(self):
        # A system token without reader or admin must not see any
        # project's data. Regression: this used to hit the unfiltered
        # project_id=None query path.
        self.create_ip_usage()
        response = self.client.get("/v1/ip-usage/")

        self.assert403(response)
