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

import datetime
from unittest import mock

import flask_testing
from oslo_config import cfg
from oslo_context import context
from oslo_utils import uuidutils

from varroa import app
from varroa.common import keystone
from varroa import extensions
from varroa.extensions import db
from varroa import models


PROJECT_ID = "ksprojectid1"
USER_ID = "ksuserid1"

PORT_ID = uuidutils.generate_uuid()
RESOURCE_ID = uuidutils.generate_uuid()
START = datetime.datetime(2020, 2, 2)


class TestCase(flask_testing.TestCase):
    def create_app(self):
        return app.create_app(
            {
                "SECRET_KEY": "secret",
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            },
            conf_file="varroa/tests/etc/varroa.conf",
        )

    def setUp(self):
        super().setUp()
        self.addCleanup(mock.patch.stopall)
        db.create_all()
        self.context = context.RequestContext(
            user_id=USER_ID, project_id=PROJECT_ID
        )

    def tearDown(self):
        super().tearDown()
        db.session.remove()
        db.drop_all()
        cfg.CONF.reset()
        extensions.api.resources = []

    def create_ip_usage(
        self,
        ip="203.0.113.1",
        project_id=PROJECT_ID,
        port_id=PORT_ID,
        resource_id=RESOURCE_ID,
        resource_type="instance",
        start=START,
        end=None,
    ):
        ip_usage = models.IPUsage(
            ip=ip,
            project_id=project_id,
            port_id=port_id,
            resource_id=resource_id,
            resource_type=resource_type,
            start=start,
            end=end,
        )
        db.session.add(ip_usage)
        db.session.commit()
        return ip_usage

    def create_security_risk_type(
        self, name='ssh-password', description="Don't allow root to ssh"
    ):
        # Get-or-create by name: the name is unique, and create_security_risk
        # calls this with the default name on every invocation.
        sr_type = (
            db.session.query(models.SecurityRiskType)
            .filter_by(name=name)
            .first()
        )
        if sr_type is None:
            sr_type = models.SecurityRiskType(
                name=name, description=description
            )
            db.session.add(sr_type)
            db.session.commit()
        return sr_type

    def create_security_risk(
        self,
        ipaddress='203.0.113.1',
        time=datetime.datetime(2020, 2, 3),
        expires=datetime.datetime(2020, 3, 3),
        project_id=None,
    ):
        sr_type = self.create_security_risk_type()

        sr = models.SecurityRisk(
            ipaddress=ipaddress,
            time=time,
            type_id=sr_type.id,
            expires=expires,
        )
        sr.project_id = project_id
        db.session.add(sr)
        db.session.commit()
        return sr


class TestKeystoneWrapper:
    def __init__(self, app, roles, system_scope=False):
        self.app = app
        self.roles = roles
        self.system_scope = system_scope

    def __call__(self, environ, start_response):
        context_args = {
            'roles': self.roles,
            'user_id': USER_ID,
        }
        if self.system_scope:
            context_args['system_scope'] = 'all'
        else:
            context_args['project_id'] = PROJECT_ID

        cntx = context.RequestContext(**context_args)
        environ[keystone.REQUEST_CONTEXT_ENV] = cntx

        return self.app(environ, start_response)


class ApiTestCase(TestCase):
    ROLES = ["member"]
    SYSTEM_SCOPE = False

    def setUp(self):
        super().setUp()
        self.init_context()

    def init_context(self):
        self.app.wsgi_app = TestKeystoneWrapper(
            self.app.wsgi_app, self.ROLES, self.SYSTEM_SCOPE
        )
