"""Load subscription auth into process memory only; never persist credentials."""
import json
import os
from pathlib import Path
import urllib.request


def subscription_environment():
    credentials = json.loads((Path.home()/'.claude/.credentials.json').read_text())
    token = credentials['claudeAiOauth']['accessToken']
    request = urllib.request.Request('https://api.anthropic.com/api/oauth/usage', headers={
        'Authorization': 'Bearer '+token, 'anthropic-beta': 'oauth-2025-04-20'})
    with urllib.request.urlopen(request, timeout=30) as response:
        usage = json.load(response)
    if usage.get('extra_usage', {}).get('is_enabled') is not False:
        raise RuntimeError('Subscription-only run requires extra usage disabled')
    for key in ('five_hour', 'seven_day', 'seven_day_sonnet'):
        window = usage.get(key) or {}
        if window.get('utilization', 0) >= 100:
            raise RuntimeError('Subscription quota exhausted: '+key)
    env = dict(os.environ)
    for name in list(env):
        if name.startswith(('ANTHROPIC_', 'CLAUDE_CODE_USE_')) or name in {'AWS_BEARER_TOKEN_BEDROCK','CLAUDE_CODE_OAUTH_TOKEN'}:
            env.pop(name, None)
    env.update(CLAUDE_CODE_OAUTH_TOKEN=token, CLAUDE_FORCE_OAUTH='1')
    for name in ('ANTHROPIC_DEFAULT_SONNET_MODEL','ANTHROPIC_DEFAULT_OPUS_MODEL',
                 'ANTHROPIC_DEFAULT_HAIKU_MODEL','CLAUDE_CODE_SUBAGENT_MODEL'):
        env[name] = 'claude-sonnet-5-5'
    return env, usage
