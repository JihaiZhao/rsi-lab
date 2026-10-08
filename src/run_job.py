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
    parser.add_argument('--config', type=Path, default=ROOT/'config/experiment.json')
    parser.add_argument('--domain', choices=['biology','chemistry','all'], required=True)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--attempts', type=int, default=1)
    args = parser.parse_args()
    experiment = json.loads(args.config.read_text())
    if experiment.get('budget_status') != 'subscription_only_authorized':
        raise RuntimeError('Subscription-only authorization not recorded')
    if not args.name.replace('-', '').replace('_', '').isalnum():
        raise ValueError('Invalid job name')
    run_root=ROOT/'runs/experiments'/experiment['experiment_id'] if experiment.get('experiment_id') else ROOT/'runs'
    destination = run_root/'jobs'/args.name
    if destination.exists():
        raise RuntimeError('Job already exists; will not resume or overwrite')
    tasks = experiment['evolve'] if args.domain == 'all' else experiment['domains'][args.domain]
    spec = build('candidate' if args.bundle else 'baseline', tasks[0], args.bundle, args.attempts)
    if experiment.get('policy_runtime') == 'codex':
        from cached_codex_runtime import validate_cache
        validate_cache()
        if not args.bundle: raise ValueError('Bio protocol requires an explicit candidate')
        from native_bundle import bundle_hash
        spec['agents'] = [{'import_path': 'native_codex_agent:RSICodex',
            'model_name': experiment['model_roles']['policy'], 'env': {},
            'kwargs': {'version': '0.154.0', 'reasoning_effort': 'max', 'web_search': 'disabled',
                       'harness_dir': str(args.bundle.resolve()), 'harness_sha256': bundle_hash(args.bundle)}}]
    spec['tasks'] = [{'path': str(ROOT/'external/as-bench/tasks'/task)} for task in tasks]
    spec.update(job_name=args.name, jobs_dir=str(run_root/'jobs'),
        n_concurrent_trials=experiment.get('n_concurrent_trials',2), retry={'max_retries':0})
    from harbor.models.job.config import JobConfig
    from harbor.job import Job
    config = JobConfig(**spec)
    if experiment.get('policy_runtime') == 'codex':
        from codex_subscription import codex_subscription_environment
        env, usage = codex_subscription_environment()
    else:
        env, usage = subscription_environment()
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
        job = await Job.create(config)
        return await job.run()
    try:
        result = asyncio.run(run())
    except BaseException as error:
        (record/'failure.json').write_text(json.dumps({'type':type(error).__name__, 'message':str(error)},indent=2))
        raise
    (record/'job-result.json').write_text(result.model_dump_json(indent=2))
    print('Job finished:', args.name, flush=True)


if __name__ == '__main__':
    main()
