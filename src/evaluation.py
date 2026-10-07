"""Aggregate official task rewards without dropping missing/failed attempts."""
import json
from pathlib import Path


def collect(job_dir):
    records = []
    for path in sorted(Path(job_dir).glob('*/result.json')):
        value = json.loads(path.read_text())
        if 'trial_name' not in value:
            continue
        verifier = value.get('verifier_result') or {}
        rewards = verifier.get('rewards') or {}
        reward = rewards.get('reward')
        if reward is None and len(rewards) == 1:
            reward = next(iter(rewards.values()))
        if reward not in (0,1,None):
            raise ValueError('Unexpected official binary reward')
        agent = value.get('agent_result') or {}
        native_events=[]
        log=path.parent/'agent/claude-code.txt'
        if log.is_file():
            for line in log.read_text().splitlines():
                try:native_events.append(json.loads(line))
                except ValueError:pass
        models=sorted({event.get('message',{}).get('model') for event in native_events
            if event.get('type')=='assistant' and event.get('message',{}).get('model')})
        model_error=not models or any(model!='claude-sonnet-5-5' for model in models)
        api_error=any(event.get('type')=='result' and event.get('is_error') for event in native_events)
        records.append({'task':value['task_name'].split('/')[-1], 'trial':value['trial_name'],
            'reward':reward, 'exception':value.get('exception_info'),
            'executed_models':models, 'model_audit_error':model_error, 'api_error':api_error,
            'model_info':(value.get('agent_info') or {}).get('model_info'),
            'agent_result':agent, 'path':str(path.parent)})
    return records


def accept(parent, candidate, task_names):
    def scores(rows):
        result = {}
        for task in task_names:
            trials = [r for r in rows if r['task']==task]
            if not trials or any(r.get('exception') or r.get('model_audit_error') or r.get('api_error') or r.get('reward') is None for r in trials):
                raise ValueError('Incomplete or errored evaluation; selection is blocked')
            result[task] = sum(r['reward'] for r in trials)/len(trials)
        return result
    previous, proposed = scores(parent), scores(candidate)
    better = sum(proposed.values()) > sum(previous.values())
    no_regression = all(proposed[t]>=previous[t] for t in task_names)
    return {'accepted':better and no_regression, 'parent':previous, 'candidate':proposed,
            'rule':'strict_official_pass_gain_without_per_task_regression',
            'reason':'strict_gain' if better and no_regression else 'regression_or_no_strict_gain'}
