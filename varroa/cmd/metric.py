#!/usr/bin/env python
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
from oslo_config import cfg
from prometheus_client import CollectorRegistry
from prometheus_client import make_wsgi_app

from varroa import app
from varroa import metrics


CONF = cfg.CONF


def create_app():
    application = app.create_app()
    metric_app = flask.Flask('varroa-metric')

    registry = CollectorRegistry()
    registry.register(metrics.VarroaCollector(app=application))

    metric_app.wsgi_app = make_wsgi_app(registry=registry)
    return metric_app


def main():
    create_app().run(host=CONF.flask.host, port=CONF.flask.metric_port)


if __name__ == "__main__":
    main()
