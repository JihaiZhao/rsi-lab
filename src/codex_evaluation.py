"""Official rewards with independent native Codex model and effort audits."""
import json
from pathlib import Path
from evaluation import collect as collect_claude


def collect(job_dir):
    rows = collect_claude(job_dir)
    for row in rows:
        path = Path(row['path']) / 'agent'
        contexts = []
        for f in path.glob('sessions/**/*.jsonl'):
            for line in f.read_text().splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get('type') == 'turn_context':
                    contexts.append(event.get('payload') or {})
        models = sorted({c['model'] for c in contexts if c.get('model')})
        efforts = sorted({c.get('effort') or c.get('reasoning_effort') for c in contexts
                          if c.get('effort') or c.get('reasoning_effort')})
        events = []
        log = path / 'codex.txt'
        if log.exists():
            for line in log.read_text().splitlines():
                try:
                    events.append(json.loads(line))
                except ValueError:
                    pass
        row.update(executed_models=models, reasoning_efforts=efforts,
                   model_audit_error=not contexts or any(
                       c.get('model') != 'gpt-5.6-terra' or
                       (c.get('effort') or c.get('reasoning_effort')) != 'max'
                       for c in contexts),
                   api_error=any(e.get('type') in ['error', 'turn.failed'] for e in events),
                   stop_reason='completed' if any(e.get('type') == 'turn.completed' for e in events) else None,
                   error_message=None)
    return rows
