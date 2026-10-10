"""Export one experiment as the website's published snapshot (website/dist/experiment.json).

Framework v2 experiments (configs with a "framework" key) export every round: plan,
gate and critic history, decision with posterior, diff, trials and visible harness
interventions. Older configs keep the original phase-1 export. Only official rewards,
this experiment's own records and candidate source are exported; no trajectories,
credentials or local paths.
"""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from job_spec import ROOT

# Native-log markers that a harness hook actually intervened (exit 2 feedback to the agent).
INTERVENTION = re.compile(r'Stop hook feedback:|PreToolUse:\w+ hook error:|PostToolUse:\w+ hook error:')


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def role_cost(folder, names):
    total, calls = 0.0, 0
    for name in names:
        data = read(folder/f'{name}-stdout.json', {})
        if data.get('total_cost_usd') is not None:
            total += data['total_cost_usd']
            calls += 1
    return {'calls': calls, 'list_price_estimate_usd': round(total, 2)}


def interventions(log):
    """Hook feedback delivered to the agent as a user turn (one per blocking intervention)."""
    count = 0
    for line in log.read_text().splitlines() if log.exists() else []:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get('type') == 'user' and INTERVENTION.search(json.dumps(event.get('message', {}))):
            count += 1
    return count


def trial_rows(root, jobs, runtime):
    from rsi import runtimes
    adapter = runtimes.get(runtime['adapter'])
    rows = []
    for job in jobs:
        for record in adapter.collect(root/'jobs'/job, runtime):
            agent = record.get('agent_result') or {}
            rows.append({'task': record['task'], 'trial': record['trial'], 'job': job, 'reward': int(record['reward']),
                         'model_audit_ok': not record['model_audit_error'], 'harness_interventions': interventions(Path(record['path'])/'agent/claude-code.txt'),
                         'tokens': (agent.get('n_input_tokens') or 0)+(agent.get('n_output_tokens') or 0),
                         'list_price_estimate_usd': agent.get('cost_usd')})
    return rows


def export_v2(config, annotations):
    root = ROOT/'runs/experiments'/config['experiment_id']
    runtime = config['runtimes']['policy']
    history = read(root/'history.json', [])
    selected = read(root/'selected.json') or read(root/'closure.json', {}).get('selected')
    selected_round = None
    if selected:
        match = re.search(r'round-(\d+)', str(selected.get('bundle', '')))
        selected_round = int(match.group(1)) if match else selected.get('round')
    rounds = []
    for item in history:
        n = item['round']
        folder, archive = root/f'round-{n:02d}', root/'archive'/f'round-{n:02d}'
        decision = read(archive/'decision.json', item)
        plan = read(folder/'plan.json') or {}
        attempts = []
        for gate in sorted(folder.glob('gate-*.json'), key=lambda p: int(p.stem.split('-')[1])):
            k = int(gate.stem.split('-')[1])
            report, critic = read(gate), read(folder/f'critic-{k}.json')
            attempts.append({'attempt': k, 'gate_passed': report.get('passed'), 'gate_errors': report.get('errors', []),
                             'critic': critic})
        candidate = archive/'candidate'
        files = {str(p.relative_to(candidate)): p.read_text() for p in sorted(candidate.rglob('*')) if p.is_file()}
        roles = ['analyst', 'planner', 'proposer', *[p.name[:-len('-stdout.json')] for p in sorted(folder.glob('*-stdout.json'))
                                                     if p.name.startswith(('critic-', 'proposer-repair-'))]]
        note = annotations.get('rounds', {}).get(str(n), {})
        rounds.append({
            'round': n, 'title': note.get('title') or ', '.join(item.get('components_changed') or []),
            'summary': note.get('summary', ''), 'observation': note.get('observation', ''),
            'accepted': decision.get('accepted'), 'reason': decision.get('reason'),
            'recorded_offline': decision.get('recorded_offline', False),
            'score': decision.get('score'), 'trials_run': decision.get('trials', 0),
            'task_rates': decision.get('task_rates'), 'p_superior': decision.get('p_superior'),
            'incumbent_score': decision.get('incumbent_score'),
            'tokens_per_trial': decision.get('candidate_tokens_per_trial'),
            'complexity': decision.get('candidate_complexity'), 'edit_budget': item.get('edit_budget'),
            'components_changed': item.get('components_changed'), 'changed_files': item.get('changed_files'),
            'plan': {k: plan.get(k) for k in ('problem', 'edits', 'predictions', 'why_not_simpler', 'regression_risk')},
            'attempts': attempts, 'diff': (archive/'candidate.diff').read_text() if (archive/'candidate.diff').exists() else '',
            'files': files, 'candidate_sha256': item.get('candidate_sha256'), 'parent_sha256': item.get('parent_sha256'),
            'role_cost': role_cost(folder, roles),
            'trials': trial_rows(root, decision.get('jobs', []), runtime) if decision.get('jobs') else []})
    return {
        'schema': 'rsi-v2', 'updated_at': datetime.now(timezone.utc).isoformat(),
        'experiment_id': config['experiment_id'], 'status': 'complete' if (root/'selected.json').exists() else
        ('stopped' if (root/'stopped.json').exists() else 'running'),
        'models': {'policy': runtime, 'roles': {k: v for k, v in config['runtimes']['roles'].items() if k != 'image'}},
        'protocol': {k: config[k] for k in ('tasks', 'rounds', 'trials_per_task', 'screen_trials_per_task',
                                            'edit_budget', 'max_repairs', 'selection', 'reporting')},
        'external_reference': config.get('external_reference'), 'billing': config.get('billing'),
        'selected_round': selected_round, 'selected_sha256': (selected or {}).get('sha256'),
        'notes': annotations.get('notes', []), 'prior_attempts': config.get('prior_attempts', []),
        'rounds': rounds}


