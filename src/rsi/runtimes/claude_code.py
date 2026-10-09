"""Native Claude Code adapter: subscription OAuth only, model audited per call."""
import json
import os
import subprocess

from rsi.runtimes import Capabilities
from job_spec import ROOT

CAPABILITIES = Capabilities('claude_code', ('instructions', 'skill', 'tool', 'mcp', 'hook', 'memory'),
    notes='Hooks compile to settings.json; MCP servers register as user-scoped stdio servers.')
MODEL_ENV = ('ANTHROPIC_DEFAULT_SONNET_MODEL', 'ANTHROPIC_DEFAULT_OPUS_MODEL',
             'ANTHROPIC_DEFAULT_HAIKU_MODEL', 'CLAUDE_CODE_SUBAGENT_MODEL')


def subscription(model):
    from subscription_auth import subscription_environment
    env, usage = subscription_environment()
    for key in MODEL_ENV:
        env[key] = model  # Subagents and aliases resolve to the audited model only.
    return env, usage


def preflight(runtime):
    """Fails before anything is created when the login or quota is unusable."""
    subscription(runtime['model'])


def run_role(name, directory, prompt, *, runtime, boundary, writable=False, schema=None):
    """One isolated, non-persistent role call. Raises on any error; never retries."""
    env, usage = subscription(runtime['model'])
    (directory/(name+'-usage-before.json')).write_text(json.dumps(usage, indent=2)+'\n')
    command = ['docker', 'run', '--rm', '--name', 'rsi-'+directory.name+'-'+name,
        '--user', f'{os.getuid()}:{os.getgid()}', '--tmpfs', '/tmp:rw,mode=1777',
        '-e', 'HOME=/tmp/rsi-home', '-e', 'CLAUDE_CONFIG_DIR=/tmp/rsi-home/.claude']
    for key in ('CLAUDE_CODE_OAUTH_TOKEN', *MODEL_ENV):
        command += ['-e', key]
    for folder in ('evidence', 'parent', 'candidate'):
        mode = 'rw' if folder == 'candidate' and writable else 'ro'
        command += ['-v', f'{directory/folder}:/workspace/{folder}:{mode}']
    command += ['-i', runtime['image'], '--print', '--model', runtime['model'],
        '--effort', runtime['effort'], '--output-format', 'json', '--no-session-persistence',
        '--setting-sources', '', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
        '--tools', 'Read,Write,Edit,Glob,Grep' if writable else 'Read,Glob,Grep',
        '--permission-mode', 'bypassPermissions', '--append-system-prompt', boundary]
    if schema:
        command += ['--json-schema', json.dumps(schema)]
    (directory/(name+'-prompt.txt')).write_text(prompt)
    print('Role:', directory.name, name, runtime['model'], flush=True)
    result = subprocess.run(command, input=prompt, text=True, capture_output=True, env=env)
    token = env['CLAUDE_CODE_OAUTH_TOKEN']
    raw = result.stdout.replace(token, '[REDACTED]')
    (directory/(name+'-stdout.json')).write_text(raw)
    (directory/(name+'-stderr.txt')).write_text(result.stderr.replace(token, '[REDACTED]'))
    if result.returncode:
        raise RuntimeError(name+' process failed; preserved without retry')
    try:
        data = json.loads(raw)
    except ValueError as error:
        raise RuntimeError(name+' did not return valid JSON') from error
    if data.get('is_error'):
        raise RuntimeError(name+' model call returned error; inspect archived output')
    models = set((data.get('modelUsage') or {}).keys())
    if not models or models != {runtime['model']}:
        raise RuntimeError('Role model audit failed: '+str(sorted(models)))
    return {'result': data.get('result', ''), 'structured_output': data.get('structured_output'),
            'usage': data.get('usage'), 'cost_usd_list_price': data.get('total_cost_usd')}


def agent_spec(bundle, sha256, runtime):
    """Harbor agent entry for the task policy, pinned to the archived H0 settings."""
    h0 = json.loads((ROOT/'harness/H0/manifest.json').read_text())['agent']
    if runtime['model'] != h0['model_name'] or runtime.get('version', h0['kwargs']['version']) != h0['kwargs']['version']:
        raise ValueError('Claude Code policy must match the archived H0 model and version')
    return {'import_path': 'rsi.runtimes.claude_bridge:PortableClaudeCode', 'model_name': runtime['model'],
            'env': {key: runtime['model'] for key in MODEL_ENV},
            'kwargs': {**h0['kwargs'], 'harness_dir': str(bundle), 'harness_sha256': sha256}}


def policy_environment(runtime):
    return subscription(runtime['model'])


def collect(job_dir, runtime):
    from evaluation import collect as collect_claude
    return collect_claude(job_dir, expected_model=runtime['model'])
