"""Explicitly authorized full reevaluation of the unchanged fifth candidate.

This is not an automatic retry. Original job outcomes and stop records stay intact.
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from job_spec import ROOT
from evaluation import collect, accept
from native_bundle import bundle_hash


def main():
    config = json.loads((ROOT / 'config/experiment.json').read_text())
    root = ROOT / 'runs/experiments' / config['experiment_id']
    evolution = root / 'evolution/chemistry'
    candidate = evolution / 'chemistry-round-05/candidate'
    source = json.loads((candidate.parent / 'source.json').read_text())
    if bundle_hash(candidate) != source['candidate_sha256']:
        raise RuntimeError('Round 5 candidate has changed')
    record = evolution / 'round-05-reevaluation.json'
    if record.exists():
        raise RuntimeError('Reevaluation already recorded; no implicit retry')
    job = 'chemistry-r05-user-reevaluation-01'
    state = {'round': 5, 'job': job, 'status': 'running',
             'authorization': 'User explicitly requested rerunning round 5',
             'original_job': 'chemistry-r05-search', 'trials_per_task': 3,
             'candidate_sha256': source['candidate_sha256'],
             'started_at': datetime.now(timezone.utc).isoformat()}
    def save():
        record.write_text(json.dumps(state, indent=2) + '\n')
    save()
    try:
        subprocess.run([sys.executable, str(ROOT / 'src/run_job.py'), '--name', job,
                        '--domain', 'chemistry', '--bundle', str(candidate), '--attempts', '3'], check=True)
        rows = collect(root / 'jobs' / job)
        names = [task.split('/')[-1] for task in config['domains']['chemistry']]
        if any(sum(r['task'] == name for r in rows) != 3 for name in names):
            raise RuntimeError('Missing planned reevaluation trials')
        history = json.loads((evolution / 'history.json').read_text())
        incumbent = next(d for d in reversed(history) if d['accepted'])
        decision = accept(collect(root / 'jobs' / incumbent['job']), rows, names)
        state.update(status='complete', decision=decision,
                     finished_at=datetime.now(timezone.utc).isoformat())
        winner = candidate if decision['accepted'] else evolution / f"chemistry-round-{incumbent['round']:02d}/candidate"
        selected = {'domain': 'chemistry', 'bundle': str(winner), 'sha256': bundle_hash(winner),
                    'selected_round': 5 if decision['accepted'] else incumbent['round'],
                    'job': job if decision['accepted'] else incumbent['job'],
                    'history': history, 'reevaluation': state,
                    'frozen_at': datetime.now(timezone.utc).isoformat()}
        (evolution / 'selected.json').write_text(json.dumps(selected, indent=2) + '\n')
        save()
        print('Reevaluation selection:', json.dumps(decision), flush=True)
    except BaseException as error:
        state.update(status='stopped', error_type=type(error).__name__,
                     message=str(error), finished_at=datetime.now(timezone.utc).isoformat())
        save()
        raise


if __name__ == '__main__':
    main()
