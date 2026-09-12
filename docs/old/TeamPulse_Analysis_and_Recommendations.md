# TeamPulse — Complete Analysis and Engineering Recommendations

Companion review of `TeamPulse_Production_Ready_AI_Agent_Checklist.md`.

This document covers: what to update, the loopholes, the failure points, the weak
points, the best choices, and a concrete build order to make TeamPulse an
industry-ready, valuable product.

---

## 0. Overall verdict

The checklist is strong on breadth. It covers security, privacy, evidence
framing, reliability, and operations, and the core product boundary ("evidence,
not surveillance") is the right spine. Keep that boundary.

Breadth is not where TeamPulse succeeds or fails. The checklist is weak exactly
where the product is hard, and it compresses several genuinely difficult
subsystems into a single bullet point. The rest of this document adds the depth,
the reality checks, the prioritization, and the concrete technology choices that
the checklist leaves out.

Rating by area:

| Area | Checklist coverage | Real-world readiness |
|---|---|---|
| Security framing | Strong | Good |
| Privacy framing | Strong | Good |
| Evidence and confidence model | Good in words | Weak in mechanism |
| Identity resolution | Almost absent | Critical gap |
| Ingestion and rate limits | Vague | Critical gap |
| Evaluation | Listed | Under-planned (needs labeled data) |
| Cost model | Listed | Missing unit economics |
| Deletion and legal | Partial | Missing deletion pipeline |
| Agent decomposition | Over-specified | Over-engineered for MVP |

---

## 1. The biggest loophole: identity resolution

This is the single largest source of wrong answers, and the checklist gives it
2 lines ("use stable identifiers, do not rely on names").

### The problem

One human is `keshan-dev` on GitHub, `accountId 5f3a...` on Jira, `U04AB` on
Slack, and `keshan@dynarq.com` on calendar. None of these join automatically.
Display names collide, change, and differ across every tool.

If identity mapping is wrong, every downstream insight is confidently attributed
to the wrong person. That is worse than returning no answer, because a lead acts
on it.

### What must be built (and the checklist omits)

- An explicit **identity graph**: a table mapping every external ID to one
  internal `User`, with a `match_method` (verified / inferred / manual) and a
  confidence value per link.
- An **unmatched-entity queue**. When a commit author, PR reviewer, or Slack
  user cannot be mapped to a known person, it goes to a review queue. It is never
  silently dropped and never guessed.
- A **manual override UI** so a lead confirms a mapping once and it sticks.
- A hard rule: **never attribute work from display name alone.** Require at least
  one verified link (OAuth-confirmed email, or admin-confirmed mapping) before
  attributing activity to a person.

Treat identity resolution as a Phase 1 subsystem with its own schema, its own
tests, and its own review queue. It is not a detail.

### Suggested schema sketch

```text
identity_link
  id
  user_id            -> internal User
  integration        -> github | jira | slack | calendar
  external_id        -> stable external identifier
  external_handle    -> display handle at time of mapping
  match_method       -> verified | inferred | manual
  confidence         -> HIGH | MEDIUM | LOW
  verified_at
  created_at
  UNIQUE(integration, external_id)
```

---

## 2. Ingestion strategy is undefined

The checklist lists webhooks (section 6.3) and pull tools (section 3.1)
separately but never resolves how data actually enters the system. This decides
your cost, latency, and whether external APIs throttle you.

### The 3 options

1. **On-demand pull** (fetch when a lead asks). Simple and always fresh, but slow
   per query and burns rate limits fast.
2. **Scheduled polling.** Predictable but stale between polls and wasteful.
3. **Webhook-driven ingestion plus cache.** The correct end state, and the most
   work.

### Recommendation

Webhooks for freshness, plus a nightly reconciliation poll to catch missed
events, plus on-demand pull only to fill gaps. Cache normalized data in Postgres.
Each webhook invalidates the relevant cache rows. The checklist mentions caching
(section 28) and webhooks (section 6.3) as separate topics; they are one system
and must be designed together.

### Missing entirely from the checklist

- **Cold-start backfill.** Onboarding a team requires 30 to 90 days of history.
  Backfilling Jira and GitHub across their rate limits is a multi-hour job that
  needs checkpointing and resumability. Plan it as real work.
- **Rate-limit budgeting.** GitHub allows roughly 5000 requests per hour per
  installation. Jira Cloud and Slack throttle aggressively and tier by plan. At
  team scale you need a per-integration token-bucket limiter feeding a shared
  work queue, not per-request retries bolted on afterward.
- **Cache and webhook coupling.** State the freshness contract explicitly:
  `source_updated_at`, `retrieved_at`, `normalized_at` on every row, surfaced in
  the UI when confidence depends on it.

---

## 3. Failure points that will bite in production

### 3.1 Prompt injection defense is under-enforced

The checklist states the right words ("label external text as untrusted,"
"separate instructions from evidence") but that alone does not hold. LLMs do not
reliably respect delimiters under adversarial pressure.

The defense that actually works is architectural, not prompt-based:

> The LLM stage that reads untrusted retrieved content must have **zero write
> tools** in its context.

Make data exfiltration or unauthorized action impossible by construction, not
requested politely in a system prompt. If Phase 1 is read-only (see section 6),
successful injection can at worst leak data the user is already authorized to
see, and can never take an action.

### 3.2 Confidence scoring is circular

Section 12 says use "a calibrated numeric score if you have evaluation evidence."
You cannot calibrate without labeled ground truth, which you will not have at
launch. Do not ship numeric confidence early.

Start with rule-based `HIGH / MEDIUM / LOW` driven by countable facts:

```text
HIGH   -> 3+ independent sources agree, recent, direct evidence
MEDIUM -> 2 sources, or 1 strong direct source, reasonably recent
LOW    -> 1 weak or indirect source, or stale data
UNKNOWN-> no supporting evidence found
```

Move to a numeric, calibrated score only after you have labeled evaluation data
to calibrate against.

### 3.3 The evaluation set needs ground truth you have to create

Section 22 lists 12 excellent scenarios, but blocker precision and recall require
a human to label the real blockers for each case. That labeling is a staffed
operation, not a free byproduct. It is the most expensive part of evaluation and
the checklist treats it as trivial. Budget time and a person for it.

### 3.4 Deduplication depends on the identity graph

The same work appears as a GitHub event, a Jira transition, and a Slack message
with no shared key. Deduplication (section 11.4) is impossible until the
entity-correlation graph exists. It is downstream of section 1, not independent.

### 3.5 Slack is the highest-risk, lowest-reliability source

Blocker detection from Slack means reading semi-private conversations. In several
jurisdictions (EU works councils in particular) that alone can block deployment.
The signal is also noisy and easy to misread. Make Slack opt-in per channel and
push it out of the MVP.

---

## 4. Weak design choices to reconsider

### 4.1 "Current work inference" is the riskiest feature for the least value

It is inherently guessy, closest to surveillance, and the hardest thing to
evaluate. Meanwhile "assigned issue + status + open PR" already answers most of
what a lead asks, deterministically, with no inference at all. Ship the
deterministic version first. Add inference later, behind a feature flag, if it
proves its worth.

### 4.2 The 7-stage agent decomposition is over-engineered for the MVP

Section 3.2 lists Planner, Collector, Context, Reasoning, Validation, Response,
and Action as stages, and the diagrams imply each is an LLM call. That multiplies
cost, latency, and failure surface.

Most stages should be **deterministic Python, not LLM calls**. Realistically the
MVP needs 2 LLM calls:

1. One reasoning call over already-structured evidence.
2. One validation call that checks claims against evidence.

Planning, retrieval, correlation, and response formatting are ordinary code. The
checklist actually says this in sections 3.2 and 14.2, then contradicts it in the
architecture diagrams. Follow 14.2.

### 4.3 Vector DB is premature

Section 9 lists it as optional, but many teams will build it too early. Nearly
every TeamPulse query is structured (recent PRs, assigned issues within a time
window). You do not need semantic search at MVP. When you do, use `pgvector`
inside the Postgres you already run rather than adding a separate service.

### 4.4 Human-in-the-loop machinery is premature for a read-only MVP

Sections 17 and 18 describe approval gates and autonomous-action risk classes. If
the MVP has no write tools, there are no consequential actions, so most of that
infrastructure is dead weight in Phase 1. Build it when you build write tools.

---

## 5. Gaps the checklist does not mention at all

### 5.1 Employee-departure and deletion pipeline

When a person leaves or objects, you must purge their data and revoke their
identity mappings. Section 8.4 asks retention questions but there is no deletion
pipeline. Right-to-erasure plus employee-data rules make this mandatory. Design a
`purge_user(user_id)` flow that removes evidence, mappings, cached activity, and
audit references (or anonymizes where audit must be retained for legal reasons).

### 5.2 Unit economics

Section 25 covers cost controls but there is no cost model. Set a target: cost
per team per day. With 2 LLM calls per member per query across a team, this
decides both viability and pricing. Model it before building, not after the bill
arrives.

Rough model to fill in:

```text
cost_per_run = (reasoning_tokens + validation_tokens) * price_per_token
runs_per_team_per_day = members * queries_per_member + daily_briefings
daily_team_cost = cost_per_run * runs_per_team_per_day + ingestion_cost
```

### 5.3 GitHub App vs OAuth App (and equivalents)

The checklist says "OAuth" generically. For a multi-tenant product use a
**GitHub App with installation tokens**, not per-user OAuth. Installation-scoped
access, higher rate limits, cleaner revocation. Same reasoning favors a Jira
Connect app and Slack app-level tokens. This is a foundational choice, hard to
change later.

### 5.4 Deterministic agent testing

To run evaluations repeatably you must **record and replay tool outputs as
fixtures** and pin model temperature to 0. Otherwise every eval run drifts and
regressions hide. This is the mechanism that makes section 22 actually function,
and the checklist never mentions it.

### 5.5 Works-council and labor-law review

In some jurisdictions an employee-monitoring tool requires formal worker
representation sign-off before any deployment. This can gate the whole product.
Raise it with legal at the start, not before launch.

---

## 6. Best choices: concrete stack

Aligned with the standing constraints (Python for backend and scraping, one
repository per product, small readable functions, every network call has a
timeout and retry limit).

| Layer | Choice | Why |
|---|---|---|
| Backend | Python + FastAPI, async | I/O-bound tool calls, matches standard |
| Orchestrator | Thin explicit state machine in own code | Auditable control flow; avoid heavy agent frameworks early |
| LLM access | Anthropic SDK directly, native tool use + structured outputs | No framework magic hiding the calls you must audit |
| Model tiers | Latest capable Claude for reasoning, cheaper tier for classification | Match model to task, per section 14.1 |
| Primary store | Postgres, single source of truth | Structured queries dominate |
| Semantic search | `pgvector` only when justified | Avoid a separate vector service |
| Cache and rate limiting | Redis | Cache, token buckets, job coordination |
| Job queue | Arq or Celery | Background ingestion and daily analysis |
| Secrets | Cloud secret manager or KMS, read from env at runtime | Never commit tokens |
| Observability | OpenTelemetry traces + a dedicated LLM-trace tool | Both system and AI visibility |
| Auth / SSO | Managed identity provider (do not build) | SSO/OIDC/MFA is solved; do not reinvent |

### Paid or hosted components needing budget sign-off

Per Dynarq rules, do not add these without approval:

- Managed identity provider for SSO (paid; open-source self-host options exist).
- Hosted LLM-trace / evaluation SaaS (paid; self-hostable open-source options
  exist).
- Any hosted vector service (avoidable with `pgvector`).

Confirm budget and preference (managed vs self-host) before any of these is
introduced.

---

## 7. Revised build order

The checklist's Phase 1 is too large. Tighter sequence:

1. **Identity graph plus one integration (GitHub App), read-only.** Prove you can
   map humans to activity correctly. No LLM yet.
2. **Add Jira, read-only. Deterministic member summary:** assigned issues,
   status, open PRs, recent commits. Facts only, no inference, LLM not required.
3. **Add one LLM reasoning call** over the structured evidence, with a strict
   output schema and rule-based HIGH/MEDIUM/LOW confidence. Add deterministic
   conflict detection (Jira state vs GitHub state), which is high value and needs
   no model.
4. **Build the eval harness with recorded fixtures** before adding more features.
   Everything after this gates on evals passing.
5. **Then, and only then:** Slack (opt-in channels), risk detection, daily
   briefing. Write tools and human-in-the-loop come last.

---

## 8. Prioritized gap register

Severity: P0 blocks a trustworthy MVP, P1 needed before real deployment, P2
needed before scale.

| ID | Gap | Severity | Phase | Owner |
|---|---|---|---|---|
| G1 | Identity graph + unmatched-entity queue | P0 | 1 | |
| G2 | Ingestion model (webhook + reconcile + backfill) | P0 | 1 to 2 | |
| G3 | Prompt injection: no write tools in data-reading LLM | P0 | 3 | |
| G4 | Rule-based confidence, defer numeric | P0 | 3 | |
| G5 | Eval harness with recorded fixtures + labeled ground truth | P0 | 4 | |
| G6 | Deterministic conflict detection | P1 | 3 | |
| G7 | GitHub App (not OAuth app) + scoped tokens | P1 | 1 | |
| G8 | Deletion / employee-departure pipeline | P1 | 2 to 3 | |
| G9 | Unit-economics cost model | P1 | 1 | |
| G10 | Rate-limit budgeting per integration | P1 | 2 | |
| G11 | Reduce agent stages to 2 LLM calls | P1 | 3 | |
| G12 | Slack opt-in per channel, deferred | P2 | 5 | |
| G13 | Works-council / labor-law review | P1 | 0 (pre-build) | |
| G14 | Defer vector DB; use pgvector if needed | P2 | later | |
| G15 | Defer HITL / write-tool machinery | P2 | 6 | |

---

## 9. Keep from the checklist unchanged

These parts are correct and should stay as written:

- The product boundary: evidence-based decision support, not surveillance or
  productivity scoring (sections 1, 45, 46).
- The output classes: verified fact, evidence-backed inference, unknown
  (section 1.3). "Unknown is a valid answer" is a genuine strength.
- Typed tool failures (section 60). "Slack access denied" is not "no blockers
  found," and modeling that distinction is exactly right.
- Source authority and explicit conflict reporting (section 13).
- The 15 design principles (section 81). The product will not fail on principles.
  It will fail on identity resolution, ingestion at scale, and shipping the
  guessy inference feature before the reliable deterministic one.

---

## 10. One-line summary

The checklist tells you what a good agent should be. This document tells you the
5 things that actually decide whether it works: get identity resolution right,
design ingestion for real rate limits, keep write tools out of the LLM that reads
untrusted data, ship deterministic facts before guessy inference, and build the
eval harness before you scale features.
