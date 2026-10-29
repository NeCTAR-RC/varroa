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

import functools
import threading

import cotyledon
from futurist import periodics
from oslo_log import log as logging


LOG = logging.getLogger(__name__)


class PeriodicTaskService(cotyledon.Service):
    def __init__(self, worker_id, conf, manager):
        super().__init__(worker_id)
        self.conf = conf
        self.server = conf.host
        self.worker = None
        self.t = None
        self.endpoints = []
        self.manager = manager

    def clean_expired_risks(self):
        LOG.info("Running periodic task clean_expired_risks")
        self.manager.clean_expired_risks()

    def reprocess_new_risks(self):
        LOG.info("Running periodic task reprocess_new_risks")
        self.manager.reprocess_new_risks()

    def reconcile_open_ip_usages(self):
        LOG.info("Running periodic task reconcile_open_ip_usages")
        self.manager.reconcile_open_ip_usages()

    @staticmethod
    def _periodic(method, spacing):
        # periodics.periodic() sets attributes on the function it wraps,
        # which a bound method does not allow, so wrap it in a plain
        # function first.
        @periodics.periodic(spacing)
        @functools.wraps(method)
        def task():
            return method()

        return task

    def run(self):
        LOG.info("Starting periodic task thread...")

        # The spacing is read from self.conf here at run time rather than
        # with @periodics.periodic(CONF...) on the methods, because a
        # decorator argument is evaluated at import time. varroa-worker
        # imports this module before the config file is parsed, so the
        # decorators would always see the option defaults.
        task_interval = self.conf.worker.periodic_task_interval
        reconcile_interval = self.conf.worker.reconcile_interval
        callables = [
            (self._periodic(self.clean_expired_risks, task_interval), (), {}),
            (self._periodic(self.reprocess_new_risks, task_interval), (), {}),
            (
                self._periodic(
                    self.reconcile_open_ip_usages, reconcile_interval
                ),
                (),
                {},
            ),
        ]
        self.worker = periodics.PeriodicWorker(callables)
        self.t = threading.Thread(target=self.worker.start, daemon=True)
        self.t.start()

    def terminate(self):
        if self.worker:
            self.worker.stop()
            self.worker.wait()
        if self.t:
            self.t.join()

        super().terminate()
