# ARGUS Architecture Decision Records

Decisions that shape the system and are expensive to reverse. Ordinary implementation
choices do not belong here.

**Status values:** `Proposed`, `Accepted`, `Superseded by DEC-nnn`, `Rejected`.

**Rule:** if a task appears to require breaking an Accepted decision, do not work around
it. Raise it as a Decision Required entry in `WORKLOG.md` and add a new DEC record.

All decisions below are `Proposed` until both developers ratify them in task P0-006.

| ID | Title | Status |
|---|---|---|
| DEC-001 | Read-only MVP, no write tools | Proposed |
| DEC-002 | Agent tools read the database, never external APIs | Proposed |
| DEC-003 | Ingestion is an explicitly triggered write path with recorded state | Proposed |
| DEC-004 | Evidence has stable IDs and the model cites by ID | Proposed |
| DEC-005 | Validation is deterministic code, 1 LLM call per run | Proposed |
| DEC-006 | Confidence is rule-based HIGH / MEDIUM / LOW / UNKNOWN | Proposed |
| DEC-007 | Fixed question types, no free-text input in the MVP | Proposed |
| DEC-008 | Identity mapping is bootstrapped manually | Proposed |
| DEC-009 | Jira to GitHub correlation is a stored table | Proposed |
| DEC-010 | Source health is derived from sync history | Proposed |
| DEC-011 | Determinism comes from fixtures and schemas, not temperature | Proposed |
| DEC-012 | Demo data is seeded through the real ingestion path | Proposed |
| DEC-013 | PostgreSQL only, no Redis, queue or vector database | Proposed |
| DEC-014 | Slack and calendar are deferred | Proposed |
| DEC-015 | The developer boundary is the database schema | Proposed |

---

## DEC-001: Read-only MVP, no write tools

Date: 2026-09-13
Status: Proposed
Owner: Both

### Context

ARGUS reads text written by other people: pull request descriptions, Jira comments, commit
messages. Any of that text can contain instructions aimed at the model. Large language
models do not reliably ignore injected instructions just because a prompt tells them to.

The question is how much damage a successful injection can do.

### Options considered

1. Allow write tools (post a Slack summary, comment on a ticket) and defend with prompt
   instructions and delimiters.
2. Allow write tools behind a human approval gate.
3. Allow no write tools at all in the MVP.

### Decision

Option 3. ARGUS is read-only for the entire MVP. No tool writes to any external system.
The LLM is given no tools whatsoever.

### Reason

Prompt-based defences are advisory. Architectural defences are absolute. With no write
capability anywhere in the system, the worst outcome of a successful injection is 1 wrong
answer shown to a user who was already authorized to see the underlying data. No data can
be exfiltrated and no action can be taken.

Option 2 requires approval gates, risk classification and an audit trail for consequential
actions. That is a substantial subsystem, and it is dead weight while there is nothing
consequential to approve.

### Consequences

- Human-in-the-loop machinery is not needed in the MVP. Deferred to Stage 4.
- Integration tokens are read-only scoped. No write endpoint may appear in the codebase.
- Prompt injection is contained rather than prevented, which is the honest framing.
- Adding any write tool later requires a new decision record and the approval machinery.

### Related documents

FR-029, NFR-007, NFR-008, `AI_BEHAVIOR.md` 5.6, `AI_BEHAVIOR.md` 5.11, `AGENT_TOOLS.md`.

---

## DEC-002: Agent tools read the database, never external APIs

Date: 2026-09-13
Status: Proposed
Owner: Both

### Context

The original plan placed `tools/` next to `integrations/` and gave both to 1 developer,
which implied that agent tools call GitHub and Jira directly. The architecture diagram
showed the tool layer reading PostgreSQL. Both cannot be true.

If tools call external APIs at request time, a lead's question blocks on 2 external
services, latency becomes 5 to 60 seconds, rate limits are consumed by ordinary browsing,
and no test or evaluation is reproducible.

### Options considered

1. Tools call GitHub and Jira APIs on demand. Always fresh, slow, rate-limited, untestable.
2. Tools call APIs but cache aggressively. Adds cache invalidation complexity and still
   couples the request path to an external service.
