import json
from pathlib import Path
import random
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from rsi import bundle as portable, evidence, gate, plan as contract, selection
from rsi.controller import Experiment, authorized, check_config
from rsi.runtimes import claude_code, codex

TASKS = ['propylene-active-learning', 'suzuki-condition-screen']


def write(root, rel, text):
    path = Path(root)/rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if isinstance(text, str) else json.dumps(text))


def row(task, reward, i, path='/nonexistent', tokens=1000):
    return {'task': task, 'trial': f'{task}__{i}', 'reward': reward, 'exception': None, 'model_audit_error': False,
            'api_error': False, 'agent_result': {'n_input_tokens': tokens, 'n_output_tokens': 0}, 'path': path}


def rows(passes_by_task, n=3, tokens=1000):
    return [row(t, int(i < passes_by_task[t]), i, tokens=tokens) for t in TASKS for i in range(n)]


class BundleTests(unittest.TestCase):
    def test_empty_working_bundle_is_valid_everywhere(self):
        for adapter in (claude_code, codex):
            self.assertEqual(portable.validate(ROOT/'harness/working', adapter.CAPABILITIES), [])
        self.assertEqual(portable.components(ROOT/'harness/working'), [])

    def test_runtime_specific_settings_and_unknown_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            write(d, 'instructions.md', '')
            write(d, 'settings.json', {'hooks': {}})
            write(d, 'notes.md', 'x')
            errors = portable.validate(d, claude_code.CAPABILITIES)
            self.assertTrue(any('settings.json' in e for e in errors))
            self.assertTrue(any('notes.md' in e for e in errors))

    def test_hooks_compile_for_claude_and_are_refused_by_codex(self):
        with tempfile.TemporaryDirectory() as d:
            write(d, 'instructions.md', 'Use the checker.')
            write(d, 'tools/check.py', 'print(1)\n')
            write(d, 'hooks.json', {'stop': [{'command': 'python3', 'args': ['/opt/rsi-harness/tools/check.py']}],
                                    'pre_tool': [{'command': 'python3', 'args': ['/opt/rsi-harness/tools/check.py'],
                                                  'matcher': 'Bash', 'timeout': 10}]})
            write(d, 'smoke.json', [{'name': 'runs', 'command': 'python3', 'args': ['/opt/rsi-harness/tools/check.py']}])
            self.assertEqual(portable.validate(d, claude_code.CAPABILITIES), [])
            self.assertTrue(any("'hook'" in e for e in portable.validate(d, codex.CAPABILITIES)))
            settings = portable.claude_settings(d)
            self.assertEqual(settings['hooks']['Stop'][0]['hooks'][0]['command'],
                             'python3 /opt/rsi-harness/tools/check.py')
            self.assertEqual(settings['hooks']['PreToolUse'][0]['matcher'], 'Bash')
            self.assertEqual(portable.components(d), ['hook', 'instructions', 'tool'])

    def test_executables_need_smoke_tests_and_scripts_must_stay_in_bundle(self):
        with tempfile.TemporaryDirectory() as d:
            write(d, 'instructions.md', '')
            write(d, 'mcp/servers.json', {'calc': {'command': 'bash', 'args': ['/etc/passwd']}})
            write(d, 'mcp/calc.py', 'pass\n')
            errors = portable.validate(d, codex.CAPABILITIES)
            self.assertTrue(any('command must be' in e for e in errors))
            self.assertTrue(any('under /opt/rsi-harness' in e for e in errors))
            self.assertTrue(any('smoke.json' in e for e in errors))

    def test_emptied_files_are_deleted_but_instructions_stay(self):
        with tempfile.TemporaryDirectory() as d:
            write(d, 'instructions.md', '')
            write(d, 'tools/fixtures/x.js', '  \n')
            write(d, 'tools/a.py', 'print(1)\n')
            self.assertEqual(portable.apply_deletions(d), ['tools/fixtures/x.js'])
            self.assertEqual(portable.files(d), ['instructions.md', 'tools/a.py'])
            self.assertFalse((Path(d)/'tools/fixtures').exists())

    def test_mcp_servers_are_portable(self):
        with tempfile.TemporaryDirectory() as d:
            write(d, 'mcp/servers.json', {'calc': {'command': 'python3', 'args': ['/opt/rsi-harness/mcp/calc.py']}})
            self.assertEqual(portable.mcp_servers(d), [{'name': 'calc', 'transport': 'stdio', 'command': 'python3',
                                                        'args': ['/opt/rsi-harness/mcp/calc.py']}])


