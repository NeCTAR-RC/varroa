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

import flask
from flask import request
import flask_restful

from varroa.common import keystone
from varroa import policy

API_LIMIT = 1000


class Resource(flask_restful.Resource):

    def authorize(self, rule, target={}, do_raise=True):
        rule = self.POLICY_PREFIX % rule
        enforcer = policy.get_enforcer()
        return enforcer.authorize(rule, target, self.context,
            do_raise=do_raise)

    @property
    def context(self):
        return flask.request.environ.get(keystone.REQUEST_CONTEXT_ENV, None)

    def paginate(self, query, args):
        limit = args.get('limit')
        if limit is None:
            limit = API_LIMIT

        items = query.paginate(per_page=limit)
        response = {'results': self.schema.dump(items.items),
                    'total': items.total}

        if items.has_next:
            response['next'] = "%s?page=%s" % (request.base_url,
                                               items.next_num)
        return response