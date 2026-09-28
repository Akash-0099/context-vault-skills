---
name: detective
description: Use when the user wants the complete picture of a topic, bug chain, decision history, or system evolution — needs exhaustive investigation, not a quick answer. Triggers on words like whole picture, everything about, trace, investigate, deep dive, full story.
---

# Detective — Deep Graph Investigation

Build the **complete picture** of a topic by systematically mapping and investigating the knowledge graph — feature docs, session logs, the plan/design/spec artifacts linked from them, and — when implementation detail is needed — the full session transcripts. Unlike `/harpoon` (quick answer, ~10 reads), detective does exhaustive two-pass research (~30 reads).

## Invocation

- `/detective <topic or question>` — investigate within the current project
- `/detective <topic> in <project>` — investigate a specific project
- `/detective <topic> --all` — investigate across all projects (expensive; use when a topic genuinely spans projects)
- `/detective` — ask the user what they want to investigate

## The Rules

1. **Map before you dig** — read the hub and ALL relevant feature docs, and list candidate artifacts, BEFORE reading any session log.
2. **Feature docs are the index** — sessions and transcripts are discovered through feature-doc changelogs, session frontmatter (`transcript:`, `artifacts:`) and daily notes, not by grepping sessions.
3. **Transcripts are last** — `_transcripts/` holds full conversations. Open one only when a session log lacks the implementation detail the question needs. Grep inside it for the relevant part; never read a whole transcript top to bottom.
4. **Build the case board explicitly** before Pass 2.
5. **Artifacts are first-class evidence** — a plan or design often holds more decision history than three session summaries.

## Resolve the Vault Root

Run this command with the Bash tool:

```bash
v="${AGENT_CONTEXT_VAULT%/}"; echo "vault=${v:-UNSET}"; [ -d "$v" ] && echo "status=ok" || echo "status=missing"
```

- `vault=UNSET` → stop and tell the user:

  > `AGENT_CONTEXT_VAULT` is not set. Add `{ "env": { "AGENT_CONTEXT_VAULT": "/absolute/path/to/vault" } }` to `~/.claude/settings.json`, then start a new session.

- `status=missing` → stop and tell the user that the vault directory does not exist at the printed path.
- `status=ok` → use the printed path as `<vault>` in every path below. Use it exactly as printed (case-sensitive). Do not search for the vault anywhere else.

## Determining Scope

1. If the user specified `in <project>`, use that as `<project>`.
2. If the user passed `--all`, read every project hub (`<vault>/<name>/<name>.md`) in Pass 1.
3. Otherwise use the git repo of the current working directory (`basename $(git rev-parse --show-toplevel)`), falling back to the cwd basename. Cross-repo features link their sibling feature docs in other repos — follow those.

Project folder: `<vault>/<project>/` with `<project>.md` (hub), `features/`, `sessions/`, `artifacts/`. Transcripts: `<vault>/_transcripts/<project>/`. Daily notes: `<vault>/Daily/`.

If the folder does not exist, tell the user:

> No vault folder for `<project>`. Try `/detective <topic> --all` or `/detective <topic> in <project-name>`.

and stop.

## Three-Pass Algorithm

### Pass 1 — MAP (build the case board)

1. Read the hub `<vault>/<project>/<project>.md`.
2. Read ALL feature docs relevant to the topic (cast wide; include sibling docs in other repos linked from their header line). If the Features table doesn't match, `grep -ril "<keyword>" <vault>/*/features/`.
3. List (do not read) `<project>/artifacts/`; note filenames matching the topic.
4. Build the case board from the feature docs' `## Changelog` rows: every session log and every transcript-only row, plus candidate artifacts. Sort chronologically.

```markdown
## Case Board: <topic>

**Project:** <project>
**Feature docs consulted:** <list>

### Sessions (chronological)
| # | Session | From feature doc | One-liner |
|---|---------|------------------|-----------|
| 1 | [[YYYY-MM-DD_HH-MM-SS_slug]] | <doc> | what it's about |

### Artifacts
| # | Artifact | Type | Why it's a lead |
|---|----------|------|-----------------|
```

