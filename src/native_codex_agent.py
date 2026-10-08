"""Fixed native Codex bridge; retain Harbor's native Codex.run conversation/tool loop."""
from pathlib import Path
from harbor.agents.installed.codex import Codex
from native_bundle import bundle_hash, validate_bundle


class RSICodex(Codex):
    @staticmethod
    def name():
        return 'codex-rsi'

    def __init__(self, logs_dir, harness_dir, harness_sha256, **kwargs):
        self.bundle = Path(harness_dir).resolve()
        errors = validate_bundle(self.bundle)
        if errors or bundle_hash(self.bundle) != harness_sha256:
            raise ValueError('Invalid or changed Bio candidate bundle')
        if (self.bundle / 'settings.json').exists():
            raise ValueError('Claude-specific hook settings are not supported by the Codex bridge')
        kwargs['config'] = {
            'model_reasoning_effort': 'max',
            'forced_login_method': 'chatgpt',
            'web_search': 'disabled',
            'developer_instructions': (self.bundle / 'instructions.md').read_text() +
                '\nReusable harness files are in /opt/rsi-harness. Follow the official task rules and budgets. '
                'Only use supplied public task data and in-episode measurements. Do not seek solutions. '
                'Do not invoke additional models or change model providers.',
            'features': {'multi_agent': False},
        }
        kwargs['skills_dir'] = '/opt/rsi-harness/skills'
        super().__init__(logs_dir=logs_dir, **kwargs)

    async def install(self, environment):
        from cached_codex_runtime import install_cached_runtime
        await install_cached_runtime(environment, self.logs_dir)

    async def setup(self, environment):
        await super().setup(environment)
        await environment.exec(command='mkdir -p /opt/rsi-harness', user='root')
        await environment.upload_dir(self.bundle, '/opt/rsi-harness')
        await environment.exec(command='chmod -R a+rX /opt/rsi-harness', user='root')
