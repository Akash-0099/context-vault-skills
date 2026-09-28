---
name: harpoon
description: Use when the user asks a question about past work, wants context on a topic, or needs to recall what happened with a specific feature, bug, or migration. Also use when the user says recall, remember, or look up something from the vault.
---

# Harpoon — Graph-Walking Context Retrieval

Retrieve context from the Obsidian Agent Context Vault by **navigating the graph: project hub → feature docs → session logs**, not by scanning files.

## Invocation

- `/harpoon <topic or question>` — direct query, scoped to the current project
- `/harpoon <topic> in <project>` — query a specific project
- `/harpoon <topic> --all` — query across all projects (use sparingly; expensive)
- `/harpoon` — ask the user what they want to know

## The Rule

**NEVER grep or glob session files directly. Always enter through the project hub. NEVER open `_transcripts/`** — they are full conversations, reserved for `/detective`.

You are navigating a knowledge graph like a human in Obsidian — clicking hub nodes, following links, hopping between connected files. You are NOT a search engine.

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
2. If the user passed `--all`, read every hub (`<vault>/*/<name>.md` where `<name>` is the folder name) at Hop 0 and pick the best-matching project(s).
3. Otherwise use the git repo of the current working directory (`basename $(git rev-parse --show-toplevel)`), falling back to the cwd basename. If the cwd is not a repo (e.g. home dir), treat it like `--all`.

Project folder: `<vault>/<project>/` containing `<project>.md` (hub), `features/`, `sessions/`, `artifacts/`.

If that folder does not exist, tell the user:

> No vault folder for `<project>`. Try `/harpoon <topic> --all` or `/harpoon <topic> in <project-name>`.

and stop.

## Graph Traversal

### Hop 0 — Hub (and segment)
Read `<vault>/<project>/<project>.md`. Its `## Features` table lists every feature doc with a one-line description.

**Segmented repo** (hub has a `## Segments` table instead, e.g. posistApp): match the question to 1-2 segments by name, "Covers" and code paths, and read their segment notes `features/<Segment>/<project> - <Segment>.md`. The segment note has the area overview, area-wide gotchas and that segment's Features table. For a brand-new feature, the segment note is often all you need.

### Hop 1 — Feature docs (usually enough)
Match the question against the Features table. Read 1-3 feature docs from `<project>/features/` (or `features/<Segment>/`). They hold the **current** state (what it is, how it works, key files, gotchas) plus a dated changelog. Most questions are answered here — if so, stop and answer.

### Hop 2 — Session logs
If you need the why, when, or a decision's context, pick 2-4 sessions from the feature doc's `## Changelog` and read them from `<project>/sessions/`. A changelog row may link a transcript instead of a session (no session log was saved); do not open it — mention it as a `/detective` lead.

### Hop 3 — Cross-links (optional)
Follow at most 2 essential links: a sibling feature doc in another repo (cross-repo features link each other in their header line), or an artifact in `<project>/artifacts/` listed in a session's `artifacts:` frontmatter.

### Fallback — topic not in the Features table
Grep ONLY the hub and feature docs: `grep -ril "<keyword>" <vault>/<project>/<project>.md <vault>/<project>/features/`. Still nothing → try other projects' `features/` folders. Still nothing → say the topic isn't in the vault and suggest `/detective <topic>` (it can search transcripts).

## Constraints

- **Max 10 file reads total** per query; never re-read a file
- Hub first, feature docs second, sessions only via a changelog link
- **Never read `_transcripts/`** — if exact implementation detail is needed and the session log lacks it, say so and suggest `/detective`

## Output Format

```markdown
## Harpoon: <topic>

**Project:** <project>
**Trail:** <project> hub → <segment note, if segmented> → <feature doc(s)> → <session 1>, <session 2>, <artifact if any>

### Answer
<synthesized answer drawing from the traversed files>

### Key Sessions
- [[session-file]] — what it contributes to the answer
- [[session-file]] — ...

### Key Artifacts
- [[artifact-file]] — plan/design/spec that is directly relevant
<omit this section if no artifacts were read>

### Related Topics
- [[wiki-link]] — for further exploration
```

## Red Flags — You Are Doing It Wrong

| If you're doing this... | Stop and... |
|------------------------|-------------|
| Grepping session files or transcripts | Read the hub and feature docs first |
| Opening anything in `_transcripts/` | That's `/detective`'s job — suggest it |
| Reading sessions before feature docs | The feature doc likely already answers it |
| Reading more than 10 files | You have enough context, synthesize |
| Skipping Hop 0 | Always start at `<project>/<project>.md` |
