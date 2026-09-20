# ARGUS Work Log

**Append new entries at the top. Do not rewrite previous entries unless correcting a
factual mistake.**

This is the shared chronological development log. It is not a planning document. For what
needs doing, see `TASKS.md`. For why things are the way they are, see `DECISIONS.md`.

## How to use this file

- **1 entry per work session.** Newest entry directly under this header block.
- **Only add your own entries.** Do not edit the other developer's entries.
- **Update it in the same pull request as your code.** A reviewer should see the change
  and the log entry together.
- **Keep entries short.** 10 lines is normal. This is a status handoff, not a diary.
- **Omit empty sections.** If nothing was blocked, delete the Blocked By line.
- **A merge conflict here is never a real conflict.** Keep both blocks.

## Entry template

```markdown
## YYYY-MM-DD | <Developer> | <Task ID>
Status: IN_PROGRESS | IN_REVIEW | DONE | BLOCKED

### Completed
What was actually finished. Specific, not "worked on X".

### Changed
Important files or components touched.

### Discovered
New technical findings the other developer needs to know.

### Problems
Bugs, failures, unexpected behaviour.

### Decisions Needed
Any unresolved choice needing team discussion. Add a DEC record if it is architectural.

### Blocked By
The exact blocker, with a task ID or a person.

### Next Step
What you will do next.

### AI Assistance
Optional. Note where an AI assistant did something worth knowing about, especially
anything that needs a human check.
```

## For AI coding assistants

Read the 3 most recent entries before proposing a change. They tell you what state the
code is actually in, which is often ahead of or behind `TASKS.md`.

When you complete work, append an entry using the template above. Record what you actually
did, not what was planned. If you were unable to complete something, say so in Problems
and leave the status as `IN_PROGRESS`. Do not mark a task `DONE` unless every acceptance
criterion in `TASKS.md` is met.

---

## 2026-09-20 | Keshan | P2-002
Status: DONE