3. Tools read PostgreSQL only. A separate ingestion path writes it.

### Decision

Option 3. **Agent-facing tools MUST NOT make external API calls.** Every module under
`app/tools/` reads PostgreSQL. A test asserts that no HTTP client is imported there.

The system has 2 separate paths:
- **Write path:** `app/integrations/` and `app/sync.py`. Makes network calls. Triggered
  explicitly, never by a web request.
- **Read path:** `app/tools/`. Reads PostgreSQL. Never makes a network call.

### Reason

The read path becomes fast, offline, fully reproducible and trivially testable. A slow or
failing external API cannot break a demo. Evaluation runs against fixed database state, so
results are comparable across runs.

The cost is staleness, which is not hidden: it is measured by DEC-010 and shown to the
user.

### Consequences

- `retrieved_at` is a column on the row set by the ingester, not a property of the call.
- Freshness must be surfaced in the UI, otherwise the staleness cost is invisible.
- Source health must be derivable from sync history, which forces DEC-010.
- Ownership shifts: `app/tools/` belongs to Developer 2, not Developer 1. See DEC-015.

### Related documents

FR-013, NFR-015, DEC-003, DEC-010, `ARCHITECTURE.md` section 4, `AGENT_TOOLS.md`.

---

## DEC-003: Ingestion is an explicitly triggered write path with recorded state

Date: 2026-09-13
Status: Proposed
Owner: Developer 1

### Context

DEC-002 requires that something populates the database. The original plan deferred Redis,
a job queue and a scheduler, correctly for an MVP, but did not replace them with anything.
Nothing said what runs ingestion, when, or how a partial run recovers.

### Options considered

1. Trigger ingestion from a web request when data looks stale. Couples the request path to
   external APIs, which contradicts DEC-002.
2. Add a background scheduler and a job queue now.
3. A command-line entry point, run manually or by an external cron, with run state
   recorded in the database.

### Decision

Option 3. `python -m app.sync --source <github|jira> --team <id>` is the single ingestion
entry point. It is idempotent and safe to re-run. Every attempt writes a `sync_run` row.
Progress is recorded in `sync_cursor` so a re-run resumes rather than refetching.

A scheduler is deferred to Stage 2. For the MVP, sync is run manually or from cron.

### Reason

A CLI plus 2 small tables gives observable, resumable ingestion with no new infrastructure.
It satisfies DEC-002 and provides the raw material for DEC-010. A queue and scheduler are
real work that buys nothing while the team is 2 people running a local demo.

### Consequences

- The MVP has no automatic refresh. Data is as fresh as the last manual or cron-driven run.
  This is acceptable only because freshness is visible to the user.
- `sync_run` and `sync_cursor` are required tables in the first migration.
- Adding a scheduler later changes the trigger, not the ingestion code.

### Related documents

FR-008, FR-009, NFR-003, NFR-015, DEC-002, DEC-010, `DATA_AND_EVIDENCE.md` 6.2.

---

## DEC-004: Evidence has stable IDs and the model cites by ID

Date: 2026-09-13
Status: Proposed
Owner: Developer 2

### Context

The draft response contract had the shape:

```python
class Insight(BaseModel):
    claim: str
    evidence: list[EvidenceItem]   # generated by the model
```

If the model produces the evidence objects, it can produce evidence that does not exist.
The validation stage then has nothing authoritative to compare against, because the only
field it could check was a human-readable string.

This is the exact shape that produces confident, well-formatted, fabricated citations.

### Options considered

1. Model generates evidence objects. Validator fuzzy-matches them against real records.
   Fragile, and fuzzy matching fails open.
2. Model generates claims only, with no evidence. Loses the connection between a claim and
   the records that support it.
3. Application code builds the evidence set first and assigns each item a stable ID. The
   model receives the set and cites items by ID only.

### Decision

Option 3. Stage S3 builds the complete evidence set before any model call and assigns IDs
`ev_1`, `ev_2`, and so on, unique within the run. The model returns
`evidence_ids: list[str]`. It cannot mint IDs, because any ID not in the provided set is
rejected by code.

Application code resolves IDs back to evidence objects for the response. The evidence a
user sees is never copied from model output.

### Reason

