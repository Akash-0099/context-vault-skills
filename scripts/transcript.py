#!/usr/bin/env python3
"""Render a Claude Code session JSONL as readable, redacted markdown in the vault.

  transcript.py <session-id | path.jsonl> [--project NAME]   # /obs-save, backfill
  transcript.py                                             # SessionEnd hook (JSON on stdin)
  transcript.py --test                                      # redaction self-check

Writes <vault>/_transcripts/<project>/YYYY-MM-DD_HH-MM_<title-slug>_<id8>.md and prints the path.
Re-running for the same session overwrites the same file, so links to it never break.
"""
import glob, json, os, re, sys
from collections import Counter
from datetime import datetime

VAULT = os.environ.get('AGENT_CONTEXT_VAULT', '').rstrip('/')
PROJECTS = os.path.expanduser('~/.claude/projects')
MAX_IN, MAX_OUT = 4000, 1500  # chars kept per tool input / tool result

SECRETS = [
    (re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----', re.S), '[REDACTED KEY]'),
    (re.compile(r'\b(?:AKIA|ASIA)[0-9A-Z]{16}\b'), '[REDACTED]'),
    (re.compile(r'\b(?:gh[pousr]_\w{30,}|github_pat_\w{30,}|xox[abprs]-[\w-]{10,}|sk-[\w-]{20,}|AIza[\w-]{35})'), '[REDACTED]'),
    (re.compile(r'\beyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]{10,}'), '[REDACTED JWT]'),
    (re.compile(r'(\w+://[^:/\s@]+:)[^@\s]+@'), r'\1***@'),
    (re.compile(r'(?i)(bearer\s+)[\w.~+/-]{16,}=*'), r'\1***'),
    (re.compile(r'(?i)((?:secret|passw(?:or)?d|pwd|token|api[_-]?key|access[_-]?key|private[_-]?key|authorization)\w*["\']?\s*[:=]\s*)(["\'])[^"\'\s]{4,}\2'), r'\1\2***\2'),
    (re.compile(r'(?m)^(\s*(?:export\s+)?[A-Z0-9_]*(?:SECRET|PASSWORD|PASSWD|TOKEN|API_?KEY|ACCESS_?KEY|PRIVATE_?KEY)[A-Z0-9_]*\s*=\s*)\S+'), r'\1***'),
]


def redact(s):
    for rx, rep in SECRETS:
        s = rx.sub(rep, s)
    return s


def cut(s, n):
    return s if len(s) <= n else s[:n] + f'\n… [{len(s) - n} chars truncated]'


def fence(s, lang=''):
    ticks = '`' * max(3, max(map(len, re.findall(r'`+', s)), default=0) + 1)
    return f'{ticks}{lang}\n{s}\n{ticks}'


def collapsed(title, body):
    return f'> [!quote]- {title}\n' + '\n'.join('> ' + l for l in body.splitlines())


_repo_cache = {}


def repo_of(path):
    d = os.path.dirname(path)
    if d not in _repo_cache:
        r = d
        while r not in ('', '/') and not os.path.exists(os.path.join(r, '.git')):
            r = os.path.dirname(r)
        _repo_cache[d] = os.path.basename(r) if r not in ('', '/') else None
    return _repo_cache[d]


def text_of(content):
    if isinstance(content, str):
        return content
    out = []
    for b in content or []:
        if b.get('type') == 'text':
            out.append(b['text'])
        elif b.get('type') == 'image':
            out.append('[image]')
    return '\n'.join(out)


def render_tool(name, inp):
    path = inp.get('file_path') or inp.get('notebook_path') or ''
    if name == 'Bash':
        return f"**Bash** — {inp.get('description', '')}\n{fence(cut(inp.get('command', ''), MAX_IN), 'bash')}"
    if name in ('Edit', 'MultiEdit'):
        edits = inp.get('edits') or [inp]
        diff = '\n\n'.join('\n'.join(['- ' + l for l in e.get('old_string', '').splitlines()] +
                                     ['+ ' + l for l in e.get('new_string', '').splitlines()]) for e in edits)
        return f'**{name}** `{path}`\n{fence(cut(diff, MAX_IN), "diff")}'
    if name == 'Write':
        return f'**Write** `{path}`\n{fence(cut(inp.get("content", ""), MAX_IN))}'
    if name == 'Read':
        return f'**Read** `{path}`'
    return f'**{name}**\n{fence(cut(json.dumps(inp, indent=1, ensure_ascii=False), MAX_IN), "json")}'


def render(jsonl, project=None):
    rows = [json.loads(l) for l in open(jsonl, encoding='utf-8') if l.strip()]
    sid = os.path.basename(jsonl)[:-6]
    title, cwd, branch, start, session_log = None, '', '', None, None
    weights, body, last, prompts = Counter(), [], None, 0

    for d in rows:
        if d.get('type') == 'ai-title':
            title = d.get('aiTitle') or title
        if d.get('type') not in ('user', 'assistant') or d.get('isMeta') or d.get('isSidechain'):
            continue
        cwd, branch = d.get('cwd') or cwd, d.get('gitBranch') or branch
        ts = datetime.fromisoformat(d.get('timestamp', '1970-01-01T00:00:00Z').replace('Z', '+00:00')).astimezone()
        start = start or ts
        content = (d.get('message') or {}).get('content')

        if d['type'] == 'user':
            if d.get('isCompactSummary'):
                body.append(collapsed('Context compacted — summary', redact(text_of(content))))
                continue
            results = [b for b in content if b.get('type') == 'tool_result'] if isinstance(content, list) else []
            for b in results:
                out = redact(cut(text_of(b.get('content')), MAX_OUT))
                if out.strip():
                    body.append(collapsed('Error' if b.get('is_error') else 'Output', fence(out)))
            if results:
                continue
            t = re.sub(r'<system-reminder>.*?</system-reminder>', '', text_of(content), flags=re.S).strip()
            cmd = re.search(r'<command-name>(.*?)</command-name>', t)
            if cmd:
                args = re.search(r'<command-args>(.*?)</command-args>', t, re.S)
                t = f"`{cmd.group(1)} {args.group(1).strip() if args else ''}`".replace(' `', '`')
            elif not t or t.startswith('<local-command'):
                continue
            prompts += 1
            body.append(f'## User · {ts:%H:%M}\n\n{redact(t)}')
            last = 'user'
            continue

        for b in content if isinstance(content, list) else []:
            if b.get('type') not in ('text', 'tool_use'):
                continue
            if last != 'claude':
                body.append(f'## Claude · {ts:%H:%M}')
                last = 'claude'
            if b['type'] == 'text':
                body.append(redact(b['text']))
                continue
            inp = b.get('input') or {}
            path = inp.get('file_path') or inp.get('notebook_path') or inp.get('path') or ''
            if path.startswith('/') and not (VAULT and path.startswith(VAULT)):
                repo = repo_of(path)
                if repo:
                    weights[repo] += 3 if b['name'] in ('Edit', 'MultiEdit', 'Write', 'NotebookEdit') else 1
            if b['name'] == 'Write' and VAULT and path.startswith(VAULT) and '/_transcripts/' not in path \
                    and re.search(r'/\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}[^/]*\.md$', path):
                session_log = os.path.basename(path)[:-3]
            body.append(redact(render_tool(b['name'], inp)))

    if not prompts:
        return None  # opened and closed without a prompt: nothing worth keeping

    existing = glob.glob(f'{VAULT}/_transcripts/*/*_{sid[:8]}.md')
    if not project and existing:
        project = os.path.basename(os.path.dirname(existing[0]))
    project = project or (weights.most_common(1)[0][0] if weights else None) \
        or (cwd and repo_of(os.path.join(cwd, 'x'))) or os.path.basename(cwd) or 'misc'
    if existing:
        name = os.path.basename(existing[0])
    else:
        slug = re.sub(r'[^a-z0-9]+', '-', (title or 'untitled').lower()).strip('-')[:50].strip('-')
        name = f'{start:%Y-%m-%d_%H-%M}_{slug}_{sid[:8]}.md'
    out = f'{VAULT}/_transcripts/{project}/{name}'

    head = ['---', 'tags: [transcript]', f'date: {start:%Y-%m-%d}', f'session_id: {sid}',
            f'title: {json.dumps(title or "")}', f'project: "[[{project}]]"', f'cwd: {json.dumps(cwd)}',
            f'branch: {json.dumps(branch)}']
    if session_log:
        head.append(f'session_log: "[[{session_log}]]"')
    head += ['---', '', f'# {title or sid}', '']

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(head) + '\n' + '\n\n'.join(body) + '\n')
    for old in existing:
        if old != out:
            os.remove(old)
    return out


