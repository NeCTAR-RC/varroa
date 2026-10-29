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

from urllib import parse

import flask
from flask import request
import flask_restful

from varroa.common import keystone
from varroa import manager
from varroa import policy

API_LIMIT = 1000


class Resource(flask_restful.Resource):
    def __init__(self):
        self.manager = manager.Manager()

    def authorize(self, rule, target={}, do_raise=True):
        rule = self.POLICY_PREFIX % rule
        enforcer = policy.get_enforcer()
        return enforcer.authorize(
            rule, target, self.context, do_raise=do_raise
        )

    @property
    def context(self):
        return flask.request.environ.get(keystone.REQUEST_CONTEXT_ENV, None)

    def paginate(self, query, args):
        limit = args.get("limit")
        if limit is None:
            limit = API_LIMIT
        elif limit < 1:
            flask_restful.abort(
                400, message="limit must be a positive integer"
            )

        page = request.args.get("page", 1)
        try:
            page = int(page)
        except (TypeError, ValueError):
            page = 0
        if page < 1:
            flask_restful.abort(400, message="page must be a positive integer")

        items = query.paginate(
            page=page, per_page=limit, max_per_page=API_LIMIT
        )
        response = {
            "results": self.schema.dump(items.items),
            "total": items.total,
        }

        if items.has_next:
            next_args = request.args.to_dict(flat=False)
            next_args["page"] = [items.next_num]
            query_string = parse.urlencode(next_args, doseq=True)
            response["next"] = f"{request.base_url}?{query_string}"
        return response
