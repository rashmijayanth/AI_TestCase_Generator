# ADR-0004: Rename the Milvus URI setting's environment variable, not the Python attribute

**Status:** Accepted
**Date:** 2026-08-27

## Context

`pydantic-settings` auto-derives an environment variable name from a
`Settings` field by uppercasing it: `milvus_uri` → `MILVUS_URI`. That name
turned out not to be free to claim. `pymilvus` itself reads a real OS
environment variable literally named `MILVUS_URI` for its own internal
default connection config (confirmed by reading
`pymilvus.orm.connections`' source, whose own docstring says as much:
"default config will be read from env: MILVUS_URI"). Every phase of local,
non-containerized development missed this collision entirely, because this
app's own `.env`-file loading (`pydantic-settings`'s `env_file=".env"`)
never promotes those values into real `os.environ` entries — `pymilvus`
never saw them. The first time `MILVUS_URI` became a genuine process
environment variable was Phase 9's `docker-compose.yml`, via `env_file:
.env` — and both the `api` and `worker` containers crashed at import time
with `pymilvus.exceptions.ConnectionConfigException: Illegal uri:
[/app/data/milvus_lite.db], expected form 'http[s]://...'`, because
`pymilvus`'s own connection singleton was trying to parse *our* local file
path as if it were pymilvus's own remote-server URI.

## Decision

Keep the Python-level attribute `Settings.milvus_uri` — every existing
call site (`vector_store.py`'s `get_vector_store()`, every test that
references `settings.milvus_uri`) stays unchanged — and redirect only the
*environment variable name* pydantic-settings looks for, via
`Field(validation_alias="MILVUS_DB_URI")`. `.env.example` and
`docker-compose.yml` were updated to the new name; a regression test
(`test_milvus_db_uri_env_var_is_read_and_the_colliding_name_is_ignored`)
asserts `MILVUS_DB_URI` is read and the colliding `MILVUS_URI` name is
correctly ignored by this app.

Renaming the environment variable (not the Python attribute, and not
switching to a whole different config-loading strategy) was the narrowest
fix that actually closes the collision: `pymilvus` has a legitimate,
documented claim on `MILVUS_URI`'s meaning (its own server connection
string), so this app ceding that specific name is the correct resolution,
not a workaround to route around.

## Consequences

- The env var name (`MILVUS_DB_URI`) and the Python attribute
  (`settings.milvus_uri`) now visibly differ. A future contributor reading
  only the Python code and reaching for the "obvious" env var name would
  guess wrong — mitigated with a comment at the `Field` definition itself
  explaining why, and this ADR.
- This bug class — a third-party library silently claiming a common
  environment variable name — is invisible to any verification that stays
  inside this app's own `.env`-file loading path. It only surfaces once a
  deployment mechanism (a container's `environment:`/`env_file:`, a real
  shell `export`, a systemd unit's `Environment=`) promotes `.env` values
  into real process environment variables. Worth remembering as a category
  the next time a new third-party client library is introduced: check
  whether it reads its own environment variables before assuming a
  `Settings` field name is free to use.
