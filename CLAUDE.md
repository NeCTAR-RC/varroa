# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Varroa is an OpenStack security service that tracks IP ownership over time and manages
discovered security risks for OpenStack resources. It links externally-reported security
risks (by IP address) to the OpenStack resource that owned that IP at the time, so resource
owners can see and remediate their exposures. See `README.md` for domain concepts
(IP Usage, Security Risk Type, Security Risk and its NEW/PROCESSED states).

## Commands

Tests run via `tox` (envlist defaults to `pep8` + `py312`).

- `tox` — run lint and the full unit test suite
- `tox -e py312` — run unit tests only (stestr)
- `tox -e py312 -- <regex>` — run a subset, e.g. `tox -e py312 -- varroa.tests.unit.api.v1.test_security_risks`
- `tox -e pep8` — run all pre-commit hooks (ruff, ruff-format, hacking/flake8, doc8, typos)
- `tox -e cover` — coverage report; **fails under 90%** coverage
- `tox -e genconfig` — regenerate sample config from `etc/varroa/config-generator.conf`
- `tox -e genpolicy` — regenerate sample policy from `etc/varroa/policy-generator.conf`
- `make build` — `python3 -m build` then build the Docker image (tag derived from `git describe`)

Tests depend on the OpenStack upper-constraints file for the `2026.1` release; the matching
constraint URL is also hardcoded in the `Dockerfile`. Bump both together when changing release.

This project does **not** use reno; `setup.cfg` sets `skip_changelog=true`. Do not add release notes.

## Code review / contribution workflow

Changes are submitted through **Gerrit** (`review.rc.nectar.org.au`, see `.gitreview`), not GitHub
pull requests. Submit with `git review`. Do not create local branches.

## Architecture

### Processes (entry points in `setup.cfg`)

All processes build the same Flask app via `varroa/app.py:create_app()`. Long-running workers
pass `init_config=False` because config/logging is already initialised by `common/service.py`.

- **`varroa-api`** — Flask REST API. In production served by gunicorn as `varroa.wsgi:application` (see `Dockerfile`).
- **`varroa-notification`** — Consumes neutron port notifications to maintain IP-ownership history.
- **`varroa-worker`** — RPC consumer + periodic tasks. Does the OpenStack-facing business logic.
- **`varroa-manage`** — Flask CLI (`FlaskGroup`); hosts DB migrations (flask-migrate) and `backfill-ports`.
- **`varroa-metric`** — Prometheus exporter (`varroa/metrics.py`).

Both `varroa-worker` and `varroa-notification` run their consumers as **cotyledon** `Service`s.

### The two core data flows

1. **IP usage tracking** (`varroa/notification/`): the notification consumer subscribes to the
   `ceilometer` exchange (topic `varroa`) and handles `port.create/update/delete.end` events.
   `handle_create_update` opens/updates an `IPUsage` row; `handle_end` sets its `end` timestamp.
   Only compute ports on external networks with public IPs are tracked (private IPs are skipped).

2. **Security risk processing** (`varroa/manager.py` → `varroa/worker/manager.py`): the API creates a
   `SecurityRisk` in state `NEW` and casts a `process_security_risk` RPC message to the
   `varroa-worker` topic. The worker matches the risk's IP+time against `IPUsage` (and falls back to
   querying neutron directly via `_find_and_create_ip_usage`), fills in `project_id`/`resource_id`/
   `resource_type`, dedupes against existing risks of the same type on the same resource, and marks
   the risk `PROCESSED`. The periodic task `clean_expired_risks` deletes risks past their `expires`.

### Layers

- `varroa/api/v1/` — REST layer. `__init__.py:initialize_resources` wires routes. `resources/`
  are flask_restful resources; `schemas/` are marshmallow (de)serialisers. Resources subclass
  `resources/base.py:Resource`, which provides `self.manager`, `self.context` (the oslo
  RequestContext from the WSGI environ), `authorize()`, and `paginate()`.
- `varroa/manager.py` — `Manager` used by API resources: performs DB writes and casts work to the
  worker. Distinct from `varroa/worker/manager.py`, which holds the async business logic.
- `varroa/common/` — cross-cutting infra: `config.py` (oslo.config opts + `list_opts`),
  `rpc.py` (oslo.messaging transport/notifier singletons, `init()` called from `create_app`),
  `keystone.py` (auth middleware + service session), `clients.py` (openstacksdk), `policies.py`
  (oslo.policy rule definitions), `service.py`, `exceptions.py`, `utils.py`.
- `varroa/models.py` — SQLAlchemy models: `IPUsage`, `SecurityRiskType`, `SecurityRisk`. String-PK
  models generate their own UUIDs in `__init__`.
- `varroa/extensions.py` — shared Flask extension singletons (`api`, `db`, `ma`, `migrate`).

### Auth and policy

When `auth_strategy=keystone`, the WSGI stack wraps the app with `SkippingAuthProtocol`
(keystonemiddleware, bypassed for `/` and `/healthcheck`) and `KeystoneContext`, which stores an
oslo `RequestContext` under the `oslo_context` environ key. Authorisation is per-action via
`Resource.authorize(rule)`, which formats `POLICY_PREFIX % rule` and enforces it with oslo.policy.
Rules live in `varroa/common/policies.py` (`security_admin`, `owner`, `reader_or_owner`); policy is
loaded from `/etc/varroa/policy.yaml`. Scope enforcement is on (`enforce_scope`).

### Async-context pattern

Worker and notification managers run outside the Flask request lifecycle, so they create their own
app (`app.create_app(init_config=False)`) and wrap DB-touching methods with the local `@app_context`
decorator to push a Flask app context (needed for `db.session`).

## Configuration

oslo.config driven; options registered in `varroa/common/config.py` (groups: `DEFAULT`, `worker`,
`database`, `flask`, `service_auth`). Production config lives at `/etc/varroa/varroa.conf`. Database
is MySQL (pymysql) in production, SQLite in tests. Messaging uses oslo.messaging
(control exchange `varroa`).

## Testing

Tests use stestr + flask_testing. The base classes are in `varroa/tests/unit/base.py`:

- `TestCase` builds the app against in-memory SQLite using `varroa/tests/etc/varroa.conf`, creates
  all tables in `setUp`, and provides `create_ip_usage` / `create_security_risk[_type]` factories.
- `ApiTestCase` additionally wraps the WSGI app with `TestKeystoneWrapper` to inject a fake keystone
  context; set `ROLES` / `SYSTEM_SCOPE` on the subclass to control authorisation.