def test():
    cases = {
        'DB_PASSWORD=hunter2': 'DB_PASSWORD=***',
        'mongodb://admin:s3cret@10.0.0.1/db': 'mongodb://admin:***@10.0.0.1/db',
        '{"apiKey": "abcd1234efgh"}': '{"apiKey": "***"}',
        'Authorization: Bearer abcdefghijklmnopqrstu': 'Authorization: Bearer ***',
        'const token = this.auth.getToken();': 'const token = this.auth.getToken();',
        'https://github.com/org/repo': 'https://github.com/org/repo',
    }
    for src, want in cases.items():
        assert redact(src) == want, (src, redact(src))
    print('ok')


def main():
    args = sys.argv[1:]
    if args == ['--test']:
        return test()
    if not VAULT or not os.path.isdir(VAULT):
        sys.exit('AGENT_CONTEXT_VAULT is not set or missing')
    project = args[args.index('--project') + 1] if '--project' in args else None
    target = args[0] if args and args[0] != '--project' else json.load(sys.stdin).get('transcript_path', '')
    if not target.endswith('.jsonl'):
        found = glob.glob(f'{PROJECTS}/*/{target}.jsonl')
        target = found[0] if found else ''
    if not os.path.isfile(target):
        sys.exit(f'transcript not found: {args[:1]}')
    out = render(target, project)
    print(out or 'skipped: no prompts in session')


if __name__ == '__main__':
    main()
