"""Evidence for roles: archived candidates, raw trajectories, and deterministic trial cards.

Cards are navigation aids. Raw trajectories remain available because summaries alone
lose the detail proposers need. Only official public task inputs, in-episode records
and official rewards from this experiment are copied.
"""
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from rsi import bundle as portable

ERROR_PATTERN = re.compile(r'Traceback \(most recent call last\)|\b\w*Error:|exit code [1-9]|command not found|'
                           r'No such file or directory|Permission denied', re.IGNORECASE)


def _text(value):
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _time(value):
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (AttributeError, ValueError):
        return None


def trial_card(record, bundle_files=()):
    """Deterministic summary of one Harbor ATIF trajectory. No model calls."""
    path = Path(record['path'])/'agent/trajectory.json'
    data = json.loads(path.read_text()) if path.is_file() else {}
    steps = data.get('steps') or []
    tools, errors, refs = {}, [], set()
    for step in steps:
        for call in step.get('tool_calls') or []:
            name = call.get('function_name') or 'unknown'
            tools[name] = tools.get(name, 0)+1
            arguments = _text(call.get('arguments', {}))
            refs.update(f for f in bundle_files if portable.RUNTIME_ROOT+'/'+f in arguments)
            if name.startswith('mcp__'):
                refs.add('mcp:'+name.split('__')[1])
        for result in (step.get('observation') or {}).get('results') or []:
            content = _text(result.get('content', ''))
            match = ERROR_PATTERN.search(content)
            if match and len(errors) < 12:
                start = max(0, match.start()-120)
                errors.append({'step': step.get('step_id'), 'excerpt': content[start:start+400]})
    times = [t for t in (_time(s.get('timestamp')) for s in steps) if t]
    final = next((s.get('message') for s in reversed(steps) if s.get('source') == 'agent' and s.get('message')), '')
    return {'task': record['task'], 'trial': record['trial'], 'reward': record['reward'],
            'trajectory_available': path.is_file(), 'steps': len(steps),
            'agent_steps': sum(s.get('source') == 'agent' for s in steps),
            'tool_calls': sum(tools.values()), 'tool_histogram': dict(sorted(tools.items(), key=lambda kv: -kv[1])),
            'observed_errors': errors, 'duration_seconds': (max(times)-min(times)).total_seconds() if times else None,
            'tokens': record.get('agent_result'), 'final_metrics': data.get('final_metrics'),
            'harness_references': sorted(refs),
            'harness_reference_note': 'Paths seen in tool-call arguments; not proof of successful use.',
            'final_message_excerpt': _text(final)[-1500:]}


def archive_trials(destination, records, bundle_dir):
    """Copy trajectories and write cards under destination/<task>/<trial>/."""
    bundle_files = portable.files(bundle_dir) if bundle_dir else []
    cards = []
    for record in records:
        target = Path(destination)/record['task']/record['trial']
        target.mkdir(parents=True, exist_ok=False)
        source = Path(record['path'])/'agent/trajectory.json'
        if source.is_file():
            shutil.copyfile(source, target/'trajectory.json')
        card = trial_card(record, bundle_files)
        (target/'card.json').write_text(json.dumps(card, ensure_ascii=False, indent=2)+'\n')
        cards.append(card)
    return cards


def copy_public_tasks(destination, task_root, tasks):
    for task in tasks:
        target = Path(destination)/Path(task).name
        target.mkdir(parents=True, exist_ok=True)
        # Explicit allowlist: never copy benchmark tests, lab truth or solutions.
        shutil.copyfile(Path(task_root)/task/'instruction.md', target/'instruction.md')


def _pct(value):
    return '—' if value is None else f'{100*value:.0f}%'


def render_index(history, ledger, scoreboard):
    lines = ['# Evidence index', '',
             'All scores are evolve-set pass rates from this experiment only. Six binary trials per candidate '
             'give roughly ±35–40 point intervals; read posteriors, not just rates.', '',
             '| Round | Components | Decision | Reason | Trials | Pass rate | P(better than parent) |',
             '|---|---|---|---|---|---|---|']
    for h in history:
        lines.append(f"| {h['round']} | {', '.join(h.get('components_changed') or []) or '—'} | "
                     f"{'accepted' if h.get('accepted') else 'not accepted'} | {h.get('reason', '')} | "
                     f"{h.get('trials', '—')} | {_pct(h.get('score'))} | {_pct(h.get('p_superior'))} |")
    lines += ['', '## Hypothesis ledger', '']
    for item in ledger:
        lines.append(f"- Round {item['round']} [{item['status']}] {item['component']}: {item['hypothesis']}")
    lines += ['', '## Prediction scoreboard', '']
    for item in scoreboard:
        lines.append(f"- Round {item['round']}: {item['hits']}/{item['total']} task predictions matched; "
                     f"unpredicted regressions: {', '.join(item['unpredicted_regressions']) or 'none'}")
    lines += ['', 'Archive layout: `archive/round-NN/` holds candidate source, diff, plan, gate report, critic '
              'verdict, decision and `trials/<task>/<trial>/{card.json,trajectory.json}`.', '']
    return '\n'.join(lines)


def score_predictions(plan, parent_rates, candidate_rates):
    """Compare per-task predicted direction with observed pass-rate change."""
    hits, regressions = 0, []
    predictions = (plan or {}).get('predictions', {}).get('tasks', {})
    for task, predicted in predictions.items():
        if task not in candidate_rates:
            continue
        delta = candidate_rates[task]-(parent_rates or {}).get(task, candidate_rates[task])
        observed = 'improve' if delta > 0 else 'worsen' if delta < 0 else 'same'
        hits += observed == predicted
        if observed == 'worsen' and predicted != 'worsen':
            regressions.append(task)
    return {'hits': hits, 'total': len(predictions), 'unpredicted_regressions': regressions}
