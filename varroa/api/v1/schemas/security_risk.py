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

from varroa.api.v1.schemas import security_risk_type
from varroa.extensions import ma
from varroa import models


class SecurityRiskSchema(ma.SQLAlchemyAutoSchema):
    type = ma.Nested(security_risk_type.SecurityRiskTypeSchema)

    class Meta:
        model = models.SecurityRisk
        load_instance = True
        include_relationships = True
        datetimeformat = '%Y-%m-%dT%H:%M:%S+00:00'


class SecurityRiskCreateSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = models.SecurityRisk
        load_instance = True
        include_fk = True
        datetimeformat = '%Y-%m-%dT%H:%M:%S%z'
        exclude = (
            'id',
            'status',
            'project_id',
            'resource_id',
            'resource_type',
            'first_seen',
            'last_seen',
        )


security_risk = SecurityRiskSchema()
security_risks = SecurityRiskSchema(many=True)
security_risk_create = SecurityRiskCreateSchema()
