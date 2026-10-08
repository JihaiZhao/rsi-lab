import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from codex_evaluation import collect


class CodexAuditTests(unittest.TestCase):
    def collect_contexts(self, contexts, expected_model='gpt-5.6-terra'):
        with tempfile.TemporaryDirectory() as d:
            trial = Path(d) / 'trial'
            sessions = trial / 'agent/sessions'
            sessions.mkdir(parents=True)
            (trial / 'result.json').write_text(json.dumps({
                'trial_name': 'trial', 'task_name': 'public-task',
                'verifier_result': {'rewards': {'reward': 1}}}))
            (sessions / 'session.jsonl').write_text('\n'.join(json.dumps({
                'type': 'turn_context', 'payload': c}) for c in contexts))
            (trial / 'agent/codex.txt').write_text('{"type":"turn.completed"}\n')
            return collect(d, expected_model=expected_model)[0]

    def test_exact_model_and_max_pass(self):
        row = self.collect_contexts([{'model': 'gpt-5.6-terra', 'effort': 'max'}])
        self.assertFalse(row['model_audit_error'])
        self.assertEqual(row['reward'], 1)

    def test_missing_effort_in_any_turn_blocks_selection(self):
        row = self.collect_contexts([{'model': 'gpt-5.6-terra', 'effort': 'max'},
                                     {'model': 'gpt-5.6-terra'}])
        self.assertTrue(row['model_audit_error'])

    def test_wrong_model_blocks_selection(self):
        row = self.collect_contexts([{'model': 'other', 'effort': 'max'}])
        self.assertTrue(row['model_audit_error'])

    def test_no_native_context_blocks_selection(self):
        self.assertTrue(self.collect_contexts([])['model_audit_error'])

    def test_luna_audit_does_not_accept_terra(self):
        self.assertFalse(self.collect_contexts([{"model": "gpt-5.6-luna", "effort": "max"}], "gpt-5.6-luna")["model_audit_error"])
        self.assertTrue(self.collect_contexts([{"model": "gpt-5.6-terra", "effort": "max"}], "gpt-5.6-luna")["model_audit_error"])