This converts hallucination from something discouraged by a prompt into something the
system structurally rejects. The check is a set membership test: cheap, exact, and
impossible to fail open.

It also makes the validator writable in ordinary Python, which enables DEC-005.

### Consequences

- The evidence `summary` field is generated by application code, not by the model.
- `agent_run.evidence_set` stores the exact set given to the model, which makes every run
  replayable.
- Rejected claims are recorded in `agent_run.dropped_claims`, which is direct evidence
  that the defence is working.
- The prompt must present evidence in a stable, ID-labelled format.

### Related documents

FR-015, FR-017, FR-024, NFR-016, DEC-005, `AI_BEHAVIOR.md` 5.3, `AI_BEHAVIOR.md` 5.5,
`DATA_AND_EVIDENCE.md` 6.5.

---

## DEC-005: Validation is deterministic code, 1 LLM call per run

Date: 2026-09-13
Status: Proposed
Owner: Developer 2

### Context

The source material described the validation stage inconsistently: as an LLM call in one
diagram, as code and rules in a table, and as part of a 2-call design in a companion
document. A 7-stage design where each stage is a model call multiplies cost, latency and
failure surface for no gain.

### Options considered

1. 7 LLM stages as originally diagrammed.
2. 2 LLM calls: 1 to reason, 1 to check the reasoning against the evidence.
3. 1 LLM call to reason, with validation entirely in application code.

### Decision

Option 3. Exactly 1 LLM call per agent run, in stage S4. Stages S1, S2, S3, S5 and S6 are
deterministic Python. Validation in S5 enforces 4 rules in code:

1. Every cited evidence ID exists in the run's evidence set.
2. A claim classified `fact` cites at least 1 item from the authoritative source for that
   fact type.
3. A claim classified `inference` cites 2 or more evidence items.
4. Confidence is computed by code from the resolved evidence.

### Reason

A second model call to check the first is weaker than a set membership test, costs twice
as much, doubles the latency, and adds a second thing that can hallucinate. DEC-004 makes
code-based validation possible, so the model call buys nothing.

Planning, retrieval, correlation, conflict detection, blocker detection and response
formatting are all ordinary code. The only task that genuinely needs a language model is
turning correlated evidence into a readable narrative claim.

### Consequences

- Cost is roughly 0.04 USD per run rather than 0.08 USD or more.
- The validator is unit-testable without any model call.
- Conflicts, blockers, risks and confidence are all produced by code, which means the
  evaluation suite can test them independently of the model.
- The honest framing, which should be stated in the README: the LLM's job is the narrative
  and the phrasing. The value of the product is the evidence graph. This is a strength.

### Related documents

FR-016, FR-017, FR-018, FR-019, FR-020, NFR-030, DEC-004, DEC-006,
`AGENT_ARCHITECTURE.md` 3.4, `AGENT_ARCHITECTURE.md` 3.11.

---

## DEC-006: Confidence is rule-based HIGH / MEDIUM / LOW / UNKNOWN

Date: 2026-09-13
Status: Proposed
Owner: Developer 2

### Context

A numeric confidence such as 0.91 implies a calibrated probability. Calibration requires
labelled ground truth, which the project will not have at launch. A model asked for its
own confidence produces a number that looks precise and is not.

### Options considered

1. Numeric confidence from the model.
2. Numeric confidence computed by code, for example a weighted score from 0 to 1.
3. Ordinal confidence computed by code from countable facts.

### Decision

Option 3. Confidence is `HIGH`, `MEDIUM`, `LOW` or `UNKNOWN`, assigned by application code
from the resolved evidence. Model-supplied confidence is ignored if present.

Base rules, with the exact thresholds in `AI_BEHAVIOR.md` 5.4:
- HIGH: 3 or more evidence items across 2 or more sources, all fresh, at least 1 from the
  authoritative source, no unresolved conflict.
- MEDIUM: 2 or more evidence items, or 1 item from the authoritative source.
- LOW: exactly 1 non-authoritative evidence item, or all evidence is stale.
- UNKNOWN: no supporting evidence, or a source required by the question is unavailable.

Modifiers: a stale source drops 1 level. An unresolved conflict drops 1 level. An
unavailable required source forces UNKNOWN regardless of other evidence.

