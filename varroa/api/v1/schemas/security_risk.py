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

import marshmallow
from oslo_utils import timeutils

from varroa.api.v1.schemas import security_risk_type
from varroa.extensions import ma
from varroa import models


class UTCDateTime(marshmallow.fields.DateTime):
    """DateTime field that stores incoming values as naive UTC.

    The model's DateTime columns are timezone-naive UTC, and the worker and
    periodic tasks compare against naive UTC. Normalising on load means a
    client supplying any offset (for example +10:00) is converted to UTC
    before storage rather than having its offset silently dropped, which would
    skew IP-ownership matching and expiry.
    """

    def _deserialize(self, value, attr, data, **kwargs):
        dt = super()._deserialize(value, attr, data, **kwargs)
        if dt is not None and dt.tzinfo is not None:
            dt = timeutils.normalize_time(dt)
        return dt


class SecurityRiskSchema(ma.SQLAlchemyAutoSchema):
    type = ma.Nested(security_risk_type.SecurityRiskTypeSchema)

    class Meta:
        model = models.SecurityRisk
        load_instance = True
        include_relationships = True
        datetimeformat = '%Y-%m-%dT%H:%M:%S+00:00'


class SecurityRiskCreateSchema(ma.SQLAlchemyAutoSchema):
    time = UTCDateTime(format='%Y-%m-%dT%H:%M:%S%z', required=True)
    expires = UTCDateTime(format='%Y-%m-%dT%H:%M:%S%z', required=True)

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
