"""Pre-registered, noise-aware selection. Pure functions over official trial records."""
from math import exp, lgamma, log

DEFAULTS = {'delta': 1/6, 'p_accept': 0.8, 'token_saving': 0.15,
            'screen_stop_if_zero_and_incumbent_at_least': 0.5}


def check_complete(rows, tasks, per_task):
    for task in tasks:
        trials = [r for r in rows if r['task'] == task]
        if len(trials) != per_task:
            raise ValueError(f'Expected {per_task} trials for {task}, found {len(trials)}')
        if any(r.get('exception') or r.get('model_audit_error') or r.get('api_error') or r.get('reward') is None
               for r in trials):
            raise ValueError('Incomplete or errored evaluation; selection is blocked')


def rate(rows):
    return sum(r['reward'] for r in rows)/len(rows)


def task_rates(rows, tasks):
    return {t: rate([r for r in rows if r['task'] == t]) for t in tasks}


def tokens_per_trial(rows):
    values = []
    for r in rows:
        agent = r.get('agent_result') or {}
        if agent.get('n_input_tokens') is None or agent.get('n_output_tokens') is None:
            return None
        values.append(agent['n_input_tokens']+agent['n_output_tokens'])
    return sum(values)/len(values)


def _lbeta(a, b):
    return lgamma(a)+lgamma(b)-lgamma(a+b)


def p_superior(s1, n1, s0, n0):
    """Exact P(p1 > p0) for independent Beta(1+s, 1+n-s) posteriors (uniform prior)."""
    a1, b1, a0, b0 = 1+s1, 1+n1-s1, 1+s0, 1+n0-s0
    return sum(exp(_lbeta(a0+i, b0+b1)-log(b1+i)-_lbeta(1+i, b1)-_lbeta(a0, b0)) for i in range(a1))


def continue_after_screen(screen, incumbent, rules=DEFAULTS):
    """Top up unless the screen passed nothing against a clearly working incumbent."""
    if not incumbent:
        return True, 'no_incumbent'
    if sum(r['reward'] for r in screen) == 0 and rate(incumbent) >= rules['screen_stop_if_zero_and_incumbent_at_least']:
        return False, 'screen_zero_against_working_incumbent'
    return True, 'screen_not_clearly_worse'


def decide(incumbent, candidate, *, best_score, incumbent_complexity, candidate_complexity, rules=DEFAULTS):
    """Returns the decision record. Callers must run check_complete first."""
    s_c = rate(candidate)
    base = {'score': s_c, 'trials': len(candidate), 'candidate_complexity': candidate_complexity,
            'candidate_tokens_per_trial': tokens_per_trial(candidate), 'rules': rules,
            'paired_local_improvement_claim': False}
    if not incumbent:
        return {**base, 'accepted': True, 'reason': 'first_measured_incumbent', 'p_superior': None}
    s_i = rate(incumbent)
    passes_c, passes_i = sum(r['reward'] for r in candidate), sum(r['reward'] for r in incumbent)
    p = p_superior(passes_c, len(candidate), passes_i, len(incumbent))
    tok_c, tok_i = base['candidate_tokens_per_trial'], tokens_per_trial(incumbent)
    record = {**base, 'incumbent_score': s_i, 'p_superior': p, 'incumbent_complexity': incumbent_complexity,
              'incumbent_tokens_per_trial': tok_i}
    if best_score is not None and s_c < best_score-rules['delta']-1e-9:
        return {**record, 'accepted': False, 'reason': 'below_noise_floor_of_best'}
    if s_c > s_i and p >= rules['p_accept']:
        return {**record, 'accepted': True, 'reason': 'credible_gain'}
    if abs(s_c-s_i) <= rules['delta']+1e-9:
        if candidate_complexity < incumbent_complexity:
            return {**record, 'accepted': True, 'reason': 'in_band_simpler'}
        cheaper = tok_c is not None and tok_i is not None and tok_c <= (1-rules['token_saving'])*tok_i
        if cheaper and candidate_complexity <= incumbent_complexity:
            return {**record, 'accepted': True, 'reason': 'in_band_cheaper_not_more_complex'}
        return {**record, 'accepted': False, 'reason': 'unresolved_in_noise_band'}
    return {**record, 'accepted': False, 'reason': 'regression' if s_c < s_i else 'gain_not_credible'}
