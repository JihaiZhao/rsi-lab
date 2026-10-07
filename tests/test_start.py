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

    def test_clean_paused_start_and_immutable_h0(self):
        config=json.loads((ROOT/'config/experiment.json').read_text())
        self.assertEqual(config['status'],'paused_for_design')
        self.assertEqual(set(config['model_roles'].values()),{'claude-sonnet-5-5'})
        self.assertIsNone(config['acceptance_rule'])
        self.assertEqual((ROOT/'harness/working/instructions.md').read_text(),'')
        provenance=json.loads((ROOT/'harness/H0/provenance.json').read_text())
        for file,sha in provenance['h0_files'].items():
            self.assertEqual(hashlib.sha256((ROOT/file).read_bytes()).hexdigest(),sha)


if __name__=='__main__':unittest.main()
