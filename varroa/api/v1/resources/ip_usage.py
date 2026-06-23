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


import flask_restful
from flask_restful import inputs
from flask_restful import reqparse
from oslo_log import log as logging
from oslo_policy import policy

from varroa.api.v1.resources import base
from varroa.api.v1.schemas import ip_usage as schemas
from varroa.common import policies
from varroa.extensions import db
from varroa import models


LOG = logging.getLogger(__name__)


class IPUsageList(base.Resource):
    POLICY_PREFIX = policies.IP_USAGE_PREFIX
    schema = schemas.ip_usage_list

    def _get_ip_usage(self, project_id=None):
        query = db.session.query(models.IPUsage)
        if project_id:
            query = query.filter_by(project_id=project_id)
        return query

    def get(self, **kwargs):
        try:
            self.authorize("list")
        except policy.PolicyNotAuthorized:
            flask_restful.abort(403, message="Not authorised")

        parser = reqparse.RequestParser()
        parser.add_argument("limit", type=int, location="args")
        parser.add_argument(
            "all_projects", type=inputs.boolean, location="args"
        )
        parser.add_argument("project_id", type=str, location="args")
        parser.add_argument("ip", type=str, location="args")
        args = parser.parse_args()
        query = self._get_ip_usage(self.context.project_id)
        if self.authorize("list:all", do_raise=False):
            project_id = args.get("project_id")
            if args.get("all_projects") or project_id:
                query = self._get_ip_usage(project_id)

        if args.get("ip"):
            query = query.filter_by(ip=args.get("ip"))

        return self.paginate(query, args)
