## What changed

<!-- 1 or 2 sentences. What does this pull request do. -->

## Why

<!-- The reason, not the diff. Link the task: Closes #n, or Refs #n if criteria remain. -->

## Not covered

<!-- What a reviewer might expect here and will not find, and why. -->

## Checklist

- [ ] Code plus at least 1 unit test
- [ ] `ruff check .` and `black --check .` pass
- [ ] Public functions have type hints and a docstring
- [ ] No secret in code, logs, prompts, error details or committed files
- [ ] Every network call has a timeout, a retry limit, and logs what was attempted,
      what came back and what was skipped
- [ ] No architectural constraint from `ARCHITECTURE.md` 15 is broken
- [ ] Every acceptance criterion in the task is checked
- [ ] `WORKLOG.md` updated in this same pull request
- [ ] No AI attribution anywhere in the commit or this description (CLAUDE.md rule 1)
