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


from flask import request
import flask_restful
from flask_restful import reqparse
import marshmallow
from oslo_log import log as logging
from oslo_policy import policy

from varroa.api.v1.resources import base
from varroa.api.v1.schemas import security_risk as schemas
from varroa.common import exceptions
from varroa.common import policies
from varroa.common import utils
from varroa.extensions import db
from varroa import models


LOG = logging.getLogger(__name__)


class SecurityRiskList(base.Resource):
    POLICY_PREFIX = policies.SECURITY_RISK_PREFIX
    schema = schemas.security_risks

    def _get_security_risks(self, project_id=None):
        query = db.session.query(models.SecurityRisk)
        if project_id:
            query = query.filter_by(project_id=project_id)
        return query

    def get(self, **kwargs):
        try:
            self.authorize('list')
        except policy.PolicyNotAuthorized:
            flask_restful.abort(403, message="Not authorised")

        parser = reqparse.RequestParser()
        parser.add_argument('limit', type=int, location='args')
        parser.add_argument('all_projects', type=bool, location='args')
        parser.add_argument('project_id', type=str, location='args')
        parser.add_argument('type_id', type=str, location='args')
        parser.add_argument('resource_id', type=str, location='args')
        parser.add_argument('resource_type', type=str, location='args')
        args = parser.parse_args()
        query = self._get_security_risks(self.context.project_id)
        if self.authorize('list:all', do_raise=False):
            project_id = args.get('project_id')
            if args.get('all_projects') or project_id:
                query = self._get_security_risks(project_id)

        if args.get('type_id'):
            query = query.filter_by(type_id=args.get('type_id'))
        if args.get('resource_id'):
            query = query.filter_by(type_id=args.get('resource_id'))
        if args.get('resource_type'):
            query = query.filter_by(type_id=args.get('resource_type'))

        return self.paginate(query, args)

    def post(self, **kwargs):
        try:
            self.authorize('create')
        except policy.PolicyNotAuthorized:
            flask_restful.abort(403, message="Not authorised")

        data = request.get_json()
        if not data:
            return {"error_message": "No input data provided"}, 400

        try:
            security_risk = schemas.security_risk_create.load(data)
        except exceptions.SecurityRiskTypeDoesNotExist:
            return {'error_message': "Type does not exist"}, 404
        except marshmallow.ValidationError as err:
            return {'error_message': err.messages}, 422

        # Check if the IP address is private
        if utils.is_private_ip(security_risk.ipaddress):
            return {
                'error_message': 'Private IP addresses are not allowed'
            }, 400

        try:
            security_risk = self.manager.create_security_risk(
                self.context, security_risk
            )
        except exceptions.InvalidSecurityRisk as err:
            LOG.info("Failed to create security_risk: %s", err)
            return {'error_message': str(err)}, 401
        except Exception as err:
            LOG.error("Failed to create security risk")
            LOG.exception(err)
            return {'error_message': 'Unexpected API Error.'}, 500

        return schemas.security_risk.dump(security_risk), 201


class SecurityRisk(base.Resource):
    POLICY_PREFIX = policies.SECURITY_RISK_PREFIX
    schema = schemas.security_risk

    def _get_security_risk(self, id):
        return (
            db.session.query(models.SecurityRisk)
            .filter_by(id=id)
            .first_or_404()
        )

    def get(self, id):
        security_risk = self._get_security_risk(id)

        target = {'project_id': security_risk.project_id}
        try:
            self.authorize('get', target)
        except policy.PolicyNotAuthorized:
            flask_restful.abort(
                404, message=f"SecurityRisk {id} doesn't exist"
            )

        return self.schema.dump(security_risk)

    def delete(self, id):
        security_risk = self._get_security_risk(id)

        target = {'project_id': security_risk.project_id}
        try:
            self.authorize('delete', target)
        except policy.PolicyNotAuthorized:
            flask_restful.abort(
                404, message=f"SecurityRisk {id} doesn't exist"
            )

        self.manager.delete_security_risk(self.context, security_risk)
        return '', 204