class GateTests(unittest.TestCase):
    def test_leakage_flags_task_text_and_secrets_not_chemistry_words(self):
        task = 'Design dilute copper alloy electrocatalysts for carbon dioxide conversion over three rounds of synthesis'
        with tempfile.TemporaryDirectory() as d:
            write(d, 'instructions.md', 'Prepare the solution carefully and check the verifier-free constraints.')
            self.assertEqual(gate.leakage(d, [task]), [])
            write(d, 'memory/a.md', 'design dilute copper alloy electrocatalysts for carbon dioxide conversion')
            write(d, 'memory/b.md', 'token sk-ant-abcdefghijklmnop')
            write(d, 'smoke.json', [{'stdin': 'item\nCu-0.98-In-0.02,1'}])
            kinds = {(f['file'], f['kind']) for f in gate.leakage(d, [task])}
            self.assertIn(('memory/a.md', 'task_text_overlap'), kinds)
            self.assertIn(('memory/b.md', 'credential_pattern'), kinds)
            self.assertIn(('smoke.json', 'literal_composition'), kinds)

    def test_smoke_runs_tests_mcp_probe_and_hooks(self):
        calls = []

        def sandbox(folder, image, argv, stdin, timeout):
            calls.append(argv)
            return (1, '', 'boom') if argv[-1].endswith('bad.py') else (0, 'ok', '')
        with tempfile.TemporaryDirectory() as d:
            write(d, 'instructions.md', '')
            write(d, 'tools/good.py', 'print(1)\n')
            write(d, 'tools/bad.py', 'raise SystemExit(1)\n')
            write(d, 'mcp/servers.json', {'calc': {'command': 'python3', 'args': ['/opt/rsi-harness/tools/good.py']}})
            write(d, 'hooks.json', {'stop': [{'command': 'python3', 'args': ['/opt/rsi-harness/tools/bad.py']}]})
            write(d, 'smoke.json', [{'name': 'good', 'command': 'python3', 'args': ['/opt/rsi-harness/tools/good.py']}])
            report = gate.run(d, claude_code.CAPABILITIES, [], 'image', sandbox=sandbox)
            self.assertFalse(report['passed'])
            self.assertEqual([c['check'] for c in report['smoke']], ['smoke:good', 'mcp:calc', 'hook:stop[0]'])
            self.assertTrue(any('hook:stop[0] failed' in e for e in report['errors']))
            self.assertEqual(calls[1][:2], ['python3', '-c'])


