"""Use existing ChatGPT login only, with no API-key fallback."""
import json
import os
from pathlib import Path


def codex_subscription_environment():
    path = Path.home() / '.codex/auth.json'
    auth = json.loads(path.read_text())
    if auth.get('auth_mode') != 'chatgpt' or not auth.get('tokens') or auth.get('OPENAI_API_KEY'):
        raise RuntimeError('Bio requires an existing ChatGPT subscription login without API-key auth')
    env = {k: v for k, v in os.environ.items() if not k.startswith(('OPENAI_', 'AZURE_OPENAI_', 'ANTHROPIC_'))
           and k not in {'CODEX_API_KEY', 'CLAUDE_CODE_OAUTH_TOKEN', 'CODEX_AUTH_JSON_PATH'}}
    env['CODEX_FORCE_AUTH_JSON'] = '1'
    return env, {'auth_method': 'chatgpt_subscription', 'api_key_fallback': False}