### Reason

Ordinal levels driven by countable facts are honest, explainable without reading model
output, and unit-testable. A numeric score is a later decision that requires labelled
evaluation data first.

### Consequences

- The UI shows a badge, never a percentage.
- Confidence rules are pure functions and are tested independently of the LLM.
- Moving to numeric confidence later requires labelled ground truth, and is Stage 3.

### Related documents

FR-018, NFR-018, DEC-005, `AI_BEHAVIOR.md` 5.4, `TESTING_AND_EVALUATION.md` 11.3.

---

## DEC-007: Fixed question types, no free-text input in the MVP

Date: 2026-09-13
Status: Proposed
Owner: Both

### Context

The architecture includes a planning stage that decides what data a question needs, but
the MVP UI is 2 pages with no text input. If there is no text box, the planner has nothing
to plan from. If there is a text box, the system needs intent classification, out-of-scope
handling, and a defence against questions like "who should I fire".

### Options considered

1. A free-text question box with LLM intent classification.
2. A free-text box restricted by a classifier to 3 intents.
3. 3 fixed question types selected in the UI.

### Decision

Option 3. The MVP supports exactly 3 question types:

| ID | Question |
|---|---|
| `current_work` | What is this person working on? |
| `blockers` | Is anything blocking this person? |
| `risks` | What is at risk this week? |

The API rejects any other value with a 422. The planner becomes a fixed mapping from
question type to required sources and time window.

### Reason

It removes intent classification, out-of-scope handling and the largest untrusted input
surface in the product, at the cost of flexibility the MVP does not need. The planner
stays deterministic and testable. A lead asking a standup question does not need free
text; 3 buttons are faster.

### Consequences

- The planner is a dictionary, not a model call.
- There is no user-supplied text anywhere in the prompt, which materially shrinks the
  injection surface. The only untrusted text is retrieved content.
- Adding free text later is a Stage 2 feature and needs its own evaluation scenarios.

### Related documents

FR-014, FR-029, `AGENT_ARCHITECTURE.md` 3.4 stage S1, `AI_BEHAVIOR.md` 5.6.

---

## DEC-008: Identity mapping is bootstrapped manually

Date: 2026-09-13
Status: Proposed
Owner: Developer 1

### Context

The rule "never attribute work from a display name alone, require at least 1 verified
link" is correct, but the MVP uses personal access tokens rather than OAuth, so there is
no OAuth-verified email anywhere in the system. As written, the rule could not be
satisfied and the identity task had no starting point.

2 practical details make automatic matching worse than expected, both to be confirmed in
task P0-002:
- GitHub commit author emails are frequently the privacy address
  `NNNN+username@users.noreply.github.com` rather than a company address.
- Jira Cloud hides user email addresses by default, so `emailAddress` is often absent from
  API responses.

### Options considered

1. Match on display name. Rejected outright: names collide and change, and a wrong
   attribution is worse than no answer.
2. Match on email automatically. Low coverage for the reasons above, and silently wrong
   when a privacy address happens to collide.
3. Manual mapping file as the verified source, with automatic matching allowed only as an
   unconfirmed proposal.

### Decision

Option 3.

- Verified mappings come from `seed/identity_map.yml`, committed to the repository and
  loaded by the seeder, with `match_method = manual`.
- The resolver may propose mappings from an exact email match or an exact handle match.
  These are stored with `match_method = inferred` and **MUST NOT be used for attribution**
  until a human confirms them.
- Anything unmatched goes to `unmatched_entity` with an occurrence count and is surfaced
  in the UI. The underlying record is still ingested, with a null actor.

### Reason

It satisfies the correctness rule with the credentials the MVP actually has. It is honest
about coverage: unmapped work is visibly unmapped rather than silently attributed or
silently dropped.

### Consequences

- Onboarding a team requires a human to write a mapping file once. Acceptable at MVP scale.
- Some ingested activity will have no actor. The UI must handle this.
- OAuth-verified mapping is a Stage 2 improvement, not a rewrite.

### Related documents

FR-002, FR-003, `DATA_AND_EVIDENCE.md` 6.9, `PROJECT_REQUIREMENTS.md` A-3, scenario S-6.

