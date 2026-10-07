import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from job_spec import build


class StartTests(unittest.TestCase):
    def test_bare_baseline_is_not_an_extended_candidate(self):
        config=build('baseline','biology/jewett-lab/biosensor-active-learning')
        agent=config['agents'][0]
        self.assertEqual(agent['name'],'claude-code')
        self.assertNotIn('import_path',agent)
        self.assertNotIn('harness_dir',agent['kwargs'])
        self.assertNotIn('append_system_prompt',agent['kwargs'])
        self.assertNotIn('extra_env',agent['kwargs'])
        self.assertEqual(set(agent['env'].values()),{'claude-sonnet-5-5'})
        self.assertEqual(agent['kwargs']['version'],'2.1.293')
        with self.assertRaises(ValueError):build('baseline','example',ROOT/'harness/working')

    def test_candidate_preserves_model_and_pins_source(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'instructions.md').write_text('Check predictions against observed measurements.')
            agent=build('candidate','example',p)['agents'][0]
            self.assertIsNone(agent['name'])
            self.assertEqual(agent['model_name'],'claude-sonnet-5-5')
            self.assertEqual(agent['import_path'],'native_agent:RSIClaudeCode')
            first=agent['kwargs']['harness_sha256']
            (p/'instructions.md').write_text('Changed mechanism')
            self.assertNotEqual(first,build('candidate','example',p)['agents'][0]['kwargs']['harness_sha256'])

    def test_clean_start_and_immutable_h0(self):
        config=json.loads((ROOT/'config/experiment.json').read_text())
        self.assertIn(config['status'],{'preparing_budget_pending','ready','running','complete','failed'})
        self.assertEqual(config['ood'],[])
        self.assertEqual(len(config['evolve']),4)
        self.assertEqual(set(config['model_roles'].values()),{'claude-sonnet-5-5'})
        self.assertEqual((ROOT/'harness/working/instructions.md').read_text(),'')
        provenance=json.loads((ROOT/'harness/H0/provenance.json').read_text())
        for file,sha in provenance['h0_files'].items():
            self.assertEqual(hashlib.sha256((ROOT/file).read_bytes()).hexdigest(),sha)

    def test_harbor_factory_builds_both_arms_without_running(self):
        try:
            from harbor.agents.factory import AgentFactory
            from harbor.models.trial.config import AgentConfig
            from harbor.agents.installed.claude_code import ClaudeCode
            from native_agent import RSIClaudeCode
        except ImportError:
            self.skipTest('Install pinned Harbor in Python 3.12 for adapter integration test')
        with tempfile.TemporaryDirectory() as d:
            for arm in ['baseline','candidate']:
                config=build(arm,'example',ROOT/'harness/working' if arm=='candidate' else None)
                agent=AgentFactory.create_agent_from_config(AgentConfig(**config['agents'][0]),logs_dir=Path(d)/arm)
                self.assertIs(type(agent).run,ClaudeCode.run)
                self.assertEqual(agent.version(),'2.1.293')
                self.assertEqual(isinstance(agent,RSIClaudeCode),arm=='candidate')


if __name__=='__main__':unittest.main()
