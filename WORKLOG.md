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