---

## DEC-009: Jira to GitHub correlation is a stored table

Date: 2026-09-13
Status: Proposed
Owner: Developer 1

### Context

Connecting `AUTH-245` to the branch `feature/AUTH-245-refresh-token`, to pull request 182,
to its commits, is the core of the product. In the draft design this connection was
derived by string parsing inside the evidence builder on every request. It was not stored,
not auditable, could not be tested in isolation, and could not carry a confidence.

### Options considered

1. Derive links at request time by parsing strings. Fast to write, invisible, untestable
   in isolation.
2. Derive at request time but cache the result. Adds a cache with no schema.
3. Compute links during ingestion and store them in `work_item_link` with the derivation
   method and a confidence.

### Decision

Option 3. A `work_item_link` table stores the work item, the target type and ID, the
`link_method`, a confidence and a creation timestamp, unique per
(work_item, target_type, target_id).

Method reliability ranking:

| Method | Confidence |
|---|---|
| `jira_remote_link` (a real Jira link object) | HIGH |
| `branch_name` (ticket ID parsed from the branch) | HIGH |
| `pr_title` | MEDIUM |
| `pr_body` | MEDIUM |
| `commit_message` | MEDIUM |

A link MUST NOT be created from timing or authorship alone.

### Reason

The link becomes a first-class, inspectable fact with its own tests and its own
confidence, which feeds directly into DEC-006. It also creates a clean seam between the
2 developers: Developer 1 produces links, Developer 2 consumes them.

### Consequences

- Correlation runs during ingestion, so a new naming convention requires a re-sync to pick
  up links retroactively.
- Unlinked pull requests are visible as unlinked rather than silently guessed at.
- The evidence builder reads links instead of parsing strings, which simplifies stage S3.

### Related documents

FR-011, DEC-006, `DATA_AND_EVIDENCE.md` 6.4, scenario S-8.

---

## DEC-010: Source health is derived from sync history

Date: 2026-09-13
Status: Proposed
Owner: Developer 1

### Context

DEC-002 means the agent reads the database. A database query returns rows whether or not
the source that filled it is currently reachable. Without something extra, ARGUS cannot
tell the difference between "Jira reports no blockers" and "Jira has been unreachable for
2 days", and it would report the second as the first. That is the single most damaging
failure mode this product has.

### Options considered

1. Probe the source with a lightweight health call at request time. Violates DEC-002 and
   reintroduces a network dependency in the request path.
2. Store a health flag updated by ingestion. Works, but loses the history.
3. Derive health from the `sync_run` history at query time.

### Decision

Option 3. A function `source_health(source, team)` returns the last successful sync time,
the last attempt time, the last error type, and a state:

| State | Condition |
|---|---|
| `fresh` | Last successful sync within `FRESHNESS_WINDOW_HOURS` |
| `stale` | Last successful sync older than that, but data exists |
| `unavailable` | Last attempt failed, or no successful sync has ever occurred |

Consequences for the answer are mandatory, not advisory:
- Evidence from a `stale` source drops confidence 1 level.
- If a source required by the question is `unavailable`, the answer is UNKNOWN with the
  reason stated. A negative conclusion that depends on that source MUST NOT be produced.

### Reason

It needs no new infrastructure, keeps the request path offline, and preserves history for
debugging. It is about 20 lines of code and it is the behaviour that most clearly
separates this product from a naive dashboard.

### Consequences

- `sync_run` becomes load-bearing, not just an audit table.
- Every page showing member data must show per-source freshness.
- Evaluation scenario EV-04 depends entirely on this decision.

### Related documents

FR-010, FR-023, NFR-005, NFR-020, DEC-003, DEC-006, scenarios S-4 and S-7,
`TESTING_AND_EVALUATION.md` EV-04.

---

## DEC-011: Determinism comes from fixtures and schemas, not temperature

Date: 2026-09-13
Status: Proposed
Owner: Developer 2

### Context

The draft plan specified `temperature 0` in 3 places as the mechanism for reproducible
evaluation runs. On the current Claude models the `temperature` parameter has been
removed, and sending it returns a 400 error. The determinism strategy needed replacing,
not just the parameter.

