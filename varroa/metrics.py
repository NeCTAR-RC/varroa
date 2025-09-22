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


from prometheus_client import core
from prometheus_client import registry
from sqlalchemy import func

from varroa.extensions import db
from varroa import models


class VarroaCollector(registry.Collector):
    def __init__(self, app, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = app

    def collect(self):
        with self.app.app_context():
            sr_query = db.session.query(models.SecurityRisk)
            unique_projects = sr_query.with_entities(
                func.count(func.distinct(models.SecurityRisk.project_id))
            ).scalar()
            yield core.GaugeMetricFamily(
                'varroa_projects_with_risks',
                'Number of projects with risks',
                value=unique_projects,
            )

            gage = core.GaugeMetricFamily(
                'varroa_security_risks',
                'Number of security risks per type',
                labels=['type'],
            )
            for sr_type in db.session.query(models.SecurityRiskType).all():
                count = sr_query.filter_by(type=sr_type).count()
                gage.add_metric(labels=[sr_type.name], value=count)
            yield gage
