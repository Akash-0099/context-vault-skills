---
name: obs-save
description: Save a session summary plus any plan/design/spec/brainstorm artifacts to the Obsidian vault before clearing context
disable-model-invocation: true
user-invocable: true
---

# Obsidian Session Save

Save a concise summary of the current conversation to the Obsidian vault, **including any working artifacts produced during the session** (plans, designs, specs, brainstorms, review reports), then compact the context.

## Step 0: Resolve the vault root

Run this command with the Bash tool:

```bash
v="${AGENT_CONTEXT_VAULT%/}"; echo "vault=${v:-UNSET}"; [ -d "$v" ] && echo "status=ok" || echo "status=missing"
```

- `vault=UNSET` → stop and tell the user:

  > `AGENT_CONTEXT_VAULT` is not set. Add `{ "env": { "AGENT_CONTEXT_VAULT": "/absolute/path/to/vault" } }` to `~/.claude/settings.json`, then start a new session.

- `status=missing` → stop and tell the user that the vault directory does not exist at the printed path.
- `status=ok` → use the printed path as `<vault>` in every path below. Use it exactly as printed (case-sensitive). Do not search for the vault anywhere else.

## Step 1: Determine the project(s)

Projects are git repos, not the working directory. List every repo this session touched: the git root (`git -C <dir> rev-parse --show-toplevel`) of each file you edited or created, plus the repo(s) an investigation was about if you only read code. Ignore the vault itself.

- `<project>` = the primary repo: most changes, or the one the session centred on. The session log goes there.
- `<repos>` = all touched repos, including `<project>`. Each gets its feature docs updated in Step 6.
- No repo involved at all → `<project>` = basename of the current working directory.

## Step 1b: Name the session

A future agent picks which note to open from the filename alone, so the name must say what the session was about and what changed. Build:

```
<session-name> = YYYY-MM-DD_HH-MM-SS_<topic-slug>
```

`<topic-slug>` rules:
- 3–8 lowercase words, kebab-case, max 60 chars, only `a-z0-9-`
- Lead with the feature/module/component touched, then what happened: `fix`, `add`, `investigate`, `plan`, `refactor`, `review`, `migrate`, …
- Include a ticket ID or branch name when there is one
- Name the specifics, not the category. Banned words: `session`, `work`, `update`, `changes`, `misc`, `stuff`, `various`, `general`
- Several unrelated topics → name the biggest two (`kds-reprint-fix-and-socket-timeout-investigation`)

Good: `kds-duplicate-ticket-reprint-fix`, `pos-gst-rounding-root-cause-investigation`, `obs-save-descriptive-filenames`
Bad: `bug-fix`, `kds-changes`, `session-notes`, `misc-updates`

Also write `<session-title>`: the same topic as a short human-readable title (e.g. "KDS duplicate ticket reprint fix").

## Step 2: Identify session artifacts

Scan your own tool-use history for this session. Identify files you **created or materially rewrote** that match the artifact profile below. Do NOT scan the filesystem — rely on what you actually wrote during this session.

**Artifact profile (include):**
- Plans: `*plan*.md`, `*.plan.md`, anything under `plans/`, `.plans/`
- Brainstorms: `*brainstorm*.md`, anything under `brainstorms/`, `.brainstorms/`
- Designs: `DESIGN.md`, `*design*.md`, anything under `.design/`, `design/`
- Specs: `*spec*.md`, `SPEC.md`, anything under `specs/`
- Review reports: `*review*.md`, `code-review-*.md`, anything under `reviews/`
- Any standalone `.md` in a hidden (`.`-prefixed) working directory that this session created

**Exclude:**
- Source code (`.ts`, `.tsx`, `.js`, `.py`, `.go`, etc.)
- Config files (`package.json`, `tsconfig.json`, `.env*`, etc.)
- `README.md`, `CHANGELOG.md`, `LICENSE` — project-level docs, not session artifacts
- Anything already inside the vault
- Trivial edits (a 1-line change does not an artifact make)