### Options considered

1. Use an older model that still accepts `temperature`. Trades capability for a parameter
   that never fully guaranteed determinism anyway.
2. Accept variable output and assert loosely on the text.
3. Make the inputs fixed and assert only on structured fields.

### Decision

Option 3. Reproducibility comes from 3 mechanisms together:

1. **Recorded fixtures.** Evaluation runs against a fixed database state seeded from
   `seed/fixtures/`, so the evidence set given to the model is byte-identical each run.
2. **Structured output.** The reasoning call uses `output_config.format` with a strict
   schema, so the response shape cannot drift.
3. **Structured assertions.** Tests assert on `classification`, `confidence`, the set of
   cited evidence IDs, and the presence or absence of conflicts. Tests MUST NOT assert on
   the wording of a sentence.

Do not send a `temperature` parameter. Do not use assistant prefill; it is also removed on
current models.

### Reason

Wording was never a stable thing to test. The properties that matter are structural, and
DEC-004 and DEC-005 make all of them structural. Fixing the inputs and asserting on
structure gives stronger guarantees than temperature ever did.

### Consequences

- An evaluation failure means a real behaviour change, not a rephrasing.
- The evaluation suite depends on fixtures, which makes DEC-012 more valuable.
- Model version is recorded in `agent_run.model` so a change in behaviour can be traced to
  a model change.

### Related documents

FR-016, `TESTING_AND_EVALUATION.md` 11.4, `TESTING_AND_EVALUATION.md` 11.6, DEC-012.

---

## DEC-012: Demo data is seeded through the real ingestion path

Date: 2026-09-13
Status: Proposed
Owner: Developer 1

### Context

A seed script that inserts rows directly creates a second write path into the same tables.
Seeded data drifts from what the real ingester produces, the ingester is never exercised
in the demo, and bugs in normalization stay hidden until a real sync is run.

### Options considered

1. Seed by inserting canonical rows directly.
2. Seed by calling the real APIs during setup. Requires network and credentials, and is
   not reproducible.
3. Seed by feeding recorded API payloads through the real ingestion code.

### Decision

Option 3. `seed/fixtures/` holds real GitHub and Jira API responses captured in task
P0-002. `seed_demo.py` feeds them through the real ingestion functions with the HTTP layer
replaced by a fixture reader. No network call is made.

The same fixtures are reused by the unit tests and the evaluation suite.

### Reason

1 write path. The demo exercises the real normalization, correlation and identity code
every time it loads. It is fully offline and identical on both machines. 1 artefact serves
3 purposes: demo, tests and evaluation.

### Consequences

- Capturing realistic fixtures becomes a prerequisite task, P0-002, done before feature
  code.
- The ingestion code must accept an injectable transport so fixtures can be substituted.
- Adding a demo scenario means adding a fixture, not writing insert statements.

### Related documents

FR-032, DEC-011, `TESTING_AND_EVALUATION.md` 11.4, task P0-002, task P2-009.

---

## DEC-013: PostgreSQL only, no Redis, queue or vector database

Date: 2026-09-13
Status: Proposed
Owner: Both

### Context

The production-readiness guidance lists Redis for caching and rate limiting, a job queue
for background work, and an optional vector index for semantic search. Each is a service
to run, configure, monitor and debug.

### Options considered

1. Add Redis, a queue and a vector index now, matching the eventual production shape.
2. Add Redis only, for caching and rate limiting.
3. PostgreSQL only for the MVP.

### Decision

Option 3. The MVP runs PostgreSQL and the application container, nothing else.

- Caching: the insight cache is a table keyed by an evidence hash (FR-031).
- Rate limiting: ingestion is single-process and sequential, so a token bucket in process
  memory is sufficient.
- Background work: ingestion is a CLI command (DEC-003).
- Semantic search: not needed. Nearly every ARGUS query is structured, filtered by person,
  work item and time window. If a genuine need appears, use `pgvector` inside the
  PostgreSQL already running, not a separate service.

### Reason

Every deferred service is 1 fewer thing that can break during a demo and 1 fewer thing to
learn. None of them solve a problem the MVP actually has at this scale.

### Consequences

