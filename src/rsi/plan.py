"""Proposal contract: one structured, falsifiable plan before any file is edited."""
from rsi import bundle as portable

SUPPORT_FILES = {'instructions.md', 'smoke.json'}


def schema(tasks, components):
    text = {'type': 'string'}
    return {'type': 'object', 'additionalProperties': False,
        'required': ['problem', 'evidence', 'edits', 'predictions', 'why_not_simpler', 'regression_risk',
                     'retroactive_check', 'exploration_waiver'],
        'properties': {
            'problem': text,
            'evidence': {'type': 'array', 'minItems': 1, 'items': {'type': 'object', 'additionalProperties': False,
                'required': ['source', 'location', 'observation'],
                'properties': {'source': text, 'location': text, 'observation': text}}},
            'edits': {'type': 'array', 'minItems': 1, 'items': {'type': 'object', 'additionalProperties': False,
                'required': ['component', 'hypothesis', 'files'],
                'properties': {'component': {'type': 'string', 'enum': list(components)}, 'hypothesis': text,
                               'files': {'type': 'array', 'minItems': 1, 'items': text}}}},
            'predictions': {'type': 'object', 'additionalProperties': False, 'required': ['tasks', 'token_effect'],
                'properties': {
                    'tasks': {'type': 'object', 'additionalProperties': False, 'required': list(tasks),
                              'properties': {t: {'type': 'string', 'enum': ['improve', 'same', 'worsen']} for t in tasks}},
                    'token_effect': {'type': 'string', 'enum': ['lower', 'same', 'higher']}}},
            'why_not_simpler': text, 'regression_risk': text, 'retroactive_check': text, 'exploration_waiver': text}}


def stalled(history):
    evaluated = [h for h in history if h.get('trials')]
    return len(evaluated) >= 2 and not any(h['accepted'] and h['reason'] != 'first_measured_incumbent'
                                           for h in evaluated[-2:])


def tried_components(history):
    return sorted({c for h in history for c in h.get('components_changed') or []})


def directive(history, budget, capabilities):
    untried = [c for c in capabilities.components if c not in tried_components(history)]
    return {'edit_budget': budget, 'supported_components': list(capabilities.components),
            'tried_components': tried_components(history), 'untried_components': untried,
            'require_untried_component_or_waiver': stalled(history) and bool(untried),
            'rule': 'At most edit_budget mechanisms, each one falsifiable. When required, include an untried '
                    'component or give an evidence-based exploration_waiver; otherwise leave the waiver empty.'}


def validate(plan, budget, capabilities, guidance):
    if not isinstance(plan, dict) or not isinstance(plan.get('edits'), list) or not plan['edits']:
        return ['Missing structured plan']
    errors = []
    if len(plan['edits']) > budget:
        errors.append(f'{len(plan["edits"])} edits exceed this round\'s budget of {budget}')
    for edit in plan['edits']:
        if edit.get('component') not in capabilities.components:
            errors.append('Unsupported component: '+str(edit.get('component')))
        if not str(edit.get('hypothesis', '')).strip():
            errors.append('Edit without a hypothesis')
    if guidance['require_untried_component_or_waiver']:
        planned = {e.get('component') for e in plan['edits']}
        if not planned & set(guidance['untried_components']) and not plan.get('exploration_waiver', '').strip():
            errors.append('Stalled search: include an untried component or an evidence-based waiver')
    return errors


def validate_implementation(plan, changed):
    """Changed files must be declared, and every declared component must really change."""
    declared = {f for e in plan['edits'] for f in e['files']}
    errors = [f'Undeclared change: {f}' for f in changed if f not in declared | SUPPORT_FILES]
    changed_components = {portable.component_of(f) for f in changed}
    for edit in plan['edits']:
        if edit['component'] not in changed_components:
            errors.append(f'Planned {edit["component"]} edit has no matching file change')
    if not changed:
        errors.append('Candidate is identical to its parent')
    return errors


def components_changed(changed):
    return sorted({portable.component_of(f) for f in changed} - {None})
