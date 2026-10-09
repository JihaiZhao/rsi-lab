"""One fresh Harbor job for a portable candidate bundle. No implicit retries or continuation.

Runs in its own process because it replaces os.environ with the subscription-only environment.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path

from rsi import bundle as portable, runtimes
from rsi.controller import ROOT, authorized, check_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--attempts', type=int, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    check_config(config)
    if not authorized(config):
        raise RuntimeError('Experiment config is not authorized to spend subscription quota')
    if not args.name.replace('-', '').replace('_', '').isalnum() or args.attempts < 1:
        raise ValueError('Invalid job name or attempts')
    run_root = ROOT/'runs/experiments'/config['experiment_id']
    if (run_root/'jobs'/args.name).exists():
        raise RuntimeError('Job already exists; will not resume or overwrite')
    side = config['runtimes']['policy']
    adapter = runtimes.get(side['adapter'])
    bundle = args.bundle.resolve()
    errors = portable.validate(bundle, adapter.CAPABILITIES)
    if errors:
        raise ValueError('; '.join(errors))
    spec = {'job_name': args.name, 'jobs_dir': str(run_root/'jobs'), 'n_attempts': args.attempts,
            'n_concurrent_trials': config.get('n_concurrent_trials', 2), 'retry': {'max_retries': 0},
            'environment': {'type': 'docker'},
            'agents': [adapter.agent_spec(bundle, portable.bundle_hash(bundle), side)],
            'tasks': [{'path': str(ROOT/'external/as-bench/tasks'/t)} for t in config['tasks']]}
    from harbor.job import Job
    from harbor.models.job.config import JobConfig
    job_config = JobConfig(**spec)
    env, usage = adapter.policy_environment(side)
    for name in list(os.environ):
        if name not in env:
            del os.environ[name]
    os.environ.update(env)
    record = run_root/'launches'/args.name
    record.mkdir(parents=True, exist_ok=False)
    (record/'config.json').write_text(json.dumps(spec, indent=2)+'\n')
    (record/'usage-before.json').write_text(json.dumps(usage, indent=2)+'\n')
    print('Starting fresh subscription-only job:', args.name, flush=True)

    async def run():
        return await (await Job.create(job_config)).run()
    try:
        result = asyncio.run(run())
    except BaseException as error:
        (record/'failure.json').write_text(json.dumps({'type': type(error).__name__, 'message': str(error)}, indent=2))
        raise
    (record/'job-result.json').write_text(result.model_dump_json(indent=2))
    print('Job finished:', args.name, flush=True)


if __name__ == '__main__':
    main()
