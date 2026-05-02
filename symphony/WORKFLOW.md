---
tracker:
  kind: linear
  api_key: $LINEAR_API_KEY
  # Hardcoded for mc-kenneth so a single Infisical workspace
  # (shared with mc-briefings, mc-siam, claudette-*) doesn't collide on
  # the LINEAR_TEAM_KEY env var.
  team_key: KEN
  active_states: [Todo, "In Progress"]
  terminal_states: [Done, Canceled, Cancelled, Duplicate]
  exclude_labels: [tutorial, draft, manual-only, no-symphony]

polling:
  interval_ms: 30000

workspace:
  root: ~/symphony_workspaces

hooks:
  # IMPORTANT: workshop's Infisical workspace injects a stale `GITHUB_TOKEN`
  # (a `gho_…` value used by another consumer). When set, `gh auth git-credential`
  # returns the env-var token to git, overriding gh's stored credential and
  # failing auth with "Invalid username or token". `unset GITHUB_TOKEN` lets
  # gh's stored credential in ~/.config/gh/hosts.yml win.
  after_create: |
    set -euo pipefail
    unset GITHUB_TOKEN
    git clone https://github.com/mattcarp/mc-kenneth.git .
    git checkout -b symphony/$SYMPHONY_ISSUE_IDENTIFIER

  before_run: |
    set -euo pipefail
    unset GITHUB_TOKEN
    if [ -z "$(ls -A . 2>/dev/null)" ]; then
      git clone https://github.com/mattcarp/mc-kenneth.git .
      git checkout -b symphony/$SYMPHONY_ISSUE_IDENTIFIER 2>/dev/null || git checkout symphony/$SYMPHONY_ISSUE_IDENTIFIER
    fi
    git fetch origin main --quiet || true

  timeout_ms: 120000

agent:
  max_concurrent_agents: 2
  max_turns: 6
  max_retry_backoff_ms: 600000

codex:
  command: >-
    claude -p
    --output-format=stream-json
    --verbose
    --permission-mode=acceptEdits
    --allowedTools "Read,Edit,Write,Glob,Grep,Bash(git status),Bash(git diff:*),Bash(git log:*),Bash(git add:*),Bash(git commit:*),Bash(git checkout:*),Bash(git push:*),Bash(python:*),Bash(python3:*),Bash(pytest:*),Bash(uv:*),Bash(pip:*),Bash(npm install:*),Bash(npm run:*),Bash(npx tsc:*)"
  turn_timeout_ms: 3600000
  read_timeout_ms: 5000
  stall_timeout_ms: 300000

server:
  port: 4753
  host: 127.0.0.1
---

# Task

You are working on Linear issue **{{ issue.identifier }}**: {{ issue.title }}

{% if issue.description %}
## Description

{{ issue.description }}
{% endif %}

{% if issue.labels.size > 0 %}
**Labels:** {{ issue.labels | join: ", " }}
{% endif %}

{% if attempt %}
> **Continuation (attempt {{ attempt }}).** A previous turn ran. Pick up where it left off and take the next sensible step toward closing the issue.
{% endif %}

## Working agreement

- You are inside a fresh git worktree of `mc-kenneth`. The branch `symphony/{{ issue.identifier }}` is checked out.
- Read [CLAUDE.md](CLAUDE.md) / [AGENTS.md](AGENTS.md) and `KENNETH_PRD.md` and `MISSION.md` before making changes.
- This is an **RF forensics platform** — many subsystems run against live SDR hardware (RTL-SDR, RSPdx). If your issue affects a capture pipeline, document the impact on the existing capture chain in the commit body.
- Make focused, minimal changes that map directly to the issue.
- For Python changes: run `python3 -m pytest <module>/` for any module you touched. Don't add tests against mocks — capture pipelines and decoders should hit real hardware fixtures or fail honestly.
- Commit with a message that references `{{ issue.identifier }}`. Do not push unless the issue's labels include `auto-push`.
- The repo has many docs (`KENNETH_*.md`). They're a record of decisions, not active specs — read them as background, but the canonical specification of behaviour for an issue is the issue itself + `KENNETH_PRD.md`.

## Closing the issue (REQUIRED)

When you have completed the work for `{{ issue.identifier }}`, include the marker `[symphony:done]` in your **final commit's message body**. Without the marker, the harness will dispatch additional turns until `max_turns` is reached.

If the issue is ambiguous, write a note at `symphony-notes/{{ issue.identifier }}.md` explaining what you'd need to know, commit it with `[symphony:done]` in the message, and stop. Do not guess at SDR configuration or capture pipeline behaviour.

## Issue link

{{ issue.url }}
