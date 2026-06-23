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
from sqlalchemy import exc as sa_exc

from varroa.api.v1.resources import base
from varroa.api.v1.schemas import security_risk_type as schemas
from varroa.common import exceptions
from varroa.common import policies
from varroa.extensions import db
from varroa import models


LOG = logging.getLogger(__name__)


class SecurityRiskTypeList(base.Resource):
    POLICY_PREFIX = policies.SECURITY_RISK_TYPE_PREFIX
    schema = schemas.security_risk_types

    def _get_all_security_risk_types(self):
        return db.session.query(models.SecurityRiskType)

    def get(self, **kwargs):
        try:
            self.authorize('list')
        except policy.PolicyNotAuthorized:
            flask_restful.abort(403, message="Not authorised")

        parser = reqparse.RequestParser()
        parser.add_argument('limit', type=int, location='args')
        args = parser.parse_args()
        query = self._get_all_security_risk_types()
        return self.paginate(query, args)

    def post(self, **kwargs):
        try:
            self.authorize('create')
        except policy.PolicyNotAuthorized:
            flask_restful.abort(403, message="Not authorised")

        data = request.get_json()
        if not data:
            return {"message": "No input data provided"}, 400

        try:
            security_risk_type = schemas.security_risk_typecreate.load(data)
        except marshmallow.ValidationError as err:
            return err.messages, 422

        db.session.add(security_risk_type)
        try:
            db.session.commit()
        except sa_exc.IntegrityError:
            db.session.rollback()
            return {'error_message': 'Security risk type already exists'}, 409

        return schemas.security_risk_type.dump(security_risk_type), 201


class SecurityRiskType(base.Resource):
    POLICY_PREFIX = policies.SECURITY_RISK_TYPE_PREFIX
    schema = schemas.security_risk_type

    def _get_security_risk_type(self, id):
        return (
            db.session.query(models.SecurityRiskType)
            .filter_by(id=id)
            .first_or_404()
        )

    def get(self, id):
        security_risk_type = self._get_security_risk_type(id)

        try:
            self.authorize('get')
        except policy.PolicyNotAuthorized:
            flask_restful.abort(403, message="Not authorised")

        return self.schema.dump(security_risk_type)

    def patch(self, id):
        data = request.get_json()

        errors = schemas.security_risk_typeupdate.validate(data)
        if errors:
            flask_restful.abort(400, message=errors)

        security_risk_type = self._get_security_risk_type(id)
        try:
            self.authorize('update')
        except policy.PolicyNotAuthorized:
            flask_restful.abort(
                404, message=f"SecurityRiskType {id} dosn't exist"
            )

        errors = schemas.security_risk_typeupdate.validate(data)
        if errors:
            flask_restful.abort(401, message="Not authorized to edit")

        security_risk_type = schemas.security_risk_typeupdate.load(
            data, instance=security_risk_type
        )

        try:
            db.session.commit()
        except sa_exc.IntegrityError:
            db.session.rollback()
            return {'error_message': 'Security risk type already exists'}, 409

        return self.schema.dump(security_risk_type)

    def delete(self, id):
        security_risk_type = self._get_security_risk_type(id)
        try:
            self.authorize('delete')
        except policy.PolicyNotAuthorized:
            flask_restful.abort(
                404, message=f"SecurityRiskType {id} dosn't exist"
            )
        try:
            self.manager.delete_security_risk_type(
                self.context, security_risk_type
            )
        except exceptions.SecurityRiskTypeInUse as err:
            return {'error_message': str(err)}, 409
        return '', 204
