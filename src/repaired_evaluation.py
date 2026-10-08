"""Read explicitly recorded trial provenance without rewriting original outcomes."""

def collect_refs(jobs, refs, collector):
    rows = []
    seen = set()
    cache = {}
    for ref in refs:
        job, trial = ref['job'], ref['trial']
        if any('/' in s or s in ('.', '..') for s in (job, trial)):
            raise ValueError('Invalid trial reference')
        if (job, trial) in seen:
            raise ValueError('Duplicate trial reference')
        seen.add((job, trial))
        if job not in cache:
            cache[job] = collector(jobs / job)
        matches = [r for r in cache[job] if r['trial'] == trial]
        if len(matches) != 1:
            raise ValueError('Missing or ambiguous trial reference')
        rows.extend(matches)
    return rows
