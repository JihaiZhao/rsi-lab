"""Harbor's native Claude Code, with an archived proposer-authored bundle loaded.

The Claude Code run loop, native tools, budgets and official verifier are unchanged.
This bridge is fixed controller code, never part of the editable bundle.
"""
import json
import shlex
from pathlib import Path
from harbor.agents.installed.claude_code import ClaudeCode
from native_bundle import bundle_hash,validate_bundle

class RSIClaudeCode(ClaudeCode):
    @staticmethod
    def name():return 'claude-code-rsi'

    def __init__(self,logs_dir,harness_dir,harness_sha256,**kwargs):
        self.bundle=Path(harness_dir).resolve()
        errors=validate_bundle(self.bundle)
        if errors:raise ValueError('; '.join(errors))
        if bundle_hash(self.bundle)!=harness_sha256:raise ValueError('Archived harness hash mismatch')
        self.bundle_sha=harness_sha256
        prompt=(self.bundle/'instructions.md').read_text()+(
            '\nYour reusable harness files are in /opt/rsi-harness. '
            'Use only the supplied task data and lab measurements. Do not seek benchmark solutions. '
            'Keep all model calls on the configured Sonnet 5.5 model. '
            'The task instruction and its experiment/time budgets take precedence over harness advice.')
        # Harbor 0.21 interpolates string flag values into a shell command verbatim.
        kwargs['append_system_prompt']=shlex.quote(prompt)
        kwargs['skills_dir']='/opt/rsi-harness/skills'
        settings=self.bundle/'settings.json'
        if settings.exists():kwargs['config']=json.loads(settings.read_text())
        kwargs['extra_env']={**kwargs.get('extra_env',{}),
            'ANTHROPIC_DEFAULT_SONNET_MODEL':'claude-sonnet-5-5',
            'ANTHROPIC_DEFAULT_OPUS_MODEL':'claude-sonnet-5-5',
            'ANTHROPIC_DEFAULT_HAIKU_MODEL':'claude-sonnet-5-5',
            'CLAUDE_CODE_SUBAGENT_MODEL':'claude-sonnet-5-5'}
        super().__init__(logs_dir=logs_dir,**kwargs)

    async def setup(self,environment):
        await super().setup(environment)
        await environment.exec(command='mkdir -p /opt/rsi-harness',user='root')
        await environment.upload_dir(self.bundle,'/opt/rsi-harness')
        await environment.exec(command='chmod -R a+rX /opt/rsi-harness',user='root')
        (self.logs_dir/'harness.json').write_text(json.dumps({
            'sha256':self.bundle_sha,'source':str(self.bundle),
            'native_agent':'harbor.agents.installed.claude_code.ClaudeCode',
            'files':sorted(str(p.relative_to(self.bundle)) for p in self.bundle.rglob('*') if p.is_file())},indent=2))
