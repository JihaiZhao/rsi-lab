"""Mechanism-first search constraints and conservative component telemetry."""
import json
from pathlib import Path

PLAN_SCHEMA={'type':'object','properties':{k:{'type':'string'} for k in ['problem','evidence','hypothesis','component','why_this_component','expected_effect','exploration_waiver']},'required':['problem','evidence','hypothesis','component','why_this_component','expected_effect','exploration_waiver'],'additionalProperties':False}

# New plans use a closed enum. Only the two archived labels are supported as
# legacy aliases; do not guess arbitrary prose or rewrite archived evidence.
COMPONENTS = ('instructions', 'tool', 'skill', 'memory')
LEGACY_COMPONENTS = {
    'Memory: task-local append-only pass-risk state machine.': 'memory',
    'Skill with scripts: task-local transfer-audit gate.': 'skill',
}
PLAN_SCHEMA['properties']['component'] = {'type': 'string', 'enum': list(COMPONENTS)}

def canonical_component(value):
    return LEGACY_COMPONENTS.get(value, value)

def validate_plan_fields(plan):
    if not isinstance(plan, dict) or any(not isinstance(plan.get(k), str) for k in PLAN_SCHEMA['required']):
        return ['Missing structured mechanism plan']
    errors = []
    if set(plan) - set(PLAN_SCHEMA['required']):
        errors.append('Unexpected mechanism plan fields')
    if canonical_component(plan['component']) not in COMPONENTS:
        errors.append('Unsupported component')
    for key in ['problem', 'evidence', 'hypothesis', 'why_this_component', 'expected_effect']:
        if not plan[key].strip():
            errors.append('Empty ' + key)
    return errors

def changed_files(parent,candidate):
    paths={str(p.relative_to(root)) for root in [parent,candidate] for p in root.rglob('*') if p.is_file()}
    return sorted(p for p in paths if ((parent/p).read_bytes() if (parent/p).is_file() else None)!=((candidate/p).read_bytes() if (candidate/p).is_file() else None))

def directives(history):
    recent=history[-2:]
    explored=sorted({canonical_component(r.get('mechanism',{}).get('component')) for r in history if r.get('mechanism',{}).get('component')})
    prompt_only=not explored or all(canonical_component(r.get('mechanism',{}).get('component','instructions'))=='instructions' for r in recent)
    stalled=len(recent)==2 and all(r.get('reason')!='total_gain' for r in recent)
    return {'one_hypothesis':True,'explored_components':explored,'require_structural_exploration':prompt_only or stalled,
        'rule':'Explore a reusable tool, skill with scripts, or state mechanism when required; otherwise provide a specific evidence-based waiver. Supporting entry-point edits belong to the same single hypothesis. Do not add complexity without observed need.'}

def validate_plan(plan,files,directive):
    errors=validate_plan_fields(plan)
    if errors:return errors
    structural=any(p.startswith(('tools/','skills/','memory/')) for p in files)
    if canonical_component(plan['component'])!='instructions' and not structural:errors.append('Claimed structural change without structural file change')
    if directive['require_structural_exploration'] and not structural and not plan['exploration_waiver'].strip():errors.append('Unexplored component or evidence-based waiver required')
    return errors

def telemetry(rows,bundle):
    paths=[str(p.relative_to(bundle)) for p in bundle.rglob('*') if p.is_file() and str(p.relative_to(bundle)).startswith(('tools/','skills/','memory/'))]
    trials=[]
    for row in rows:
        trajectory=Path(row['path'])/'agent/trajectory.json'
        data=json.loads(trajectory.read_text()) if trajectory.exists() else {}
        calls=[call for step in data.get('steps',[]) for call in (step.get('tool_calls') or [])]
        # References in tool-call arguments are evidence of a reference, not proof of execution or success.
        refs=[p for p in paths if any('/opt/rsi-harness/'+p in json.dumps(call.get('arguments',{})) for call in calls)]
        result=json.loads((Path(row['path'])/'result.json').read_text())
        trials.append({'trial':row['trial'],'task':row['task'],'reward':row['reward'],'component_references':refs,
            'usage_status':'tool_call_reference_observed' if refs else 'no_reference_observed_not_proof_of_nonuse',
            'agent_result':row.get('agent_result'),'started_at':result.get('started_at'),'finished_at':result.get('finished_at')})
    return {'measurement':'Exact bundle paths in native tool-call arguments; does not infer successful execution or causal benefit','trials':trials}