- `docker compose up` starts 2 containers.
- Ingestion cannot run in parallel across sources without changes. Acceptable at this scale.
- Adding Redis later is straightforward because the interfaces it would sit behind
  (cache, rate limiter) are already isolated functions.

### Related documents

FR-031, `ARCHITECTURE.md` section 11, `README.md` section 7.

---

## DEC-014: Slack and calendar are deferred

Date: 2026-09-13
Status: Proposed
Owner: Both

### Context

Blocker detection from Slack is attractive: people say "I am blocked on X" in chat. It is
also the highest-risk and least reliable source available.

### Options considered

1. Include Slack in the MVP for blocker detection.
2. Include Slack read-only for explicitly opted-in channels.
3. Defer Slack and calendar entirely.

### Decision

Option 3. Neither Slack nor calendar is in the MVP. Blockers are detected from the
deterministic Jira and GitHub signals defined in `DATA_AND_EVIDENCE.md`.

### Reason

3 reasons, in order of weight:

1. **Legal.** Reading semi-private team conversations is the point at which an engineering
   tool becomes an employee-monitoring tool. In some jurisdictions this requires formal
   worker representation sign-off before deployment. That review gates deployment, not the
   build, and it should not gate the MVP. See DR-1.
2. **Signal quality.** Chat is noisy, sarcastic, and easy to misread. "I am blocked" in a
   message from 3 weeks ago is not a current blocker.
3. **Scope.** Jira and GitHub already carry 8 deterministic blocker signals, listed in
   `DATA_AND_EVIDENCE.md`. Those are reliable and need no inference over free text.

When Slack is eventually added it MUST be opt-in per channel, never workspace-wide.

### Consequences

- Blocker coverage is limited to what Jira and GitHub express. A purely verbal blocker is
  not detected, and the product should not imply otherwise.
- Calendar-based context, such as someone being in meetings all week, is unavailable.
- The legal review (DR-1) is raised early rather than discovered late.

### Related documents

FR-020, DR-1, `DATA_AND_EVIDENCE.md` 6.1, `PROJECT_REQUIREMENTS.md` 2.8.

---

## DEC-015: The developer boundary is the database schema

Date: 2026-09-13
Status: Proposed
Owner: Both

### Context

2 developers working in 1 repository need a boundary that minimizes merge conflicts and
lets each work without waiting on the other. The original split put `tools/` with the
integrations developer. Once DEC-002 established that tools read PostgreSQL, those tools
became database queries whose only consumer is the agent, which sits with the other
developer.

### Options considered

1. Keep `tools/` with Developer 1, alongside the integrations.
2. Split `tools/` between both developers by source.
3. Move `tools/` to Developer 2, so the handoff is the database schema alone.

### Decision

Option 3.

| Developer 1 (write path) | Developer 2 (read path) |
|---|---|
| `app/integrations/` | `app/tools/` |
| `app/sync.py` | `app/agent/` |
| identity resolution, unmatched queue | `app/web/` |
| `work_item_link` creation | `work_item_link` consumption |
| `sync_run`, `sync_cursor`, source health | `agent_run`, insight cache |
| `seed/` and fixture capture | fixture consumption |

Shared and changed only with a heads-up message plus a `WORKLOG.md` note: `app/models/`,
`app/schemas/`, `app/config.py`, `app/db.py`, `migrations/`, CI, Docker files.

Only 1 person creates an Alembic migration at a time, announced in advance. CI enforces a
single Alembic head.

### Reason

The handoff shrinks to exactly 1 artefact: the database schema, frozen in Phase 1. Neither
developer waits on the other's function signatures. Developer 2 builds against fixture-
seeded data from the start, so integration work never blocks agent work.

### Consequences

- The schema must be agreed carefully in Phase 1, because both sides depend on it.
- Developer 2 writes SQL queries, not just agent logic.
- Developer 1 owns correctness of what is in the database; Developer 2 owns correctness of
  what is concluded from it.
- Review policy: Developer 2's pull requests need Developer 1's approval. Developer 1 may
  merge their own work.

### Related documents

DEC-002, DEC-009, `TASKS.md` -> Developer Ownership, `ARCHITECTURE.md` section 12.