If no artifacts were produced, skip to Step 4.

## Step 3: Confirm and copy artifacts

Show the user the detected artifact list in this exact format:

```
## Detected session artifacts

1. <type>: <relative path from cwd>
2. <type>: <relative path from cwd>
...

Copy these to the vault? (y / n / select: 1,3)
```

Wait for the user's answer. On `y` or a selection, copy each confirmed artifact to:

```
<vault>/<project>/artifacts/YYYY-MM-DD_<type>_<artifact-slug>.md
```

Where:
- `YYYY-MM-DD` is today's date
- `<type>` is `plan`, `design`, `brainstorm`, `spec` or `review`
- `<artifact-slug>` names what the artifact covers, following the `<topic-slug>` rules from Step 1b (e.g. `2026-09-25_plan_kds-socket-reconnect-retry.md`, not `2026-09-25_plan.md`)

**Artifact file format:** prepend this frontmatter, then the **full original content unchanged**:

```markdown
---
aliases: []
tags: [artifact, <type>]
date: YYYY-MM-DD
project: "[[<project>]]"
type: <plan | design | brainstorm | spec | review>
source_path: <absolute path to the original file in the project repo>
session: "[[<session-name>]]"
---

<original file content verbatim>
```

Create the `artifacts/` subfolder if it does not exist. Do **not** modify the original file in the project repo — this is a copy, not a move.

Remember the list of vault-relative paths of each copied artifact for Step 5.

## Step 4: Create the session note

Create the session log at:

```
<vault>/<project>/sessions/<session-name>.md
```

Use `<session-name>` from Step 1b (current date and 24-hour time). Create the directories if they do not exist.

## Step 4b: Save the transcript

Run:

```bash
python3 ~/.claude/context-vault-skills/scripts/transcript.py "${CLAUDE_SESSION_ID}" --project <project>
```

It renders this session's full conversation (redacted, tool output truncated) to `<vault>/_transcripts/<project>/…md` and prints the path. `<transcript-name>` = that file's basename without `.md`. A SessionEnd hook re-renders the same file when the session ends, so it ends up complete. If the script fails, omit the `transcript:` field and mention it in Step 8.

## Step 5: Format the session note

The file MUST follow this exact format:

```markdown
---
aliases: []
tags: [devlog, context, claude-session]
date: YYYY-MM-DD
project: "[[<project>]]"
transcript: "[[<transcript-name>]]"
features:
  - "[[<feature-doc-1>]]"
artifacts:
  - "[[<artifact-wiki-link-1>]]"
  - "[[<artifact-wiki-link-2>]]"
related:
  - "[[<related-note-1>]]"
  - "[[<related-note-2>]]"
---

# <session-title> — <Month DD, YYYY HH:MM AM/PM>

**Project:** `<full working directory path>`

## Summary

<2-5 bullet points summarizing what was accomplished, discussed, or decided>

## Key Changes

<Source-code / config files created, modified, or deleted in the project repo. If none, write "No file changes.">

## Artifacts

<For each copied artifact, one bullet:>
- **[[<artifact-wiki-link>]]** (<type>) — one-line description of what it is and why it exists

<If no artifacts were copied, omit this whole section.>

## Decisions & Context

<Any architectural decisions, gotchas discovered, or important context for future sessions. Use [[backlinks]] for technologies, patterns, and related notes.>

## Related
- [[<project>]]
- <any other relevant backlinks discovered during the session>
```

### Rules

- **Tag format is `[devlog, context, claude-session]` — NO `#` prefix.** YAML treats `#` as a comment and the frontmatter will silently fail to parse.
- Use `[[wikilinks]]` throughout the body for all technologies, projects, patterns, concepts, and artifacts mentioned
- The `related` frontmatter and `## Related` section must include the project name and any technologies/concepts discussed
- The `artifacts` frontmatter field is **omitted entirely** if no artifacts were copied (do not write `artifacts: []`)
- Keep the summary concise — this is a reference note, not a transcript
- If the session was trivial, still save a note but say so in the summary
- Do NOT include full code blocks or long outputs — summarize instead

