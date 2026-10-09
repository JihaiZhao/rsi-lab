"""Harbor's native Codex with a portable bundle loaded. Fixed controller code."""
import json
from pathlib import Path

from harbor.agents.installed.codex import Codex
from harbor.models.task.config import MCPServerConfig

from rsi import bundle as portable
from rsi.runtimes.codex import CAPABILITIES


class PortableCodex(Codex):
    @staticmethod
    def name():
        return 'codex-rsi-portable'

    def __init__(self, logs_dir, harness_dir, harness_sha256, **kwargs):
        self.bundle = Path(harness_dir).resolve()
        errors = portable.validate(self.bundle, CAPABILITIES)
        if errors or portable.bundle_hash(self.bundle) != harness_sha256:
            raise ValueError('Invalid or changed candidate bundle: '+'; '.join(errors))
        self.bundle_sha = harness_sha256
        kwargs['config'] = {
            'model_reasoning_effort': kwargs.get('reasoning_effort', 'max'),
            'forced_login_method': 'chatgpt',
            'web_search': 'disabled',
            'developer_instructions': portable.entry_prompt(
                self.bundle, 'Do not invoke additional models or change model providers.'),
            'features': {'multi_agent': False},
        }
        kwargs['skills_dir'] = portable.RUNTIME_ROOT+'/skills'
        servers = [MCPServerConfig(**s) for s in portable.mcp_servers(self.bundle)]
        if servers:
            kwargs['mcp_servers'] = [*(kwargs.get('mcp_servers') or []), *servers]
        super().__init__(logs_dir=logs_dir, **kwargs)

    async def install(self, environment):
        from cached_codex_runtime import install_cached_runtime
        await install_cached_runtime(environment, self.logs_dir)

    async def setup(self, environment):
        await super().setup(environment)
        await environment.exec(command='mkdir -p '+portable.RUNTIME_ROOT, user='root')
        await environment.upload_dir(self.bundle, portable.RUNTIME_ROOT)
        await environment.exec(command='chmod -R a+rX '+portable.RUNTIME_ROOT, user='root')
        (self.logs_dir/'harness.json').write_text(json.dumps({
            'sha256': self.bundle_sha, 'source': str(self.bundle), 'format': 'portable-v2',
            'native_agent': 'harbor.agents.installed.codex.Codex',
            'components': portable.components(self.bundle), 'files': portable.files(self.bundle)}, indent=2))