class SelectionTests(unittest.TestCase):
    def test_posterior_matches_monte_carlo(self):
        rng = random.Random(0)
        for s1, s0 in [(4, 2), (3, 3), (6, 0), (1, 5)]:
            mc = sum(rng.betavariate(1+s1, 7-s1) > rng.betavariate(1+s0, 7-s0) for _ in range(40000))/40000
            self.assertAlmostEqual(selection.p_superior(s1, 6, s0, 6), mc, delta=0.01)

    def test_first_candidate_becomes_measured_incumbent(self):
        d = selection.decide([], rows({TASKS[0]: 0, TASKS[1]: 0}), best_score=None,
                             incumbent_complexity=0, candidate_complexity=10)
        self.assertTrue(d['accepted'])
        self.assertEqual(d['reason'], 'first_measured_incumbent')
        self.assertFalse(d['paired_local_improvement_claim'])

    def test_one_extra_pass_is_not_credible_but_two_are(self):
        parent = rows({TASKS[0]: 1, TASKS[1]: 1})
        one = selection.decide(parent, rows({TASKS[0]: 2, TASKS[1]: 1}), best_score=2/6,
                               incumbent_complexity=10, candidate_complexity=20)
        two = selection.decide(parent, rows({TASKS[0]: 2, TASKS[1]: 2}), best_score=2/6,
                               incumbent_complexity=10, candidate_complexity=20)
        self.assertEqual((one['accepted'], one['reason']), (False, 'unresolved_in_noise_band'))
        self.assertEqual((two['accepted'], two['reason']), (True, 'credible_gain'))

    def test_in_band_prefers_simpler_or_cheaper_and_floor_blocks_drift(self):
        parent = rows({TASKS[0]: 2, TASKS[1]: 1}, tokens=1000)
        simpler = selection.decide(parent, rows({TASKS[0]: 1, TASKS[1]: 1}), best_score=3/6,
                                   incumbent_complexity=50, candidate_complexity=20)
        cheaper = selection.decide(parent, rows({TASKS[0]: 2, TASKS[1]: 1}, tokens=800), best_score=3/6,
                                   incumbent_complexity=50, candidate_complexity=50)
        floor = selection.decide(parent, rows({TASKS[0]: 1, TASKS[1]: 1}), best_score=4/6,
                                 incumbent_complexity=50, candidate_complexity=20)
        self.assertEqual(simpler['reason'], 'in_band_simpler')
        self.assertEqual(cheaper['reason'], 'in_band_cheaper_not_more_complex')
        self.assertEqual((floor['accepted'], floor['reason']), (False, 'below_noise_floor_of_best'))

    def test_screen_and_completeness(self):
        working = rows({TASKS[0]: 2, TASKS[1]: 1})
        self.assertEqual(selection.continue_after_screen(rows({TASKS[0]: 0, TASKS[1]: 0}, n=1), working)[0], False)
        self.assertEqual(selection.continue_after_screen(rows({TASKS[0]: 1, TASKS[1]: 0}, n=1), working)[0], True)
        self.assertEqual(selection.continue_after_screen(rows({TASKS[0]: 0, TASKS[1]: 0}, n=1), [])[0], True)
        broken = rows({TASKS[0]: 1, TASKS[1]: 1})
        broken[0]['api_error'] = True
        with self.assertRaises(ValueError):
            selection.check_complete(broken, TASKS, 3)


