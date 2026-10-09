"""Native Codex adapter: ChatGPT subscription only, model and effort audited per call."""
from rsi.runtimes import Capabilities

CAPABILITIES = Capabilities('codex', ('instructions', 'skill', 'tool', 'mcp', 'memory'),
    notes='Lifecycle hooks are not loaded by the pinned Codex bridge.')


def run_role(name, directory, prompt, *, runtime, boundary, writable=False, schema=None):
    from codex_role import role
    if runtime.get('effort', 'max') != 'max':
        raise ValueError('The pinned Codex role runner audits max effort only')
    data = role(name, directory, prompt, schema=schema, boundary=boundary,
                model=runtime['model'], writable=writable)
    return {'result': data.get('result', ''), 'structured_output': data.get('structured_output'),
            'usage': None, 'cost_usd_list_price': None}


def agent_spec(bundle, sha256, runtime):
    return {'import_path': 'rsi.runtimes.codex_bridge:PortableCodex', 'model_name': runtime['model'], 'env': {},
            'kwargs': {'version': runtime.get('version', '0.154.0'), 'reasoning_effort': runtime.get('effort', 'max'),
                       'web_search': 'disabled', 'harness_dir': str(bundle), 'harness_sha256': sha256}}


def policy_environment(runtime):
    from cached_codex_runtime import validate_cache
    from codex_subscription import codex_subscription_environment
    validate_cache()
    return codex_subscription_environment()


def collect(job_dir, runtime):
    from codex_evaluation import collect as collect_codex
    return collect_codex(job_dir, expected_model=runtime['model'])
