"""One fresh native Harbor job. No implicit retries or continuation."""
import argparse
import asyncio
import json
import os
from pathlib import Path
from job_spec import ROOT, build
from subscription_auth import subscription_environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--domain', choices=['biology','chemistry','all'], required=True)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--attempts', type=int, default=1)
    args = parser.parse_args()
    experiment = json.loads((ROOT/'config/experiment.json').read_text())
    if experiment.get('budget_status') != 'subscription_only_authorized':
        raise RuntimeError('Subscription-only authorization not recorded')
    if not args.name.replace('-', '').replace('_', '').isalnum():
        raise ValueError('Invalid job name')
    destination = ROOT/'runs/jobs'/args.name
    if destination.exists():
        raise RuntimeError('Job already exists; will not resume or overwrite')
    tasks = experiment['evolve'] if args.domain == 'all' else experiment['domains'][args.domain]
    spec = build('candidate' if args.bundle else 'baseline', tasks[0], args.bundle, args.attempts)
    spec['tasks'] = [{'path': str(ROOT/'external/as-bench/tasks'/task)} for task in tasks]
    spec.update(job_name=args.name, n_concurrent_trials=2, retry={'max_retries':0})
    from harbor.models.job.config import JobConfig
    from harbor.job import Job
    config = JobConfig(**spec)
    env, usage = subscription_environment()
    for name in list(os.environ):
        if name not in env:
            del os.environ[name]
    os.environ.update(env)
    record = ROOT/'runs/launches'/args.name
    record.mkdir(parents=True, exist_ok=False)
    (record/'config.json').write_text(json.dumps(spec, indent=2)+'\n')
    (record/'usage-before.json').write_text(json.dumps(usage, indent=2)+'\n')
    print('Starting fresh subscription-only job:', args.name, flush=True)
    result = asyncio.run(Job(config).run())
    (record/'job-result.json').write_text(result.model_dump_json(indent=2))
    print('Job finished:', args.name, flush=True)


if __name__ == '__main__':
    main()