class PlanAndEvidenceTests(unittest.TestCase):
    def plan(self, *components):
        return {'edits': [{'component': c, 'hypothesis': 'h', 'files': [f]} for c, f in components],
                'exploration_waiver': '', 'predictions': {'tasks': {TASKS[0]: 'improve', TASKS[1]: 'same'},
                                                          'token_effect': 'same'}}

    def test_budget_declared_files_and_stall_exploration(self):
        guidance = contract.directive([], 1, claude_code.CAPABILITIES)
        plan = self.plan(('tool', 'tools/a.py'), ('instructions', 'instructions.md'))
        self.assertTrue(any('budget' in e for e in contract.validate(plan, 1, claude_code.CAPABILITIES, guidance)))
        one = self.plan(('tool', 'tools/a.py'))
        self.assertEqual(contract.validate_implementation(one, ['tools/a.py', 'smoke.json', 'instructions.md']), [])
        self.assertIn('Undeclared change: memory/x.md', contract.validate_implementation(one, ['tools/a.py', 'memory/x.md']))
        self.assertEqual(contract.validate_implementation(one, ['tools/a.py', 'tools/fixtures/model.js']), [])
        self.assertIn('Planned tool edit has no matching file change', contract.validate_implementation(one, ['instructions.md']))
        history = [{'trials': 6, 'accepted': False, 'reason': 'regression', 'components_changed': ['instructions']},
                   {'trials': 6, 'accepted': False, 'reason': 'unresolved_in_noise_band', 'components_changed': ['instructions']}]
        stalled = contract.directive(history, 1, claude_code.CAPABILITIES)
        self.assertTrue(stalled['require_untried_component_or_waiver'])
        retry = self.plan(('instructions', 'instructions.md'))
        self.assertTrue(contract.validate(retry, 1, claude_code.CAPABILITIES, stalled))
        retry['exploration_waiver'] = 'Trial 2 step 40 shows the instruction was never read.'
        self.assertEqual(contract.validate(retry, 1, claude_code.CAPABILITIES, stalled), [])

    def test_schema_requires_a_prediction_for_every_task(self):
        schema = contract.schema(TASKS, claude_code.CAPABILITIES.components)
        self.assertEqual(schema['properties']['predictions']['properties']['tasks']['required'], TASKS)

    def test_trial_card_from_atif(self):
        with tempfile.TemporaryDirectory() as d:
            trajectory = {'steps': [
                {'step_id': '1', 'timestamp': '2026-10-08T18:10:00Z', 'source': 'user', 'message': 'task'},
                {'step_id': '2', 'timestamp': '2026-10-08T18:12:30Z', 'source': 'agent', 'message': 'run',
                 'tool_calls': [{'function_name': 'Bash', 'arguments': {'command': 'python3 /opt/rsi-harness/tools/a.py'}},
                                {'function_name': 'mcp__calc__fit', 'arguments': {}}],
                 'observation': {'results': [{'content': 'Traceback (most recent call last):\n ValueError: bad'}]}},
                {'step_id': '3', 'timestamp': '2026-10-08T18:15:00Z', 'source': 'agent', 'message': 'final answer'}]}
            write(d, 'agent/trajectory.json', trajectory)
            card = evidence.trial_card(row(TASKS[0], 1, 0, path=d), ['tools/a.py'])
            self.assertEqual(card['tool_calls'], 2)
            self.assertEqual(card['harness_references'], ['mcp:calc', 'tools/a.py'])
            self.assertEqual(card['duration_seconds'], 300)
            self.assertEqual(len(card['observed_errors']), 1)
            self.assertEqual(card['final_message_excerpt'], 'final answer')

    def test_prediction_scoreboard(self):
        plan = self.plan(('tool', 'tools/a.py'))
        score = evidence.score_predictions(plan, {TASKS[0]: 1/3, TASKS[1]: 2/3}, {TASKS[0]: 2/3, TASKS[1]: 1/3})
        self.assertEqual(score, {'hits': 1, 'total': 2, 'unpredicted_regressions': [TASKS[1]]})


class BridgeTests(unittest.TestCase):
    def test_harbor_builds_both_portable_bridges_without_running(self):
        try:
            from harbor.agents.factory import AgentFactory
            from harbor.agents.installed.claude_code import ClaudeCode
            from harbor.agents.installed.codex import Codex
            from harbor.models.trial.config import AgentConfig
        except ImportError:
            self.skipTest('Install pinned Harbor in Python 3.12 for adapter integration test')
        with tempfile.TemporaryDirectory() as d:
            write(d, 'b/instructions.md', 'Check constraints.')
            write(d, 'b/tools/check.py', 'print(1)\n')
            write(d, 'b/mcp/servers.json', {'calc': {'command': 'python3', 'args': ['/opt/rsi-harness/tools/check.py']}})
            write(d, 'b/smoke.json', [{'name': 'runs', 'command': 'python3', 'args': ['/opt/rsi-harness/tools/check.py']}])
            bundle = Path(d)/'b'
            sha = portable.bundle_hash(bundle)
            claude = AgentFactory.create_agent_from_config(AgentConfig(**claude_code.agent_spec(
                bundle, sha, {'model': 'claude-sonnet-5-5', 'effort': 'high'})), logs_dir=Path(d)/'claude')
            self.assertIs(type(claude).run, ClaudeCode.run)
            self.assertEqual(claude.version(), '2.1.293')
            self.assertEqual([s.name for s in claude.mcp_servers], ['calc'])
            self.assertEqual(claude._extra_env['CLAUDE_CODE_SUBAGENT_MODEL'], 'claude-sonnet-5-5')
            agent = AgentFactory.create_agent_from_config(AgentConfig(**codex.agent_spec(
                bundle, sha, {'model': 'gpt-5.6-luna', 'effort': 'max'})), logs_dir=Path(d)/'codex')
            self.assertIs(type(agent).run, Codex.run)
            self.assertEqual([s.name for s in agent.mcp_servers], ['calc'])
            with self.assertRaises(ValueError):
                claude_code.agent_spec(bundle, sha, {'model': 'claude-opus-5-5', 'effort': 'high'})


