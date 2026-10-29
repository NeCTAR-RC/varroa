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
from urllib import parse

from varroa.api.v1.resources import base as resources_base
from varroa.tests.unit import base


class TestPagination(base.ApiTestCase):
    ROLES = ['admin']
    SYSTEM_SCOPE = True

    def _create_risks(self):
        ids = set()
        for i in range(2):
            ids.add(
                self.create_security_risk(
                    ipaddress=f'203.0.113.{i + 1}', project_id=base.PROJECT_ID
                ).id
            )
        self.create_security_risk(
            ipaddress='203.0.113.10', project_id=base.PROJECT_ID_2
        )
        return ids

    def _follow(self, url):
        parsed = parse.urlsplit(url)
        return self.client.get(f"{parsed.path}?{parsed.query}")

    def test_next_preserves_filters(self):
        ids = self._create_risks()
        response = self.client.get(
            f"/v1/security-risks/?limit=1&project_id={base.PROJECT_ID}"
        )

        self.assert200(response)
        data = response.get_json()
        self.assertEqual(1, len(data['results']))
        self.assertEqual(2, data['total'])

        query = parse.parse_qs(parse.urlsplit(data['next']).query)
        self.assertEqual(
            {'limit': ['1'], 'project_id': [base.PROJECT_ID], 'page': ['2']},
            query,
        )

        response2 = self._follow(data['next'])
        self.assert200(response2)
        data2 = response2.get_json()
        self.assertEqual(1, len(data2['results']))
        self.assertEqual(2, data2['total'])
        self.assertNotIn('next', data2)
        self.assertEqual(
            ids, {data['results'][0]['id'], data2['results'][0]['id']}
        )
        for result in data['results'] + data2['results']:
            self.assertEqual(base.PROJECT_ID, result['project_id'])

    def test_next_preserves_multi_valued_args(self):
        self._create_risks()
        response = self.client.get("/v1/security-risks/?limit=1&foo=a&foo=b")

        self.assert200(response)
        query = parse.parse_qs(
            parse.urlsplit(response.get_json()['next']).query
        )
        self.assertEqual(['a', 'b'], query['foo'])
        self.assertEqual(['2'], query['page'])

    def test_no_next_on_single_page(self):
        self._create_risks()
        response = self.client.get("/v1/security-risks/")

        self.assert200(response)
        data = response.get_json()
        self.assertEqual(3, len(data['results']))
        self.assertEqual(3, data['total'])
        self.assertNotIn('next', data)

    def test_limit_clamped_to_api_limit(self):
        self._create_risks()
        with mock.patch.object(resources_base, 'API_LIMIT', 2):
            response = self.client.get("/v1/security-risks/?limit=100")

        self.assert200(response)
        data = response.get_json()
        self.assertEqual(2, len(data['results']))
        self.assertEqual(3, data['total'])
        self.assertIn('next', data)

    def test_invalid_values_return_400(self):
        for qs in ('limit=0', 'limit=-1', 'page=0', 'page=-1', 'page=abc'):
            with self.subTest(qs=qs):
                response = self.client.get(f"/v1/security-risks/?{qs}")
                self.assert400(response)
                self.assertIn('message', response.get_json())