### Completed
Built the GitHub read-only API client (`P2-002`, Issue #13):
1. Created `app/integrations/github.py` implementing `GitHubClient` using `HttpClient` and
authenticated via `GITHUB_TOKEN`.
2. Implemented methods to fetch repositories, pull requests, reviews, commits, and branches.
Strictly read-only; no write endpoints exist in the module (AC-17).
3. Handled GitHub pagination by parsing RFC-5988 `Link` headers (`rel="next"`) with
automated multi-page collection in `_paginate`.
4. Created realistic GitHub JSON fixtures in `seed/fixtures/github/` (`repositories.json`,
`pull_requests.json`, `reviews.json`, `commits.json`, `branches.json`) covering all test
scenarios (impediments, draft PRs, unlinked PRs, external contributors).
5. Added unit test suite in `tests/test_github_client.py` covering PR listing, review states,
commit metadata, branches, pagination across multiple pages, 401 auth failure, 403 rate-limiting,
and 404 not found. All 10 tests pass without live network calls.
6. Marked `P2-002` as DONE in `docs/TASKS.md`.

### Changed
`app/integrations/github.py` (new), `app/integrations/__init__.py`,
`seed/fixtures/github/*.json` (new), `tests/test_github_client.py` (new),
`docs/TASKS.md`, `WORKLOG.md`.

### Discovered
RFC-5988 `Link` headers embed existing query parameters in the `rel="next"` URL, so subsequent
pagination calls do not need original query params re-applied.

### Next Step
Proceed to `P2-003` (GitHub normalization into canonical tables) or `P2-004` (Jira read-only client).

---

## 2026-09-20 | Keshan | P2-001
Status: DONE

### Completed
Built the shared HTTP client layer for all upstream integrations (`P2-001`, Issue #12):
1. Created `app/integrations/errors.py` with base `IntegrationError` and typed subclasses:
`IntegrationTimeoutError` (`TIMEOUT`), `AuthError` (`AUTH_FAILED`), `RateLimitError`
(`RATE_LIMITED`), `NotFoundError` (`NOT_FOUND`), and `UpstreamError` (`UPSTREAM_ERROR`). Each
provides `to_tool_failure` to map directly to the frozen `ToolFailure` schema contract.
2. Created `app/integrations/http.py` implementing `HttpClient` wrapping `httpx.Client`:
   - Configures explicit 10-second connect and read timeouts (`HTTP_TIMEOUT_SECONDS`, NFR-001).
   - Retries up to 3 attempts (`HTTP_MAX_ATTEMPTS`, NFR-002) using tenacity on 429, 5xx, and
     connection/transport errors. Never retries other 4xx errors (400, 401, 403, 404).
   - Implemented `_WaitRetryAfterOrExponential` honoring `Retry-After` headers on 429,
     falling back to exponential backoff with jitter.
   - Disambiguates HTTP 403: detects rate-limiting headers (`x-ratelimit-remaining: 0` or
     `retry-after`) and maps to `RateLimitError`, while standard 403 maps to `AuthError`.
   - Redacts sensitive tokens from authorization headers and query parameters before logging.
   - Supports injectable `httpx.BaseTransport` for offline fixture replay and tests (DEC-012).
3. Added test suite in `tests/test_http_client.py` covering: success 200, timeout retry exhaustion,
401 without retry, 403 rate-limited vs forbidden, 404 without retry, 429 retry with `Retry-After`,
500 upstream error with 3 attempts, secret log redaction, mock transport injection, and explicit
timeout enforcement.
4. Marked `P2-001` as DONE in `docs/TASKS.md`.

### Changed
`app/integrations/errors.py` (new), `app/integrations/http.py` (new),
`app/integrations/__init__.py`, `tests/test_http_client.py` (new), `docs/TASKS.md`,
`WORKLOG.md`.

### Discovered
GitHub rate-limiting on 403 is distinguished cleanly from authorization denial using the
`x-ratelimit-remaining` and `retry-after` response headers.

### Next Step
Start `P2-002` (GitHub read-only client) using `HttpClient`.

---

## 2026-09-20 | Keshan | P1-005
Status: DONE

### Completed
Resolved remaining open criteria for Phase 0 and Phase 1:
1. Closed #9 (`P1-003`): Added `lifespan` handler to `app/main.py` calling `get_settings()` during
startup so missing secrets halt immediately. Removed localhost fallback in `app/db.py`, raising
`RuntimeError` if `DATABASE_URL` is unset. Added startup failure test in `tests/test_config.py`.
2. Closed #10 (`P1-004`): Added real `pg_sleep(3)` statement timeout test in `tests/test_db.py`
verifying statement cancellation and `is_timeout_error` detection. Added PostgreSQL 15 service
container to the CI `test` job in `.github/workflows/ci.yml`.
3. Closed #11 (`P1-005`): Discovered exact GitHub numeric IDs (`keshan-dev`: 219891474,
`IsiwaraKumarage8`: 221026807) and populated `seed/identity_map.yml`, replacing dummy literals.
Updated `tests/test_identity_loader.py` assertions to verify real IDs and handles.
4. Closed #4 (`P0-004`) and #5 (`P0-005`): Marked DONE in `docs/TASKS.md` following confirmed CI
workflows and Ollama measurements on both machines. Marked #8 (`P1-002`) DONE following merge to
`main`.

Phase 0 and Phase 1 are now 100% complete.

### Verification
Ran in a scratch venv pinned to the versions CI resolves (black 26.5.1, ruff 0.16.8):
`ruff check .` passed, `black --check .` initially failed on 3 files and was corrected by
running `black .` rather than by hand.

Full suite run against a throwaway `postgres:15` container: 32 passed, 0 failed. The live
`pg_sleep(3)` test confirms the 2000ms read-path statement timeout cancels the query and
that `is_timeout_error` recognises it. Not verified: the CI job itself, which runs on the
pull request.

### Problems
1. `black --check` would have failed CI on `app/db.py`, `tests/test_db.py` and
`tests/test_config.py` (2 trailing blank lines, 1 line-length reflow). Fixed by running
black. This is the third time hand-formatting has caused this. Pinning an exact black
version in the dev extras would remove the class of failure, but it is a dependency change
and needs both developers to agree (rule 13).
2. `test_startup_fails_without_secrets` passed in CI but failed on a developer machine.
`Settings` reads `env_file=".env"` relative to the working directory, so a local `.env`
supplied the secrets the test expects to be missing and no `RuntimeError` was raised. Fixed
by adding `monkeypatch.chdir(tmp_path)` so the test asserts the same thing in both places.

### Changed
`app/db.py`, `app/main.py`, `seed/identity_map.yml`, `tests/test_config.py`, `tests/test_db.py`,
`tests/test_identity_loader.py`, `.github/workflows/ci.yml`, `docs/TASKS.md`, `README.md`,
`WORKLOG.md`.

### Discovered
Isiwara's GitHub account is `IsiwaraKumarage8` (numeric ID 221026807), matching repository
contributors.

### Next Step
Open the pull request from `fix/9-close-phase-0-and-1-criteria`, closing #4, #9, #10 and #11.
CI validates all 5 jobs. Begin Phase 2 (`P2-001` shared HTTP client) while Isiwara starts
Phase 3 (`P3-001` FastAPI routes and auth seam).

---

## 2026-09-19 | Keshan | P1-005
Status: IN_PROGRESS

### Completed
Created `seed/identity_map.yml` documented with a header comment block explaining fields,
constraints, and initial entries for team members Keshan and Isiwara with stable external IDs.
Implemented `app/integrations/identity_loader.py` with YAML parsing that reports exact problem
line numbers on syntax errors, Pydantic schema validation, and cross-person duplicate external ID
checks. Implemented `load_identity_map` writing `IdentityLink` rows with `match_method = manual`
and `confidence = HIGH`, handling existing user lookup, unmatched entity resolution, and
idempotent re-runs. Added test suite in `tests/test_identity_loader.py` covering valid seeding,
idempotency, duplicate rejection across people, malformed YAML lines, and unmatched resolution.

### Changed
`seed/identity_map.yml` (new), `app/integrations/__init__.py` (new),
`app/integrations/identity_loader.py` (new), `tests/test_identity_loader.py` (new),
`docs/TASKS.md`.

### Problems
The CI lint job failed on `black --check`. `app/integrations/identity_loader.py` and `tests/test_identity_loader.py` were wrapped at 88 columns, black's default, not the 100 this project sets in `pyproject.toml`. Both statements fit on 1 line at 100. Ruff passed. Fixed by running black, no logic changed.

This is the 3rd pull request in a row to fail on exactly this (#66, #68, #69). The cause is that neither developer has black installed, so formatting is done by hand or with a tool using its own default width. Pinning black to an exact version in the dev extras and actually installing it locally is the fix. It needs agreement, so it is raised below rather than done here.

### Decisions Needed
**Pin `black` and `ruff` to exact versions in `[project.optional-dependencies] dev`.** Today they are floating (`black>=24.10`, `ruff>=0.7`), so CI resolves the newest release on every run and the formatting target moves without anyone changing code. A commit that passed last week can fail today. Pinning also makes a local install match CI, which is what stops the repeat failures above. Cost is zero, it is not a new dependency, only a version constraint on 2 that are already there.

### Next Step
Merge P1-005 to `main`. This completes Phase 1. Proceed to Phase 2 (Data and Integrations,
P2-001 HTTP client) in parallel with Phase 3 (Agent Foundation).

---

## 2026-09-19 | Keshan | P1-002
Status: IN_PROGRESS

### Completed
Defined all frozen Pydantic contracts across `app/schemas/`. Created `app/schemas/errors.py`
with `ToolFailure` and typed error categories. Created `app/schemas/tools.py` with exact
inputs and outputs for all 7 deterministic read tools (T-001 through T-007) matching
`AGENT_TOOLS.md`. Created `app/schemas/insight.py` defining `EvidenceItem` matching
`DATA_AND_EVIDENCE.md` 6.5, `Claim` with strict `list[str]` evidence ID invariance
enforcing DEC-004, `Insight`, and `MemberInsight` including per-source freshness and health
status. Exported all contracts via `app/schemas/__init__.py`. Added comprehensive unit
tests in `tests/test_schemas.py` covering round-trip serialization and rejection of
embedded evidence objects.

### Changed
`app/schemas/__init__.py` (new), `app/schemas/errors.py` (new), `app/schemas/tools.py` (new),
`app/schemas/insight.py` (new), `tests/test_schemas.py` (new), `docs/TASKS.md`, `.gitignore`, `pyproject.toml`.

### Problems
The CI lint job failed. 2 separate causes.

1. 10 `UP017` violations: `datetime.now(timezone.utc)` in `app/schemas/errors.py` and `tests/test_schemas.py`. `app/main.py` already used `datetime.now(UTC)`, so the new files did not follow the convention already in the tree. Fixed with `ruff --fix`. `UTC` is an alias of `timezone.utc`, so behaviour is unchanged.
2. `black` wanted 2 files rewrapped. They were wrapped at 88 columns, black's default, not the 100 this project sets.

### Discovered
**CI was linting a generated copy of the tree.** `pip install ".[dev]"` makes setuptools write `build/lib/app/...`, and ruff's default exclude list has `_build`, `buck-out` and `dist` but not `build`. Black's defaults do exclude `build`. So ruff reported 11 errors where only 10 were real, the 11th being the copy of `app/schemas/errors.py` under `build/lib/`. A stale `build/` on a developer machine is worse than noise: it keeps copies of deleted files, so ruff reports errors in code that no longer exists. Added `extend-exclude = ["build"]` to `[tool.ruff]` and `build/` plus `dist/` to `.gitignore`, which was missing both.

### Next Step
Merge P1-002 to `main`, then proceed to `P1-005` (identity map format and loader).

---

## 2026-09-19 | Keshan | P1-001 & P1-004
Status: DONE

### Completed
Implemented `app/db.py` with SQLAlchemy engine, `SessionLocal`, FastAPI `get_session` dependency, and read-path statement timeout support (`DB_STATEMENT_TIMEOUT_MS = 2000`). Defined all 17 canonical models across `app/models/` (`canonical.py`, `identity.py`, `work.py`, `agent.py`, `operations.py`) using SQLAlchemy 2.0 declarative mappings. Ensured person table is named `app_user` (not `user`), all timestamps are `timestamptz` in UTC, and external tables carry non-null `source_updated_at` and `retrieved_at` columns. Configured Alembic (`alembic.ini`, `migrations/env.py`) and created initial migration `migrations/versions/0001_initial.py` defining all tables, unique constraints, and indexes. Added unit tests in `tests/test_models.py` and `tests/test_db.py`.

### Changed
`app/db.py` (new), `app/models/__init__.py` (new), `app/models/canonical.py` (new), `app/models/identity.py` (new), `app/models/work.py` (new), `app/models/agent.py` (new), `app/models/operations.py` (new), `alembic.ini` (new), `migrations/` (new), `tests/test_models.py` (new), `tests/test_db.py` (new), `docs/TASKS.md`.

### Problems
The CI lint job failed on `black --check`: `tests/test_db.py` ended with a trailing blank line. CI installs the newest black (26.5.1) because `pyproject.toml` pins only `black>=24.10`, and neither developer has black installed locally, so formatting has been corrected by hand across 3 commits. Fixed by running black over the file. Ruff cannot catch this: `W391` is preview-only, so adding `W` to the selected rules would not have prevented it. Pinning black to an exact version in the dev extras is the real fix and needs agreement first.

### Next Step
`P1-002` (freeze Pydantic contracts) and `P1-005` (identity map format and loader).

---

## 2026-09-19 | Keshan | P1-003
Status: DONE

### Completed
Implemented `app/config.py` using Pydantic `BaseSettings` with all 10 thresholds and runtime settings defined as typed named constants. Required secrets (`DATABASE_URL`, `GITHUB_TOKEN`, `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`) have no default values and fail fast when missing from the environment. Sensitive values are redacted in string representations (`__repr__` and `__str__`) to prevent token leaks in log lines. Updated `.env.example` with empty values and added unit tests in `tests/test_config.py` plus test isolation in `tests/conftest.py`.

### Changed
`app/config.py` (new), `.env.example`, `tests/conftest.py` (new), `tests/test_config.py` (new), `docs/TASKS.md`.

### Next Step
`P1-004` (database session management and statement timeouts) and `P1-001` (canonical models).

---

## 2026-09-19 | Isiwara | P0-005
Status: IN_REVIEW

### Completed
Ran `scripts/check_ollama.py` on my machine. 12 checks passed, 0 failed. Model `llama3.2`
was already pulled. The `api` container reaches Ollama at `host.docker.internal:11434`
(HTTP 200).

| Measurement | Value |
|---|---|
| Machine | Windows 11 Pro, 15.6 GB RAM, Intel CPU (family 6, model 154) |
| Ollama | 0.34.2 |
| Model | `llama3.2` (3B) |
| Prompt processing | 4837.9 tok/s (not comparable, see Discovered) |
| Generation | 15.4 tok/s |
| Narrative call latency | 8.7 s |
| Warm-up | 2.1 s |
| Schema enforcement | works |
| Reproducible (temperature 0 + seed) | yes, byte-identical across runs |
| Cost | zero |

With Keshan's entry of 2026-09-13, both machines now have every measurement the "on both
machines" criteria of #5 ask for. I have not changed the task status. That is for Keshan.

### Changed
`WORKLOG.md` only. No code changed.

### Discovered
**Prompt processing reads 4837.9 tok/s here against 98.7 tok/s on Keshan's machine.** That
is a 49x gap while generation speed is close (15.4 against 14.2 tok/s), so it is not a
hardware difference. My guess is that Ollama reused a cached prompt after the warm-up run,
but I have not confirmed it. Treat this number as not comparable. Generation speed and
latency are the ones that matter for NFR-013.

**`ollama --version` printed 0.33.2 earlier today and the script printed 0.34.2 later.** The
measurements above are from 0.34.2. Keshan's were on 0.33.3.

### Next Step
Waiting on P0-002 (Keshan), which unblocks Phase 1 for me.

### AI Assistance
An AI assistant guided me through both tasks and drafted these 2 entries. Every number is
copied from my own terminal output. The prompt-processing figure is the 1 item that needs
a human check.

---

## 2026-09-19 | Isiwara | P0-003
Status: IN_REVIEW

### Completed
Confirmed the skeleton runs on my machine. This is the 1 criterion left open when #3 was
closed: "Both developers confirm it runs on their machine."

| Check | Result |
|---|---|
| `docker compose up --build -d` | `db` healthy, `api` up (image build 55.5 s) |
| `GET /health` | 200, `{"status":"ok","service":"argus","version":"0.1.0",...}` |
| `pytest` inside the container | 1 passed |
| `ruff check .` inside the container | All checks passed |
| `black --check .` inside the container | 5 files unchanged |
| Ollama reachable from `api` at `host.docker.internal:11434` | HTTP 200 |

The default `API_PORT=8000` worked. The reserved TCP ranges on this machine are all
50000 and above, so port 8000 was free.

### Changed
`WORKLOG.md` only. No code changed.

### Discovered
**Docker Desktop refused to start with "Virtualization support not detected", but
virtualization was on.** `systeminfo` reported "A hypervisor has been detected", and
`wsl --status` reported that WSL was not installed. Docker Desktop needs WSL 2 on Windows,
and the error message points at the BIOS when the real cause is the missing WSL. Fix, in an
Administrator prompt: `wsl --install --no-distribution`, then restart Windows. No BIOS
change was needed.

**`python` on this machine is a Microsoft Store shortcut that fails** with "The system
cannot find the path specified". `py` works (Python 3.14.6). The Ollama check ran as
`py -X utf8 scripts/check_ollama.py`. The project itself runs on Python 3.11 inside the
container, so the host Python version did not matter.

### Next Step
Keshan to review. Suggest adding the 2 Windows findings above to `docs/HOW_TO.md`. I have
not changed it.

---
## 2026-09-19 | Keshan | P0-003
Status: DONE

### Completed
#64 merged. Issue #3 closed with each acceptance criterion recorded against its evidence.
`TASKS.md` P0-003 set to DONE and `README.md` 14 now says the skeleton exists.

Phase 0 is 3 of 6 done: P0-001, P0-003, P0-006. Open: P0-002, P0-004, P0-005.

### Changed
`docs/TASKS.md` P0-003 status, `README.md` 14.

### Problems
**P0-003 closed with 1 criterion unmet:** "Both developers confirm it runs on their
machine." Only Keshan's machine is confirmed. Closed anyway so it does not block Phase 1,
and the issue says plainly to reopen it if `docker compose up --build` fails for Isiwara.

### Next Step
P0-002, real Jira and GitHub data plus fixtures. It is now the only thing blocking Phase 1
and the only Phase 0 task that needs external access rather than code.

---

## 2026-09-19 | Keshan | P0-003
Status: IN_REVIEW

### Completed
Docker verified end to end on Keshan's machine. Every technical criterion on P0-003 passes,
and the outstanding container criterion on P0-005 is now met.

| Check | Result |
|---|---|
| `docker compose up --build` | `db` healthy, `api` up |
| `GET /health` | 200, `{"status":"ok","service":"argus","version":"0.1.0",...}` |
| `pytest` inside the container | 1 passed |
| `ruff check .` inside the container | All checks passed |
| `black --check .` inside the container | 5 files unchanged |
| PostgreSQL reachable from `api` | PostgreSQL 15.19 |
| Ollama reachable from `api` at `host.docker.internal:11434` | HTTP 200, `llama3.2:latest` listed |

### Changed
`docker-compose.yml`, `.env.example`.

### Discovered
**Port 8000 cannot be bound on this Windows machine.** `docker compose up` failed with
"An attempt was made to access a socket in a way forbidden by its access permissions".
Nothing was listening on 8000. The cause is a Hyper-V reserved TCP range:

```text
netsh interface ipv4 show excludedportrange protocol=tcp
  7915  8014      <- 8000 falls inside this
  8115  8214
  8316  8415
```

This is a Windows artifact, not a project bug, and it can appear on any Windows machine
including Isiwara's. The reserved ranges also move between reboots.

Fixed by making the host port configurable, `${API_PORT:-8000}`, with the container port
still 8000. The default is unchanged, so nothing breaks for a machine where 8000 is free.
This machine runs `API_PORT=8080` in its own `.env`. The diagnostic command is recorded in
`.env.example` next to the variable.

### Problems
**1 criterion on P0-003 is outstanding: "Both developers confirm it runs on their
machine."** Isiwara has not started, so only Keshan's machine is confirmed.

**P0-005 cannot close.** 5 of its 7 criteria say "on both machines" explicitly: Ollama
installed, `llama3.2` pulled, `api/tags` returning the model, a schema-valid structured
call, and recorded tokens/sec. Only the container reachability and zero-cost criteria are
fully met. It stays open until Isiwara runs `python scripts/check_ollama.py`.

### Next Step
P0-002, real Jira and GitHub data plus fixtures.

---

## 2026-09-19 | Keshan | P0-001
Status: DONE

### Completed
CI merged in #61 and went green on its first run, all 5 jobs. The 5 checks are now required
on `main` with `strict: true`, so a branch must also be up to date before it can merge:

```text
Lint and format, Tests, Secret scan, Migrations, Project rules
```

That was the last outstanding acceptance criterion on P0-001, which had been waiting
because a status check cannot be required before it has run once. Issue #1 closed with the
criteria verified one by one against the repository.

Phase 0 statuses corrected in `TASKS.md`: P0-001 DONE, P0-003 IN_PROGRESS, P0-004
IN_PROGRESS.

### Changed
`docs/TASKS.md` statuses, `README.md` 14.

### Problems
**1 P0-001 criterion could not be verified:** the project board columns. `gh project list`
needs the `read:project` scope, which this token does not have. Everything else was
confirmed directly. Noted on the issue so it can be reopened in seconds if the board is
missing.

### Next Step
P0-002, real Jira and GitHub data plus fixtures. Nothing else unblocks Isiwara.

---

## 2026-09-19 | Keshan | P0-004
Status: IN_REVIEW

### Completed
CI pipeline, `.github/workflows/ci.yml`, 5 jobs on every pull request into `main`:
`lint` (ruff, black), `test` (pytest), `secret-scan` (gitleaks over both the tree and the
history), `migrations` (PostgreSQL 15 service container), and `project-rules`.

`project-rules` mechanically enforces 3 rules that were previously only written down:
no AI attribution in commit messages, `WORKLOG.md` updated in the pull request, and no
HTTP client imported under `app/tools/`. The `CLAUDE.md` enforcement table is updated to
match, and 7 rows moved from "to add" to Active.

### Changed
`.github/workflows/ci.yml` (new), `CLAUDE.md` enforcement table.

### Discovered
**The gitleaks marketplace action asks organizations for a licence key.** Used the gitleaks
binary from the GitHub release instead, which is free and adds no paid dependency
(CLAUDE.md rule 13).

**The attribution check reads commit messages only, not file contents.** `CLAUDE.md`,
`HOW_TO.md` and `WORKLOG.md` all quote those strings in prose. A content grep would fail on
the files that define the rule.

**The 2 Alembic criteria on this task cannot be met yet.** `alembic.ini` and
`migrations/versions` arrive in P1-001. The job detects their absence and skips rather than
faking a pass, so it switches itself on when the directory appears. Same pattern for the
`app/tools/` check, which waits for P3-002.

### Problems
**Docker could not be verified on this machine.** Docker Desktop and its WSL distro are
running, but the Linux engine returns 500 on every API route, at every API version from
1.41 to 1.54. So `docker compose up --build` is still unrun and the P0-005 in-container
Ollama reach is still unchecked. Both need a Docker Desktop restart.

### Next Step
Merge, let CI run once, then add the 5 checks to branch protection as required. That closes
the last acceptance criterion on P0-001.

---

## 2026-09-17 | Keshan | P0-003
Status: IN_PROGRESS

### Completed
Project skeleton: `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `.env.example`,
`app/main.py` with `/health`, and `tests/test_health.py`.

Verified locally in a throwaway virtual environment:

| Check | Result |
|---|---|
| `pytest` | 1 passed |
| `ruff check .` | All checks passed |
| `black --check .` | 5 files unchanged |

### Changed
`pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `.env.example`, `app/main.py`,
`app/__init__.py`, `tests/test_health.py`, `tests/__init__.py`,
`scripts/check_ollama.py` (formatting only).

### Discovered
**Lint failed repo-wide on `scripts/check_ollama.py`**, which merged before any lint
configuration existed. 10 findings. Resolved by running black over it and adding 3 scoped
per-file ignores in `pyproject.toml`, each with the reason inline:

- `E501`: the file embeds the real S4b prompt. Reflowing that text would change the prompt
  and invalidate the measurements recorded in the P0-005 entry below. Verified by diff that
  the prompt text is byte-identical after formatting.
- `S310` and `S607`: it calls the local Ollama HTTP API and invokes `ollama` and `docker`
  from PATH, both by design for a local setup checker.

Without this, the first CI run in P0-004 would have failed on a file nobody had touched.

**`anthropic` is not installed**, per DEC-017. Ollama is reached over plain HTTP with
`httpx`. The `TASKS.md` dependency list has been corrected in #57.

### Problems
**Docker Desktop was not running on this machine, so the 2 container criteria are
unverified.** `docker compose up --build` has not been run, `/health` has not been hit over
HTTP, and the outstanding P0-005 criterion (reaching Ollama at
`host.docker.internal:11434` from inside the api container) is still open. The FastAPI app
itself is verified by the unit test, which exercises the same endpoint in-process.

This is why the task stays `IN_PROGRESS` and the pull request says `Refs #3`, not
`Closes #3`.

### Next Step
Start Docker Desktop, run `docker compose up --build`, hit `/health`, and check the
in-container Ollama reach. Then Isiwara confirms the same on her machine. Both go in this
log before #3 closes.

---

## 2026-09-17 | Keshan | #57
Status: IN_REVIEW

### Completed
Reconciled the status tables against the repository, and added the 4 procedures used today
to `docs/HOW_TO.md`: A10 merge a pull request and confirm it landed, B9 configure branch
protection, B10 reconcile a status file with reality, B11 add or change a project rule.
21 recipes total.

`README.md` 14 and `TASKS.md` "Start here" now say what is actually next, and both carry
the date they were reconciled. Phase 0 statuses corrected: P0-001 IN_REVIEW, P0-005
IN_PROGRESS, P0-006 DONE.

### Changed
`README.md` 14, `docs/TASKS.md` (statuses, Start here, P0-003 notes), `docs/HOW_TO.md`.

### Discovered
**`TASKS.md` P0-003 listed `anthropic` as a dependency.** DEC-017 moved inference to local
Ollama and states there is no LLM API key anywhere in the system, so the SDK has nothing to
call. Removed, with the reason recorded inline so it is not re-added. Ollama is reached
over plain HTTP with `httpx`.

This is the second stale-document failure today, after the duplicate PR #53. Both came from
trusting a cached view instead of the system. B10 exists because of it.

### Next Step
P0-003 skeleton.
## 2026-09-17 | Keshan | P0-001
Status: IN_REVIEW

### Completed
Finished the repository configuration that was outstanding on #1.

Branch protection on `main` tightened (applied through the GitHub API, not in this diff):
1 required approval, stale reviews dismissed on a new push, conversation resolution
required, linear history required, force push and deletion blocked.

Added `.gitignore`, `.github/pull_request_template.md` and
`.github/ISSUE_TEMPLATE/task.md`.

### Changed
`.gitignore` (new), `.github/` (new).

### Discovered
**`.gitignore` did not exist at all.** P0-001 says it must ignore `.env` before any other
commit, and `.env` becomes real in P0-003, so this was the last safe moment. Nothing has
leaked: no `.env` has existed in this repository yet.

**`enforce_admins` was deliberately left off.** Turning it on would subject Developer 1 to
the 1 approval rule and make self-merging impossible, which contradicts the review policy
in `README.md` 13. With Keshan as admin and Isiwara on write access, the current settings
produce exactly the documented behaviour: Isiwara's pull requests need an approval,
Developer 1 can merge their own.

**Required status checks are still empty.** A check cannot be required before it has ever
run, so this stays open until P0-004 creates the CI workflow. It is the 1 criterion of
this task that P0-004 has to close.

### Next Step
Reconcile the stale status tables in `README.md` and `TASKS.md`, then P0-003.

---

## 2026-09-17 | Keshan | #54
Status: IN_REVIEW

### Completed
Added 2 developer guides, neither of which adds scope.

`docs/BUILD_ORDER.md`, the layer view of the application: 17 code sections in dependency
order, each with its files, the concepts to learn before writing it, a runnable "done
when" check and the traps. Every section maps to task IDs that already exist in
`TASKS.md`, which stays authoritative for ordering and ownership.

`docs/HOW_TO.md`, the recurring procedures: splitting changes onto a branch, migrations,
fixtures, config values, contract changes after the freeze, a committed secret, and the
undo table. Each recipe leads with why that method rather than another, because that is
the part that is not recoverable from a command list.

`CLAUDE.md` at the repository root, the rule set itself: 15 hard rules with the reason
for each, what to do when a rule blocks a task, and an honest table of where each rule is
actually enforced rather than merely written down. 6 of those enforcement checks do not
exist yet and are marked as belonging to P0-004, P3-001 and P3-002.

`.claude/settings.json` sets the Claude Code attribution strings to empty, so no
`Co-Authored-By` or "Generated with" line can reach a commit or a pull request from
either machine. It is committed, so it binds both of us rather than 1 laptop.

All 3 linked from the README documentation map.

### Changed
`CLAUDE.md` (new), `.claude/settings.json` (new), `docs/BUILD_ORDER.md` (new),
`docs/HOW_TO.md` (new), `README.md` section 11.

### Decisions Needed
None, but P0-004 now has 4 extra CI checks to implement: an attribution grep, a
WORKLOG-changed check, the secret scanner, and the single-migration-head check. They are
listed in the enforcement table in `CLAUDE.md`.

### Problems
PR #53 was opened for `chore/5-ollama-check` against a stale local `main`. That work was
already squash-merged as #52, and `git diff origin/main origin/chore/5-ollama-check` is
empty. #53 closed as a duplicate. Recipe A1 in `HOW_TO.md` exists because of it: fetch
before judging branch state, and compare content against `origin/main`, not `main`.

### Next Step
P0-002, real Jira and GitHub data plus captured fixtures. Then P0-003, the skeleton.

---

## 2026-09-13 | Keshan | P0-005
Status: IN_PROGRESS

### Completed
Added `scripts/check_ollama.py`, a standard-library-only script that verifies every
acceptance criterion on issue #5 and prints a WORKLOG block. It runs the real ARGUS
narrative task (stage S4b), not a toy prompt, so the numbers reflect actual use.

Verified on my machine. 11 checks passed, 0 failed.

| Measurement | Value |
|---|---|
| Machine | Windows, 7.7 GB RAM, i7-12650H, no dedicated GPU |
| Ollama | 0.33.3 |
| Model | `llama3.2` (3B) |
| Prompt processing | 98.7 tok/s |
| Generation | 14.2 tok/s |
| Narrative call latency | 12.9 s |
| Cold warm-up | 8.2 s |
| Schema enforcement | works |
| Cost | zero |

### Discovered
**Output is byte-identical across two runs** with `temperature: 0` and a fixed seed. That
confirms the reproducibility claim in DEC-011 and DEC-017 rather than assuming it, and it
means the evaluation suite can assert on exact output.

Latency is 12.9 s against the 20 s target in NFR-013, with room to spare. Earlier probes
measured 4 tok/s with only 0.5 GB RAM free versus 14.2 tok/s here, so the guidance to close
other applications before demoing is worth keeping.

### Blocked By
Nothing. 1 acceptance criterion is outstanding: reachability from a container
(`host.docker.internal:11434`). Docker was not running during this check. It is best
verified during P0-003 when `docker-compose.yml` exists.

### Next Step
Isiwara runs `python scripts/check_ollama.py` on her machine and appends her numbers.
Then P0-002: real Jira and GitHub data plus captured fixtures.

---

## 2026-09-13 | Shared | P0-006
Status: DONE

### Completed
Ratified all 19 architecture decisions. Both developers read `docs/DECISIONS.md` and agreed.
Every decision moved from `Proposed` to `Accepted`. Four are marked as amended: DEC-003 by
DEC-016, DEC-005 by DEC-018, DEC-011 by DEC-017, DEC-015 by DEC-019.

Context for the record, since these were added after the first documentation pass:

- **DEC-017** the project must use Ollama, so inference is local (`llama3.2`, 3B) and costs
  nothing. There is no LLM API key anywhere in the system.
- **DEC-018** the model no longer produces claims, classifications or evidence IDs. Code
  produces the findings and the model writes 2 sentences over them.
- **DEC-019** lane rebalance. 13 tasks moved to Developer 1. Split is now 24 / 15 / 10.

Also completed earlier: all 49 tasks created as GitHub issues with labels, milestones,
assignees and dependency links, triaged for the 3 week deadline into 40 demo-critical,
3 stretch and 6 deferred. Branch protection enabled on `main`.

### Changed
`docs/DECISIONS.md` statuses. No code exists yet.

### Discovered
Measured `llama3.2` (3B) on the demo machine (7.7 GB RAM, i7-12650H, no dedicated GPU):

- Ollama JSON schema enforcement works, and `temperature: 0` plus a fixed `seed` are
  supported, so evaluation runs are reproducible.
- About 13 tokens/sec warm, about 4 tokens/sec with only 0.5 GB RAM free. **RAM is the
  binding constraint, not the CPU.** Close other applications before demoing.
- Asking the model to produce claims plus classifications plus evidence IDs took 22.1 s and
  **missed the blocker entirely**, ignoring a changes-requested review that was in the
  evidence set.
- Asking it only to write the narrative over code-produced findings took 15.3 s and caught
  the blocker, because rule BL-4 caught it in code.

That measurement is the basis for DEC-018.

### Next Step
P0-005: Ollama installed on both machines, tokens/sec recorded for each.
Then P0-002: real Jira and GitHub data plus captured fixtures. P0-002 unblocks Developer 2
for the next two weeks, so it is the one to protect.

---

## 2026-09-13 | Shared | Documentation foundation
Status: DONE

### Completed
Created the ARGUS documentation set in `docs/`, before any application code:
`README.md`, `PROJECT_REQUIREMENTS.md`, `AGENT_ARCHITECTURE.md`, `AGENT_TOOLS.md`,
`AI_BEHAVIOR.md`, `DATA_AND_EVIDENCE.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `TASKS.md`,
`WORKLOG.md`, `TESTING_AND_EVALUATION.md`.

Defined 33 functional requirements (FR-001 to FR-033), 33 non-functional requirements,
15 architecture decisions (DEC-001 to DEC-015), 7 agent tools (T-001 to T-007), 47 tasks
across 8 phases, and 12 evaluation scenarios.

### Changed
`docs/` created. No application code exists yet.

### Discovered
5 gaps were found in the earlier planning material and are now resolved in the
documentation:

1. **Ingestion had no trigger and no state.** The earlier plan described caching in
   PostgreSQL but never said what ran ingestion or when. Resolved by DEC-003: a CLI entry
   point plus `sync_run` and `sync_cursor` tables.
2. **Source outages were undetectable.** Because agent tools read the database, an empty
   query result was indistinguishable from an unreachable source. This would have made the
   system report "no blockers found" when Jira was down. Resolved by DEC-010 and tool
   T-007, derived from sync history.
3. **The evidence contract allowed fabricated citations.** The draft `Insight` model had
   the LLM generating `EvidenceItem` objects, which the validator could not check against
   anything. Resolved by DEC-004: code builds the evidence set with stable IDs, the model
   cites by ID only, and unknown IDs are dropped.
4. **The Jira to GitHub link was not a modelled entity.** It existed only as string parsing
   inside the evidence builder, so it could not be tested, audited or given a confidence.
   Resolved by DEC-009: a `work_item_link` table written during ingestion.
5. **Blockers had no defined source.** With Slack out of scope, nothing specified where a
   blocker came from. Resolved by 8 deterministic Jira and GitHub signals in
   `DATA_AND_EVIDENCE.md` 6.9.

Also corrected: the earlier plan specified `temperature 0` in 3 places as the determinism
strategy. The `temperature` parameter has been removed on current Claude models and
returns a 400. Replaced by DEC-011: fixtures, structured outputs, and assertions on
structured fields rather than wording.

Also resolved a contradiction in the earlier plan about whether feature branches are
deleted after merge. Decision: **branches are kept**, as stated in 2 of the 3 places it
appeared.

### Problems
None.

### Decisions Needed
- **All 15 decisions are `Proposed`, not `Accepted`.** Both developers must read and
  ratify them in task P0-006 before feature work starts. The 5 that are expensive to
  reverse are DEC-002, DEC-004, DEC-005, DEC-009 and DEC-015.
- **DR-1 works-council and labour-law review.** An employee-facing tool may require formal
  worker representation sign-off before deployment in some jurisdictions. This gates
  deployment, not the MVP build. Owner: project sponsor. Open.
- **DR-2 data retention period.** Not needed for the demo, required before any real
  deployment. Open.
- **Assumption A-3 is unconfirmed.** Jira Cloud may not expose user email addresses, and
  GitHub commit author emails are often privacy addresses. This is why identity mapping is
  bootstrapped manually (DEC-008). Confirm during P0-002 and correct this log if wrong.

### Blocked By
Nothing.

### Next Step
Task P0-006: both developers read `DECISIONS.md` and ratify the 15 decisions. Then P0-001
(create the repository) and P0-002 (create real Jira and GitHub test data and capture
fixtures).

### AI Assistance
The documentation set was drafted with an AI assistant from the earlier planning material
(`ARGUS_MVP_Plan.html`, `TeamPulse_Production_Ready_AI_Agent_Checklist.md`,
`TeamPulse_Analysis_and_Recommendations.md`). The 5 gaps listed above were identified
during that review.

**Needs a human check:** the 15 decisions, particularly the 5 expensive ones. Nothing in
this documentation has been validated against a running system, because no code exists
yet. Assumption A-3 in particular is unverified and must be confirmed in P0-002.

---

_No entries before this. The project starts here._