### Pass 2 — DIG (sessions and artifacts)

Read sessions in chronological order. For each: what happened, what caused it, what it led to, and any cross-links not on the board. Open artifacts listed in a session's `artifacts:` frontmatter or already on the board. Track the narrative.

### Pass 3 — TRANSCRIPTS (only when needed)

Needed when the question is about *how exactly* something was implemented (exact edits, commands run, approaches tried and abandoned) and the session log only summarises it, or when a changelog row links a transcript with no session log.

1. Take the transcript from the session's `transcript:` frontmatter (or the changelog link).
2. `grep -n "<keyword>" <transcript>` to find the relevant turns, then read only those line ranges (±60 lines). User turns are `## User · HH:MM`, Claude turns `## Claude · HH:MM`; edits appear as `**Edit**` lines followed by a diff block.
3. No link but you need one? `grep -ril "<keyword>" <vault>/_transcripts/<project>/` — allowed in this pass only.

### Budget

- Pass 1: up to 12 reads · Pass 2: up to 15 · Pass 3: up to 8 targeted reads (grep hits count free)
- Total cap ~35 reads

## Output Format

```markdown
## Detective Report: <topic>

**Project:** <project>
**Investigation scope:** <F> feature docs, <N> sessions, <A> artifacts, <T> transcripts | <total> files read
**Trail:** <project> hub → <feature docs> → <sessions/artifacts> → <transcripts>

### Timeline
Chronological narrative connecting all the dots. For each event:
- **<date>** — What happened. Why it happened. What it caused next.
  - Root cause: ...
  - Fix: ...
  - Downstream impact: ...
  - Referenced artifact: [[...]] (if any)

### Decisions Made
Key architectural or technical decisions discovered during the investigation, with the *why*:
- **<decision>** — why it was chosen, what alternatives were rejected, which artifact / session recorded it

### Recurring Patterns
Patterns that kept appearing across sessions or artifacts:
- **Pattern name** — description, which sessions/artifacts exhibited it

### Root Causes
The underlying decisions or conditions that started the chain:
- ...

### Implementation Detail (from transcripts)
How it was actually built, only where transcripts were read: exact edits, commands, dead ends, and why the final approach won.
<omit this section if no transcripts were read>

### Plans & Designs Consulted
Artifacts that shaped the work, and what each contributed:
- **[[artifact]]** (type) — what design thinking it captured, which decisions it drove
<omit this section if no artifacts were read>

### Key Sessions
- [[session]] — its role in the story
- ...

### Connections Discovered
Non-obvious links between topics that only become visible when you see the full picture:
- ...

### Open Threads
Sessions, artifacts, or topics referenced but not investigated (out of budget or tangential):
- ...
```

## Red Flags — You Are Doing It Wrong

| If you're doing this... | Stop and... |
|------------------------|-------------|
| Reading sessions before the hub and feature docs | Finish Pass 1 first |
| Reading a whole transcript | Grep it, read only the matching ranges |
| Opening transcripts when the session log already answers | Transcripts are for implementation detail only |
| Not building a case board | List every session AND artifact before reading any |
| Reading sessions in random order | Sort chronologically |
| Reading 45+ files | You have enough, synthesize |

## When to Use Detective vs Harpoon

| | Harpoon | Detective |
|---|---------|-----------|
| **Purpose** | Answer a question | Tell the whole story / how it was built |
| **Budget** | ~10 reads | ~35 reads |
| **Reads** | Hub → 1-3 feature docs → a few sessions | Hub → all relevant feature docs → sessions → artifacts → transcripts |
| **Transcripts** | Never | When implementation detail is needed |
| **Output** | Answer + key sessions | Timeline + decisions + root causes + implementation detail |
