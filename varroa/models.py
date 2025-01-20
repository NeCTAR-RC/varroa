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

from oslo_config import cfg
from oslo_log import log
from oslo_utils import uuidutils

from varroa.common import exceptions
from varroa.extensions import db


CONF = cfg.CONF
LOG = log.getLogger(__name__)


class IPUsage(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ip = db.Column(db.String(64), nullable=False)
    project_id = db.Column(db.String(64), nullable=False)
    port_id = db.Column(db.String(64), nullable=False, unique=True)
    resource_id = db.Column(db.String(64), nullable=True)
    resource_type = db.Column(db.String(64), nullable=True)
    start = db.Column(db.DateTime(), nullable=False)
    end = db.Column(db.DateTime(), nullable=True)

    def __init__(
        self,
        ip,
        project_id,
        port_id,
        resource_id,
        resource_type,
        start,
        end=None,
    ):
        self.ip = ip
        self.project_id = project_id
        self.port_id = port_id
        self.resource_id = resource_id
        self.resource_type = resource_type
        self.start = start
        self.end = end


class SecurityRiskType(db.Model):
    id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    display_name = db.Column(db.String(64))
    description = db.Column(db.Text())
    help_url = db.Column(db.String(255))

    def __init__(self, name, description, display_name=None, help_url=None):
        self.id = uuidutils.generate_uuid()
        self.name = name
        self.description = description
        self.display_name = display_name
        self.help_url = help_url

    def __str__(self):
        return self.display_name or self.name


class SecurityRisk(db.Model):
    NEW = 'NEW'
    PROCESSED = 'PROCESSED'

    id = db.Column(db.String(64), primary_key=True)
    status = db.Column(db.String(16), nullable=False)
    first_seen = db.Column(db.DateTime(), nullable=False)
    last_seen = db.Column(db.DateTime(), nullable=False)
    time = db.Column(db.DateTime(), nullable=False)
    type_id = db.Column(
        db.String(64), db.ForeignKey(SecurityRiskType.id), nullable=False
    )
    type = db.relationship(SecurityRiskType)
    ipaddress = db.Column(db.String(64), nullable=False)
    port = db.Column(db.Integer, nullable=True)
    expires = db.Column(db.DateTime(), nullable=False)
    project_id = db.Column(db.String(64), nullable=True)
    resource_id = db.Column(db.String(64), nullable=True)
    resource_type = db.Column(db.String(64), nullable=True)

    def __init__(self, time, type_id, ipaddress, expires, port=None):
        self.id = uuidutils.generate_uuid()
        self.status = self.NEW
        self.time = time
        self.first_seen = time
        self.last_seen = time
        sr_type = db.session.query(SecurityRiskType).get(type_id)
        if not sr_type:
            raise exceptions.SecurityRiskTypeDoesNotExist()
        self.type_id = type_id
        self.ipaddress = ipaddress
        self.expires = expires
        self.port = port
