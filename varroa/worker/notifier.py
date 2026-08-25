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

import os

import jinja2
from oslo_config import cfg
from oslo_log import log as logging
from stevedore import driver as stevedore_driver

from varroa.common import clients
from varroa.common import keystone


CONF = cfg.CONF
LOG = logging.getLogger(__name__)

TEMPLATE = 'security_risk.html.tmpl'


def get_notifier():
    return stevedore_driver.DriverManager(
        namespace='varroa.notifier',
        name=CONF.worker.notifier,
        invoke_on_load=True,
    ).driver


class SecurityRiskNotifierBase:
    def send(self, security_risk):
        raise NotImplementedError

    @staticmethod
    def render_template(tmpl, context={}):
        template_dir = os.path.realpath(
            os.path.join(os.path.dirname(__file__), '../', 'templates')
        )
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir),
            autoescape=jinja2.select_autoescape(['tmpl', 'html']),
        )
        return env.get_template(tmpl).render(context)


class TaynacNotifier(SecurityRiskNotifierBase):
    def __init__(self):
        self._taynac = None

    def _get_taynac(self):
        # Build the keystone session and client once and reuse them;
        # keystoneauth refreshes the token as needed.
        if self._taynac is None:
            k_session = keystone.KeystoneSession().get_session()
            self._taynac = clients.get_taynacclient(k_session)
        return self._taynac

    def send(self, security_risk):
        taynac = self._get_taynac()
        body = self.render_template(TEMPLATE, {'security_risk': security_risk})
        # Taynac resolves the recipients from the project itself: the
        # first tenant manager becomes the recipient and the remaining
        # tenant managers and members are cc'd.
        message = taynac.messages.send(
            subject=CONF.worker.notification_subject,
            body=body,
            project_id=security_risk.project_id,
            tags=['security'],
        )
        LOG.info(
            "Sent notification for security risk %s to project %s "
            "(recipient=%s, backend_id=%s)",
            security_risk.id,
            security_risk.project_id,
            getattr(message, 'recipient', None),
            getattr(message, 'backend_id', None),
        )


class LoggingNotifier(SecurityRiskNotifierBase):
    def send(self, security_risk):
        body = self.render_template(TEMPLATE, {'security_risk': security_risk})
        LOG.info(
            "Would notify project %s about security risk %s:",
            security_risk.project_id,
            security_risk.id,
        )
        LOG.info(body)
