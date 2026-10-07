"""Export the active Chem experiment for the English research website."""
import json
from datetime import datetime, timezone
from evaluation import collect
from job_spec import ROOT


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def main():
    config = read(ROOT / 'config/experiment.json')
    root = ROOT / 'runs/experiments' / config['experiment_id']
    trials = []
    for job in sorted((root / 'jobs').glob('*')):
        if not job.is_dir():
            continue
        for record in collect(job):
            record.pop('path', None)
            record.pop('error_message', None)
            trials.append(dict(record, job=job.name))
    rounds = []
    roles = []
    for folder in sorted((root / 'evolution/chemistry').glob('*round-*')):
        number = int(folder.name.rsplit('-', 1)[-1])
        calls = {}
        for role in ['analyst', 'proposer', 'critic']:
            call = read(folder / f'{role}-stdout.json', {})
            calls[role] = call
            if call:
                roles.append({'round': number, 'role': role, 'model_usage': call.get('modelUsage'),
                              'usage': call.get('usage'), 'list_price_estimate_usd': call.get('total_cost_usd')})
        diff = folder / 'candidate.diff'
        rounds.append({'number': number, 'proposal': calls['proposer'].get('result'),
                       'analysis': calls['analyst'].get('result'),
                       'critic': calls['critic'].get('structured_output') or calls['critic'].get('result'),
                       'source': read(folder / 'source.json', {}),
                       'decision': read(folder / 'decision.json'),
                       'diff': diff.read_text() if diff.exists() else '',
                       'trials': [t for t in trials if t['job'] == f'chemistry-r{number:02d}-search']})
    selected = read(root / 'evolution/chemistry/selected.json')
    if selected:
        selected.pop('bundle', None)
        selected.pop('history', None)
    export = {'updated_at': datetime.now(timezone.utc).isoformat(), 'experiment_id': config['experiment_id'],
              'protocol': config, 'trials': trials, 'rounds': rounds, 'role_calls': roles,
              'selected': selected, 'stopped': read(root / 'evolution/chemistry/stopped.json'),
              'billing': 'Existing Claude Max subscription only. Dollar estimates are not additional charges.'}
    (ROOT / 'website/dist/experiment.json').write_text(json.dumps(export, ensure_ascii=False, indent=2) + '\n')
    print(f'Exported active experiment: {len(rounds)} rounds, {len(trials)} trial outcomes')


if __name__ == '__main__':
    main()
