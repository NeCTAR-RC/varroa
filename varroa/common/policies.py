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

from oslo_policy import policy


READER_OR_OWNER = "reader_or_owner"

base_rules = [
    policy.RuleDefault(
        name="admin_required", check_str="role:admin or is_admin:1"
    ),
    policy.RuleDefault(name="security_admin", check_str="rule:admin_required"),
    policy.RuleDefault(name="owner", check_str="project_id:%(project_id)s"),
    policy.RuleDefault(
        name=READER_OR_OWNER,
        check_str="rule:security_admin or (role:reader and rule:owner)",
    ),
]

IP_USAGE_PREFIX = "varroa:ip_usage:%s"

ip_usage_rules = [
    policy.DocumentedRuleDefault(
        name=IP_USAGE_PREFIX % "list",
        check_str="",
        scope_types=["project"],
        description="List ip usage.",
        operations=[
            {"path": "/v1/ip-usage/", "method": "GET"},
            {"path": "/v1/ip-usage/", "method": "HEAD"},
        ],
    ),
    policy.DocumentedRuleDefault(
        name=IP_USAGE_PREFIX % "list:all",
        check_str="rule:security_admin",
        scope_types=["project"],
        description="List all ip usage.",
        operations=[{"path": "/v1/ip-usage/", "method": "GET"}],
    ),
]

SECURITY_RISK_TYPE_PREFIX = "varroa:security_risk_type:%s"

security_risk_type_rules = [
    policy.DocumentedRuleDefault(
        name=SECURITY_RISK_TYPE_PREFIX % 'get',
        check_str='',
        scope_types=['project'],
        description='Show security risk type details.',
        operations=[
            {
                'path': '/v1/security-risk-types/{security_risk_type_id}/',
                'method': 'GET',
            },
            {
                'path': '/v1/security-risk-types/{security_risk_type_id}/',
                'method': 'HEAD',
            },
        ],
    ),
    policy.DocumentedRuleDefault(
        name=SECURITY_RISK_TYPE_PREFIX % 'list',
        check_str='',
        scope_types=['project'],
        description='List security risk types.',
        operations=[
            {'path': '/v1/security-risk-types/', 'method': 'GET'},
            {'path': '/v1/security-risk-types/', 'method': 'HEAD'},
        ],
    ),
    policy.DocumentedRuleDefault(
        name=SECURITY_RISK_TYPE_PREFIX % 'create',
        check_str='rule:security_admin',
        scope_types=['project'],
        description='Create security risk type.',
        operations=[{'path': '/v1/security-risk-types/', 'method': 'POST'}],
    ),
    policy.DocumentedRuleDefault(
        name=SECURITY_RISK_TYPE_PREFIX % 'update',
        check_str='rule:security_admin',
        scope_types=['project'],
        description='Update a security risk type',
        operations=[
            {
                'path': '/v1/security-risk-types/{security_risk_type_id}/',
                'method': 'PATCH',
            }
        ],
    ),
    policy.DocumentedRuleDefault(
        name=SECURITY_RISK_TYPE_PREFIX % 'delete',
        check_str='rule:security_admin',
        scope_types=['project'],
        description='Delete security risk type.',
        operations=[
            {
                'path': '/v1/security-risk-types/{security_risk_type_id}/',
                'method': 'DELETE',
            }
        ],
    ),
]

SECURITY_RISK_PREFIX = "varroa:security_risk:%s"

security_risk_rules = [
    policy.DocumentedRuleDefault(
        name=SECURITY_RISK_PREFIX % 'get',
        check_str=f'rule:{READER_OR_OWNER}',
        scope_types=['project'],
        description='Show security risk details.',
        operations=[
            {
                'path': '/v1/security-risks/{security_risk_id}/',
                'method': 'GET',
            },
            {
                'path': '/v1/security-risks/{security_risk_id}/',
                'method': 'HEAD',
            },
        ],
    ),
    policy.DocumentedRuleDefault(
        name=SECURITY_RISK_PREFIX % 'list',
        check_str='',
        scope_types=['project'],
        description='List security risks.',
        operations=[
            {'path': '/v1/security-risks/', 'method': 'GET'},
            {'path': '/v1/security-risks/', 'method': 'HEAD'},
        ],
    ),
    policy.DocumentedRuleDefault(
        name=SECURITY_RISK_PREFIX % 'list:all',
        check_str='rule:security_admin',
        scope_types=['project'],
        description='List all security risks.',
        operations=[{'path': '/v1/security-risks/', 'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name=SECURITY_RISK_PREFIX % 'delete',
        check_str='rule:security_admin',
        scope_types=['project'],
        description='Delete security risk.',
        operations=[
            {
                'path': '/v1/security-risks/{security_risk_id}/',
                'method': 'DELETE',
            }
        ],
    ),
    policy.DocumentedRuleDefault(
        name=SECURITY_RISK_PREFIX % 'create',
        check_str='rule:security_admin',
        scope_types=['project'],
        description='Create security risk.',
        operations=[{'path': '/v1/security-risks/', 'method': 'POST'}],
    ),
]


def list_rules():
    return (
        base_rules
        + ip_usage_rules
        + security_risk_type_rules
        + security_risk_rules
    )
