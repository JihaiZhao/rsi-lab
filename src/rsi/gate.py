"""Pre-evaluation gate. Deterministic checks before any task trial is spent.

Smoke tests run candidate code in a network-less container with no credentials,
mounted read-only at the same path the task agent will see.
"""
import json
import os
import re
import subprocess
from pathlib import Path

from rsi import bundle as portable

NGRAM = 8
SECRET_PATTERNS = [r'sk-ant-[A-Za-z0-9_-]{10,}', r'sk-[A-Za-z0-9]{20,}', r'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}',
                   r'CLAUDE_CODE_OAUTH_TOKEN\s*=', r'OPENAI_API_KEY\s*=', r'ANTHROPIC_API_KEY\s*=']
LITERAL_COMPOSITION = r'\b[A-Z][a-z]?-0\.\d+(?:-[A-Z][a-z]?-0\.\d+)+'
# Path-shaped only: words like "solution" are ordinary chemistry vocabulary.
FORBIDDEN_REFERENCES = [r'/(tests?|solutions?)/', r'\b(solve|solution)\.(sh|py)\b', r'\breward\.(txt|json)\b',
                        r'api\.anthropic\.com', r'api\.openai\.com', r'\bhttps?://']

MCP_PROBE = r'''
import json, subprocess, sys
p = subprocess.Popen(sys.argv[1:], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
def call(i, method, params):
    p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": i, "method": method, "params": params}) + "\n"); p.stdin.flush()
    while True:
        line = p.stdout.readline()
        if not line: sys.exit("server closed stdout")
        msg = json.loads(line)
        if msg.get("id") == i: return msg
init = call(1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "rsi-gate", "version": "0"}})
assert "result" in init, init
p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"); p.stdin.flush()
tools = call(2, "tools/list", {})
names = [t["name"] for t in tools["result"]["tools"]]
assert names, "no tools exposed"
print(json.dumps(names)); p.kill()
'''

HOOK_EVENT_SAMPLES = {
    'session_start': {'hook_event_name': 'SessionStart', 'source': 'startup', 'cwd': '/tmp'},
    'pre_tool': {'hook_event_name': 'PreToolUse', 'tool_name': 'Bash', 'tool_input': {'command': 'ls'}, 'cwd': '/tmp'},
    'post_tool': {'hook_event_name': 'PostToolUse', 'tool_name': 'Bash', 'tool_input': {'command': 'ls'},
                  'tool_response': {'stdout': '', 'stderr': '', 'exit_code': 0}, 'cwd': '/tmp'},
    'stop': {'hook_event_name': 'Stop', 'stop_hook_active': False, 'cwd': '/tmp'},
}


def shingles(text, n=NGRAM):
    words = re.findall(r'[a-z0-9]+', text.lower())
    return {' '.join(words[i:i+n]) for i in range(len(words)-n+1)}


def leakage(folder, task_texts):
    """Verbatim task text, secrets, literal answers and grader/solution references."""
    folder = Path(folder)
    task_grams = set().union(*(shingles(t) for t in task_texts)) if task_texts else set()
    findings = []
    for rel in portable.files(folder):
        text = (folder/rel).read_text()
        overlap = sorted(shingles(text) & task_grams)
        if overlap:
            findings.append({'file': rel, 'kind': 'task_text_overlap', 'examples': overlap[:3], 'count': len(overlap)})
        for pattern in SECRET_PATTERNS:
            if re.search(pattern, text):
                findings.append({'file': rel, 'kind': 'credential_pattern', 'pattern': pattern})
        if re.search(LITERAL_COMPOSITION, text):
            findings.append({'file': rel, 'kind': 'literal_composition'})
        for pattern in FORBIDDEN_REFERENCES:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                findings.append({'file': rel, 'kind': 'forbidden_reference', 'match': match.group(0)})
    return findings


def _sandbox(folder, image, argv, stdin, timeout):
    command = ['docker', 'run', '--rm', '-i', '--network', 'none', '--user', f'{os.getuid()}:{os.getgid()}',
               '--memory', '2g', '--cpus', '2', '--tmpfs', '/tmp:rw,mode=1777', '-e', 'HOME=/tmp', '-w', '/tmp',
               '-v', f'{Path(folder).resolve()}:{portable.RUNTIME_ROOT}:ro', '--entrypoint', argv[0], image, *argv[1:]]
    try:
        result = subprocess.run(command, input=stdin, text=True, capture_output=True, timeout=timeout+30)
        return result.returncode, result.stdout[-2000:], result.stderr[-2000:]
    except subprocess.TimeoutExpired:
        return None, '', f'timed out after {timeout}s'


def smoke(folder, image, sandbox=_sandbox):
    checks = []
    for test in portable.read_smoke(folder):
        timeout = test.get('timeout', 60)
        code, out, err = sandbox(folder, image, [test['command'], *test['args']], test.get('stdin', ''), timeout)
        checks.append({'check': 'smoke:'+test['name'], 'passed': code == test.get('expect_exit', 0),
                       'exit': code, 'stdout': out, 'stderr': err})
    for name, server in sorted(portable.read_mcp(folder).items()):
        code, out, err = sandbox(folder, image, ['python3', '-c', MCP_PROBE, server['command'], *server['args']], '', 30)
        checks.append({'check': 'mcp:'+name, 'passed': code == 0, 'exit': code, 'stdout': out, 'stderr': err})
    for event, entries in sorted(portable.read_hooks(folder).items()):
        for i, entry in enumerate(entries):
            code, out, err = sandbox(folder, image, [entry['command'], *entry['args']],
                                     json.dumps(HOOK_EVENT_SAMPLES[event]), entry.get('timeout', 30))
            # Exit 2 is a legitimate "block" decision for native hooks.
            checks.append({'check': f'hook:{event}[{i}]', 'passed': code in (0, 2), 'exit': code, 'stdout': out, 'stderr': err})
    return checks


def run(folder, capabilities, task_texts, image, sandbox=_sandbox):
    """Returns a report; `passed` is False with actionable errors for the proposer."""
    errors = portable.validate(folder, capabilities)
    report = {'static_errors': errors, 'leakage': [], 'smoke': []}
    if not errors:
        report['leakage'] = leakage(folder, task_texts)
        report['smoke'] = smoke(folder, image, sandbox) if not report['leakage'] else []
    failed_smoke = [c for c in report['smoke'] if not c['passed']]
    report['passed'] = not errors and not report['leakage'] and not failed_smoke
    report['errors'] = errors + [f"{f['file']}: {f['kind']}" + (f" ({f.get('match') or f.get('examples')})" if f.get('match') or f.get('examples') else '')
                                 for f in report['leakage']] + [
                                 f"{c['check']} failed (exit {c['exit']}): {c['stderr'][-400:]}" for c in failed_smoke]
    return report