def export_legacy(config):
    from evaluation import collect
    root = ROOT/'runs/experiments'/config['experiment_id']
    trials = []
    for job in sorted((root/'jobs').glob('*')):
        if job.is_dir():
            for record in collect(job):
                record.pop('path', None)
                record.pop('error_message', None)
                trials.append(dict(record, job=job.name))
    rounds = []
    for folder in sorted((root/'evolution/chemistry').glob('*round-*')):
        number = int(folder.name.rsplit('-', 1)[-1])
        calls = {role: read(folder/f'{role}-stdout.json', {}) for role in ['analyst', 'proposer', 'critic']}
        diff = folder/'candidate.diff'
        rounds.append({'number': number, 'proposal': calls['proposer'].get('result'),
                       'analysis': calls['analyst'].get('result'),
                       'critic': calls['critic'].get('structured_output') or calls['critic'].get('result'),
                       'source': read(folder/'source.json', {}), 'decision': read(folder/'decision.json'),
                       'diff': diff.read_text() if diff.exists() else '',
                       'trials': [t for t in trials if t['job'] == f'chemistry-r{number:02d}-search']})
    selected = read(root/'evolution/chemistry/selected.json')
    if selected:
        selected.pop('bundle', None)
        selected.pop('history', None)
    return {'updated_at': datetime.now(timezone.utc).isoformat(), 'experiment_id': config['experiment_id'],
            'protocol': config, 'trials': trials, 'rounds': rounds, 'selected': selected,
            'stopped': read(root/'evolution/chemistry/stopped.json')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT/'config/chem-sonnet-v2.json')
    parser.add_argument('--annotations', type=Path, help='Human-written round titles and notes (defaults by experiment id)')
    args = parser.parse_args()
    config = read(args.config)
    if 'framework' not in config:
        export = export_legacy(config)
    else:
        notes = args.annotations or ROOT/'website/annotations'/(config['experiment_id']+'.json')
        export = export_v2(config, read(notes, {}))
        selected = next((r for r in export['rounds'] if r['round'] == export['selected_round']), None)
        if selected:
            (ROOT/'website/dist/selected-harness.md').write_text(
                f"# Selected harness: {config['experiment_id']}, round {selected['round']}\n\n"
                f"sha256 `{selected['candidate_sha256']}`\n\n" +
                ''.join(f"## {name}\n\n```\n{text}\n```\n\n" for name, text in selected['files'].items()))
    text = json.dumps(export, ensure_ascii=False, indent=2)+'\n'
    if str(Path.home()) in text:
        raise RuntimeError('Refusing to publish a local filesystem path')
    (ROOT/'website/dist/experiment.json').write_text(text)
    print(f"Exported {config['experiment_id']}: {len(export['rounds'])} rounds")


if __name__ == '__main__':
    main()