## Step 6: Update the feature docs

Feature docs are the project's living knowledge: what exists and how it works **now**. Every session must land in at least one feature doc changelog, in every repo in `<repos>`.

For each repo in `<repos>`:

1. List `<vault>/<repo>/features/`. Pick the doc(s) for the feature/module this session touched (e.g. `DMB.md`, `KDS Recall.md`). A feature is a user-facing capability or module, not a single change: a new DMB button goes in `DMB.md`, not a new doc.
2. **No matching doc?** Create `<vault>/<repo>/features/<Feature Name>.md` from the template below. Filenames must be unique across the vault (wiki-links resolve by name): check with `find "<vault>" -name "<Feature Name>.md"` and add ` (<repo>)` on a clash.
3. **Edit the doc in place** so it stays true: rewrite `What it is`, `How it works`, `Key files` and `Gotchas` to reflect the current state (replace outdated lines, don't append history there). Keep it short; no code blocks longer than a few lines.
4. Append one row to `## Changelog`: `| YYYY-MM-DD | <what changed or was learned> | <branch or —> | [[<session-name>]] |`. Investigation-only sessions still get a row.
5. Update frontmatter `updated:` to today, `status:` (`in-progress` = on a branch, `shipped` = merged to prod, `investigating` = no code yet) and `branches:`.
6. For cross-repo work, link the sibling feature docs in each doc's header line.

Then the hub `<vault>/<repo>/<repo>.md` (create it from the template if missing): add a row to its `## Features` table for any new doc, and refresh `Status` / `Updated` for the ones you touched.

Add every feature doc you touched to the session note's `features:` frontmatter.

**Feature doc template:**

```markdown
---
tags: [feature]
project: "[[<repo>]]"
status: in-progress
branches: [<branch>]
updated: YYYY-MM-DD
---
# <Feature Name>

> [[<repo>]] · other parts: [[<sibling doc>]] (<other repo>)

## What it is
<1-3 lines: what the feature does for the user>

## How it works
<bullets: flow, data shape, settings, APIs — current truth>

## Key files
- `<path>` — <role>

## Gotchas
- <traps, config quirks, open decisions>

## Changelog
| Date | Change | Branch | Session |
|---|---|---|---|
| YYYY-MM-DD | <change> | <branch> | [[<session-name>]] |
```

**Hub template** (`<vault>/<repo>/<repo>.md`; named after the repo so every `[[<repo>]]` link lands on it):

```markdown
---
tags: [hub, project]
aliases: []
repo: <absolute repo path>
prod_branch: <branch>
updated: YYYY-MM-DD
---
# <repo>

<one line: what this repo is>

## Features
| Feature | What | Status | Updated |
|---|---|---|---|
| [[<Feature Name>]] | <one line> | <status> | YYYY-MM-DD |
```

### Rules

- Never modify session logs or transcripts after writing them.
- Feature docs and hubs are living documents: edit freely, but keep changelog rows (append only).

## Step 7: Add to the daily note

Append one line to `<vault>/Daily/YYYY-MM-DD.md` (today). Create it if missing with frontmatter `tags: [daily]`, `date: YYYY-MM-DD` and heading `# YYYY-MM-DD`.

```
- **<project>** — [[<session-name>]] — <one-line what was done> ([[<feature-doc>]], …)
```

## Step 8: Confirm and compact

Report to the user:
- The session file path
- A one-line summary of what was saved
- The count and vault paths of any artifacts copied
- The transcript path
- The feature docs created or updated (per repo) and the daily note line

Then run `/clear` to compact the context.