class ControllerTests(unittest.TestCase):
    def test_shipped_config_is_valid_and_single_model(self):
        config = json.loads((ROOT/'config/chem-sonnet-v2.json').read_text())
        check_config(config)
        self.assertEqual({config['runtimes']['policy']['model'], config['runtimes']['roles']['model']},
                         {'claude-sonnet-5-5'})
        self.assertEqual(config['selection'].keys(), selection.DEFAULTS.keys())

    @unittest.skipUnless((ROOT/'external/as-bench/tasks/chemistry').exists(), 'AS-Bench checkout required')
    def test_full_loop_with_fake_roles_and_trials(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            config = json.loads((ROOT/'config/chem-sonnet-v2.json').read_text())
            config.update(status='authorized', budget_status='subscription_only_authorized', rounds=3,
                          edit_budget=[1, 1, 1], max_repairs=1)
            write(d, 'config.json', config)
            exp = Experiment(d/'config.json')
            exp.root = d/'exp'
            outcomes = iter([{TASKS[0]: 1, TASKS[1]: 0}, {TASKS[0]: 2, TASKS[1]: 1}, {TASKS[0]: 0, TASKS[1]: 0}])
            critic_calls = []

            def role(name, directory, prompt, writable=False, schema=None):
                if name == 'planner':
                    return {'structured_output': {'problem': 'p', 'evidence': [{'source': 's', 'location': 'l', 'observation': 'o'}],
                            'edits': [{'component': 'instructions', 'hypothesis': 'h', 'files': ['instructions.md']}],
                            'predictions': {'tasks': {TASKS[0]: 'improve', TASKS[1]: 'same'}, 'token_effect': 'same'},
                            'why_not_simpler': '', 'regression_risk': '', 'retroactive_check': '', 'exploration_waiver': 'w'}}
                if name.startswith('proposer'):
                    self.assertTrue(writable)
                    path = directory/'candidate/instructions.md'
                    path.write_text(path.read_text()+f'Check constraints before submitting ({directory.name}).\n')
                if name.startswith('critic'):
                    critic_calls.append(name)
                    first = directory.name == 'round-02' and name == 'critic-0'
                    return {'structured_output': {'approved': not first, 'reasons': ['r'] if first else [],
                                                  'required_fixes': ['fix'] if first else []}}
                return {'result': 'analysis'}

            def evaluate(name, bundle, attempts):
                if name.endswith('screen'):
                    self.pending = next(outcomes)
                    return [row(t, int(self.pending[t] > 0), name, path=str(d)) for t in TASKS]
                rest = {t: self.pending[t]-int(self.pending[t] > 0) for t in TASKS}
                return [row(t, int(i < rest[t]), f'{name}-{i}', path=str(d)) for t in TASKS for i in range(attempts)]
            exp.role, exp.evaluate, exp.preflight = role, evaluate, lambda: None
            exp.run()
            history = json.loads((exp.root/'history.json').read_text())
            self.assertEqual([h['reason'] for h in history],
                             ['first_measured_incumbent', 'credible_gain', 'screened_out'])
            self.assertEqual(history[2]['trials'], 2)
            self.assertIn('critic-1', critic_calls)  # Round 2 was repaired after a critic rejection.
            selected = json.loads((exp.root/'selected.json').read_text())
            self.assertTrue(selected['bundle'].endswith('archive/round-02/candidate'))
            self.assertTrue((exp.root/'archive/round-03/trials').exists())
            self.assertTrue((exp.root/'round-03/evidence/archive/round-02/decision.json').exists())
            ledger = json.loads((exp.root/'hypotheses.json').read_text())
            self.assertEqual([h['status'] for h in ledger], ['measured', 'supported', 'refuted_by_screen'])


if __name__ == '__main__':
    unittest.main()
