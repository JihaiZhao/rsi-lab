"""Harbor's native Claude Code with a portable bundle compiled in. Fixed controller code.

The Claude Code run loop, native tools, budgets and official verifier are unchanged.
"""
import json
import shlex
from pathlib import Path

from harbor.agents.installed.claude_code import ClaudeCode
from harbor.models.task.config import MCPServerConfig

from rsi import bundle as portable
from rsi.runtimes.claude_code import CAPABILITIES, MODEL_ENV


class PortableClaudeCode(ClaudeCode):
    @staticmethod
    def name():
        return 'claude-code-rsi-portable'

    def __init__(self, logs_dir, harness_dir, harness_sha256, model_name=None, **kwargs):
        self.bundle = Path(harness_dir).resolve()
        errors = portable.validate(self.bundle, CAPABILITIES)
        if errors:
            raise ValueError('; '.join(errors))
        if portable.bundle_hash(self.bundle) != harness_sha256:
            raise ValueError('Archived harness hash mismatch')
        self.bundle_sha = harness_sha256
        prompt = portable.entry_prompt(self.bundle, f'Keep all model calls on the configured {model_name} model.')
        # Harbor interpolates string flag values into a shell command verbatim.
        kwargs['append_system_prompt'] = shlex.quote(prompt)
        kwargs['skills_dir'] = portable.RUNTIME_ROOT+'/skills'
        settings = portable.claude_settings(self.bundle)
        if settings:
            kwargs['config'] = settings
        servers = [MCPServerConfig(**s) for s in portable.mcp_servers(self.bundle)]
        if servers:
            kwargs['mcp_servers'] = [*(kwargs.get('mcp_servers') or []), *servers]
        kwargs['extra_env'] = {**kwargs.get('extra_env', {}), **{key: model_name for key in MODEL_ENV}}
        super().__init__(logs_dir=logs_dir, model_name=model_name, **kwargs)

    async def setup(self, environment):
        await super().setup(environment)
        await environment.exec(command='mkdir -p '+portable.RUNTIME_ROOT, user='root')
        await environment.upload_dir(self.bundle, portable.RUNTIME_ROOT)
        await environment.exec(command='chmod -R a+rX '+portable.RUNTIME_ROOT, user='root')
        (self.logs_dir/'harness.json').write_text(json.dumps({
            'sha256': self.bundle_sha, 'source': str(self.bundle), 'format': 'portable-v2',
            'native_agent': 'harbor.agents.installed.claude_code.ClaudeCode',
            'components': portable.components(self.bundle), 'files': portable.files(self.bundle)}, indent=2))
