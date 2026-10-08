"""Isolated native Codex roles using existing subscription auth only."""
import json
import os
from pathlib import Path
import subprocess

from codex_subscription import codex_subscription_environment

MODEL = 'gpt-5.6-terra'


def role(name, directory, prompt, schema=None, boundary='', model=MODEL):
    env, usage = codex_subscription_environment()
    directory = directory.resolve()
    auth_path = Path.home() / '.codex/auth.json'
    auth = json.loads(auth_path.read_text())
    secrets = [v for v in auth.get('tokens', {}).values() if isinstance(v, str) and v]
    def scrub(value):
        for secret in secrets:
            value = value.replace(secret, '[REDACTED]')
        return value
    output = directory / (name + '-codex')
    output.mkdir()
    (output / 'sessions').mkdir()
    (directory / (name + '-usage-before.json')).write_text(json.dumps(usage))
    (directory / (name + '-prompt.txt')).write_text(prompt)
    command = ['docker', 'run', '--rm', '--name', 'rsi-' + directory.name + '-' + name,
        '--user', f'{os.getuid()}:{os.getgid()}', '--tmpfs', '/tmp:rw,mode=1777', '--tmpfs', '/tmp/codex-home:rw,mode=1777',
        '-e', 'HOME=/tmp', '-e', 'CODEX_HOME=/tmp/codex-home',
        '-v', f'{auth_path}:/tmp/codex-home/auth.json:ro',
        '-v', f'{output}/sessions:/tmp/codex-home/sessions:rw',
        '-v', f'{output}:/role-output:rw']
    for folder in ['evidence', 'parent', 'candidate']:
        mode = 'rw' if folder == 'candidate' and name == 'proposer' else 'ro'
        command += ['-v', f'{directory / folder}:/workspace/{folder}:{mode}']
    if schema:
        (output / 'schema.json').write_text(json.dumps(schema))
    command += ['-i', 'rsi-terra-roles:0.154.0', 'exec',
        '--ignore-user-config', '--ignore-rules', '--skip-git-repo-check',
        '--dangerously-bypass-approvals-and-sandbox', '--model', model,
        '-c', 'model_reasoning_effort="max"', '-c', 'forced_login_method="chatgpt"',
        '-c', 'web_search="disabled"', '-c', 'features.multi_agent=false',
        '-c', 'developer_instructions=' + json.dumps(boundary),
        '--json', '--output-last-message', '/role-output/final.txt']
    if schema:
        command += ['--output-schema', '/role-output/schema.json']
    command += ['-']
    print('Role:', directory.name, name, model, 'max', flush=True)
    events = []
    with (output / 'events.jsonl').open('w') as log:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, env=env)
        process.stdin.write(prompt)
        process.stdin.close()
        for line in process.stdout:
            clean = scrub(line)
            log.write(clean)
            log.flush()
            try:
                events.append(json.loads(clean))
            except ValueError:
                pass
        code = process.wait()
    if code or any(e.get('type') in ('error', 'turn.failed') for e in events):
        raise RuntimeError('Codex role failed; preserved without retry')
    contexts = []
    for path in (output / 'sessions').rglob('*.jsonl'):
        for line in path.read_text().splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get('type') == 'turn_context':
                contexts.append(event['payload'])
    if not contexts or any(c.get('model') != model or c.get('effort', c.get('reasoning_effort')) != 'max' for c in contexts):
        raise RuntimeError('Codex role model/effort audit failed')
    if not any(e.get('type') == 'turn.completed' for e in events):
        raise RuntimeError('Codex role did not complete')
    result = scrub((output / 'final.txt').read_text())
    data = {'result': result, 'modelUsage': {model: {}}, 'reasoning_effort': 'max'}
    if schema:
        data['structured_output'] = json.loads(result)
    (directory / (name + '-stdout.json')).write_text(json.dumps(data, indent=2))
    return data
