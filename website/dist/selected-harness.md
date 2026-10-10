# Selected harness: chem-sonnet-v2-20261009-03, round 3

sha256 `b232ad942c6f44e92710c1bf6a8c148a76d813fdc9a918bc1c68f88066815528`

## hooks.json

```
{
  "stop": [
    {
      "command": "python3",
      "args": ["/opt/rsi-harness/tools/stop_audit.py"],
      "timeout": 30
    }
  ]
}

```

## instructions.md

```
# Campaign workflow notes

These apply to tasks of the form: seed data, a few irreversible batched `asb run` rounds, then a self-contained
deterministic `final_model.js` that must pass both a discovery gate (hits among your ordered items) and a
held-out ranking (NDCG) gate. Two gates means neither can be left to the end.

## Before round 1
- Read the campaign description (`asb campaign`), the data README, and the model format spec plus the template
  script in full.
- Write a baseline model from the seed data and run the deliver command in its free validation-only mode.
  Re-validate after every round, so a valid model always exists well before the deadline.
- Note both pass criteria and how relevance, ties and the discount are defined; reproduce the metric locally.

## Each round
- Accepted rounds are final; rejected requests are free. Before `asb run`, check the file:
  `python3 /opt/rsi-harness/tools/campaign_check.py batch round_N.csv --size <N> --id-column <name> --previous round_*_results.csv [--catalog <catalog csv>]`
  Fix anything it reports (header, size, duplicates, items already ordered, ids not in the catalog).
- Split each round between the model's top picks and covering groups or levels that are under-sampled so far.
  Track the running count of hits against the discovery threshold and shift toward exploitation when behind.
  This is guidance, not fixed percentages.
- Measurements are noisy; do not read much into a single value that sits near the threshold.

## Using the seed data
- Use the seed data for how the levels of each categorical factor behave, not as a shortlist: the target regime can
  differ from the seed regime. Where targets are defined per group, normalise within group and do not let a global
  score favour easy groups over hard ones.

## Choosing and checking the model
- Pick the final model by cross-validation that mimics the held-out distribution (group the folds by the grouping variable
  that distinguishes held-out items, e.g. a categorical key), with the official metric computed locally:
  `python3 /opt/rsi-harness/tools/campaign_check.py ndcg preds.csv --pred <col> --rel <col> --k <k> [--group <col>] [--threshold <t>]`
  Pass relevance already defined as the task states (clipped/normalised). The tool breaks score ties by input row order;
  prefer models that rarely produce ties.
- The model must be self-contained, deterministic, finite for every input and independent per input; handle levels
  unseen in training with a fallback. Before delivering, run
  `python3 /opt/rsi-harness/tools/campaign_check.py probe <your model file> --inputs-file samples.txt`
  with a few real-format inputs (taken from the catalog), then the validation-only deliver, then the real deliver.
- `python3 /opt/rsi-harness/tools/campaign_check.py selftest` checks the tool itself. The tool is advisory only.

```

## smoke.json

```
[
  {
    "name": "campaign_check selftest (hand-computed NDCG, tie rule, batch and probe checks)",
    "command": "python3",
    "args": ["/opt/rsi-harness/tools/campaign_check.py", "selftest"],
    "stdin": "",
    "expect_exit": 0,
    "timeout": 120
  },
  {
    "name": "campaign_check ndcg on a tiny synthetic CSV from stdin",
    "command": "python3",
    "args": ["/opt/rsi-harness/tools/campaign_check.py", "ndcg", "-", "--pred", "p", "--rel", "r", "--k", "3", "--group", "g"],
    "stdin": "p,r,g\n0.9,1,x\n0.8,0,x\n0.7,1,x\n0.5,0,y\n0.4,2,y\n0.3,1,y\n",
    "expect_exit": 0,
    "timeout": 30
  },
  {
    "name": "campaign_check ndcg rejects an unknown column",
    "command": "python3",
    "args": ["/opt/rsi-harness/tools/campaign_check.py", "ndcg", "-", "--pred", "nope", "--rel", "r", "--k", "2"],
    "stdin": "p,r\n1,1\n2,0\n",
    "expect_exit": 2,
    "timeout": 30
  },
  {
    "name": "campaign_check batch accepts a clean round",
    "command": "python3",
    "args": ["/opt/rsi-harness/tools/campaign_check.py", "batch", "-", "--size", "3", "--id-column", "well_id"],
    "stdin": "well_id\nw1\nw2\nw3\n",
    "expect_exit": 0,
    "timeout": 30
  },
  {
    "name": "campaign_check batch flags duplicates and wrong size",
    "command": "python3",
    "args": ["/opt/rsi-harness/tools/campaign_check.py", "batch", "-", "--size", "3", "--id-column", "well_id"],
    "stdin": "well_id\nw1\nw1\n",
    "expect_exit": 1,
    "timeout": 30
  },
  {
    "name": "campaign_check batch flags a wrong header",
    "command": "python3",
    "args": ["/opt/rsi-harness/tools/campaign_check.py", "batch", "-", "--size", "2", "--id-column", "item_key"],
    "stdin": "id\nA\nB\n",
    "expect_exit": 1,
    "timeout": 30
  },
  {
    "name": "stop_audit hook selftest (block once after delivery, never loop, no-op otherwise)",
    "command": "python3",
    "args": ["/opt/rsi-harness/tools/stop_audit.py", "--selftest"],
    "stdin": "",
    "expect_exit": 0,
    "timeout": 120
  },
  {
    "name": "stop_audit hook lets an already-active stop through",
    "command": "python3",
    "args": ["/opt/rsi-harness/tools/stop_audit.py"],
    "stdin": "{\"hook_event_name\": \"Stop\", \"stop_hook_active\": true, \"session_id\": \"smoke\", \"transcript_path\": \"/nonexistent/t.jsonl\"}",
    "expect_exit": 0,
    "timeout": 30
  },
  {
    "name": "stop_audit hook ignores malformed event input",
    "command": "python3",
    "args": ["/opt/rsi-harness/tools/stop_audit.py"],
    "stdin": "not json at all",
    "expect_exit": 0,
    "timeout": 30
  },
  {
    "name": "campaign_check probe reports a missing model as a usage error",
    "command": "python3",
    "args": ["/opt/rsi-harness/tools/campaign_check.py", "probe", "/nonexistent/final_model.js", "--input", "x"],
    "stdin": "",
    "expect_exit": 2,
    "timeout": 30
  }
]

```

## tools/campaign_check.py

```
#!/usr/bin/env python3
"""Advisory checks for batched-oracle campaigns (stdlib only, never blocks anything).

Subcommands
  batch   check a round CSV before ordering it (header, size, duplicates, earlier orders, catalog)
  ndcg    local NDCG@k with 1/log2(rank+1) discount, stable ties, ideal-ranking normalisation
  probe   run final_model.js under node on sample inputs: finite, deterministic, order-independent
  selftest  built-in hand-computed checks of the above

Exit codes: 0 ok, 1 problem found, 2 usage or I/O error.
"""
import argparse
import csv
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile


def die(msg, code=2):
    sys.stderr.write("error: %s\n" % msg)
    sys.exit(code)


def read_text(path):
    if path == "-":
        return sys.stdin.read()
    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            return fh.read()
    except OSError as exc:
        die("cannot read %s: %s" % (path, exc))


def read_rows(path):
    text = read_text(path)
    if text.startswith("﻿"):
        text = text[1:]
    rows = list(csv.reader(io.StringIO(text)))
    rows = [r for r in rows if r and any(c.strip() for c in r)]
    if not rows:
        die("%s is empty" % path)
    return rows[0], rows[1:]


def id_values(path, column):
    header, body = read_rows(path)
    idx = header.index(column) if column in header else 0
    return [r[idx].strip() for r in body if len(r) > idx]


# ---------------------------------------------------------------- batch
def cmd_batch(args):
    header, body = read_rows(args.round_csv)
    problems, notes = [], []
    column = args.id_column or header[0]
    if len(header) != 1:
        problems.append("header has %d columns %r; the round file needs a single column" % (len(header), header))
    if header[0] != column:
        problems.append("header is %r, expected %r" % (header[0], column))
    ids = [r[0] for r in body]
    padded = [i for i in ids if i != i.strip()]
    if padded:
        problems.append("%d ids have leading/trailing whitespace, e.g. %r" % (len(padded), padded[0]))
    ids = [i.strip() for i in ids]
    if any(len(r) != 1 for r in body):
        problems.append("some rows have more than one field")
    if any(not i for i in ids):
        problems.append("blank ids present")
    notes.append("header=%r rows=%d" % (header, len(ids)))
    if args.size is not None and len(ids) != args.size:
        problems.append("size is %d, expected exactly %d" % (len(ids), args.size))
    seen, dups = set(), []
    for i in ids:
        if i in seen and i not in dups:
            dups.append(i)
        seen.add(i)
    if dups:
        problems.append("%d duplicated ids inside the batch, e.g. %s" % (len(dups), dups[:3]))
    prior = set()
    for p in args.previous or []:
        prior.update(id_values(p, column))
    overlap = sorted(seen & prior)
    if args.previous:
        notes.append("compared with %d earlier ids from %d files" % (len(prior), len(args.previous)))
    if overlap:
        problems.append("%d ids were already ordered, e.g. %s" % (len(overlap), overlap[:3]))
    if args.catalog:
        cat = set(id_values(args.catalog, args.catalog_column or column))
        notes.append("catalog has %d ids" % len(cat))
        unknown = sorted(seen - cat)
        if unknown:
            problems.append("%d ids are not in the catalog, e.g. %s" % (len(unknown), unknown[:3]))
    for n in notes:
        print("note: " + n)
    for p in problems:
        print("PROBLEM: " + p)
    print("batch %s" % ("FAILED" if problems else "OK"))
    return 1 if problems else 0


# ---------------------------------------------------------------- ndcg
def dcg(rels):
    return sum(r / math.log2(i + 2) for i, r in enumerate(rels))


def ndcg_at_k(preds, rels, k):
    """Rank by prediction descending; equal predictions keep input order (stable sort)."""
    order = sorted(range(len(preds)), key=lambda i: -preds[i])
    got = dcg([rels[i] for i in order[:k]])
    ideal = dcg(sorted(rels, reverse=True)[:k])
    if ideal <= 0:
        return None
    return got / ideal


def cmd_ndcg(args):
    header, body = read_rows(args.csv)
    for c in [args.pred, args.rel] + ([args.group] if args.group else []):
        if c not in header:
            die("column %r not in header %r" % (c, header))
    ip, ir = header.index(args.pred), header.index(args.rel)
    ig = header.index(args.group) if args.group else None
    preds, rels, groups = [], [], []
    for n, r in enumerate(body, 2):
        try:
            p, q = float(r[ip]), float(r[ir])
        except (ValueError, IndexError):
            die("row %d: non-numeric prediction or relevance" % n)
        if math.isnan(p) or math.isnan(q) or math.isinf(p):
            die("row %d: NaN/inf value" % n)
        preds.append(p)
        rels.append(q)
        groups.append(r[ig] if ig is not None else None)
    if any(q < 0 for q in rels):
        print("warning: negative relevance present; pass relevance already clipped at 0 if the metric does so")
    k = args.k
    if k > len(preds):
        print("warning: k=%d exceeds %d rows" % (k, len(preds)))
    val = ndcg_at_k(preds, rels, k)
    if val is None:
        print("warning: ideal DCG is 0 (no positive relevance); NDCG undefined, reported as 0")
        val = 0.0
    print("ndcg@%d = %.6f  (n=%d)" % (k, val, len(preds)))
    if args.group:
        by = {}
        for i, g in enumerate(groups):
            by.setdefault(g, []).append(i)
        vals = []
        for g in sorted(by):
            v = ndcg_at_k([preds[i] for i in by[g]], [rels[i] for i in by[g]], k)
            vals.append(v)
            print("  group %s: n=%d ndcg@%d=%s" % (g, len(by[g]), k, "undefined" if v is None else "%.4f" % v))
        ok = [v for v in vals if v is not None]
        if ok:
            print("mean over groups (informational, not the pooled metric) = %.6f" % (sum(ok) / len(ok)))
    if args.threshold is not None:
        print("threshold %.4f: %s" % (args.threshold, "PASS" if val >= args.threshold else "BELOW"))
    return 0


# ---------------------------------------------------------------- probe
PROBE_JS = r"""
const fs = require('fs'), vm = require('vm');
const req = JSON.parse(fs.readFileSync(0, 'utf8'));
function load() {
  const code = fs.readFileSync(req.model, 'utf8');
  const mod = { exports: {} };
  const sb = { module: mod, exports: mod.exports, console: { log() {}, error() {}, warn() {} } };
  vm.createContext(sb);
  vm.runInContext(code, sb, { timeout: 60000 });
  const f = (typeof sb.predict === 'function') ? sb.predict
    : (mod.exports && typeof mod.exports.predict === 'function') ? mod.exports.predict : null;
  if (!f) throw new Error('no predict function defined');
  return f;
}
function run(f, x) {
  try { return { v: f(x) }; } catch (e) { return { e: String(e && e.message || e) }; }
}
const out = { load_error: null, results: [] };
try {
  const f1 = load(), f2 = load();
  const xs = req.inputs;
  const a = xs.map(x => run(f1, x));
  const b = xs.map(x => run(f1, x));
  const c = xs.map((x, i) => run(f2, xs[xs.length - 1 - i])).reverse();
  xs.forEach((x, i) => {
    const same = (p, q) => ('e' in p && 'e' in q) || ('v' in p && 'v' in q && Object.is(p.v, q.v));
    out.results.push({
      input: x, value: ('v' in a[i]) ? a[i].v : null, error: a[i].e || null,
      type: ('v' in a[i]) ? typeof a[i].v : null,
      finite: ('v' in a[i]) && typeof a[i].v === 'number' && Number.isFinite(a[i].v),
      repeat_same: same(a[i], b[i]), order_same: same(a[i], c[i])
    });
  });
} catch (e) { out.load_error = String(e && e.message || e); }
process.stdout.write(JSON.stringify(out));
"""

BUILTIN_EDGE = ["", "?"]


def cmd_probe(args):
    if not os.path.isfile(args.model):
        die("model file not found: %s" % args.model)
    node = shutil.which("node")
    if not node:
        die("node not found on PATH")
    inputs = list(args.input or [])
    if args.inputs_file:
        inputs += [l.rstrip("\r\n") for l in read_text(args.inputs_file).splitlines() if l.strip()]
    edge_must = []
    if args.edge_file:
        edge_must = [l.rstrip("\r\n") for l in read_text(args.edge_file).splitlines() if l.strip()]
    if not inputs and not edge_must:
        die("give --input and/or --inputs-file (real-format sample inputs)")
    all_inputs = inputs + edge_must + BUILTIN_EDGE
    kinds = ["sample"] * len(inputs) + ["edge-required"] * len(edge_must) + ["edge-advisory"] * len(BUILTIN_EDGE)
    payload = json.dumps({"model": os.path.abspath(args.model), "inputs": all_inputs})
    try:
        proc = subprocess.run([node, "-e", PROBE_JS], input=payload, capture_output=True,
                              text=True, timeout=args.timeout)
    except subprocess.TimeoutExpired:
        print("PROBLEM: node timed out after %ss" % args.timeout)
        return 1
    if proc.returncode != 0:
        print("PROBLEM: node failed: %s" % proc.stderr.strip()[:500])
        return 1
    try:
        res = json.loads(proc.stdout)
    except ValueError:
        print("PROBLEM: unparseable probe output: %r" % proc.stdout[:200])
        return 1
    if res.get("load_error"):
        print("PROBLEM: model failed to load in an isolated context: %s" % res["load_error"])
        return 1
    problems = 0
    for r, kind in zip(res["results"], kinds):
        bad = []
        if r["error"]:
            bad.append("threw: %s" % r["error"])
        elif not r["finite"]:
            bad.append("not a finite number (%r)" % (r["value"],))
        if not r["repeat_same"]:
            bad.append("repeated call differs")
        if not r["order_same"]:
            bad.append("result depends on call order/fresh load")
        if bad:
            tag = "WARN" if kind == "edge-advisory" else "PROBLEM"
            if kind != "edge-advisory":
                problems += 1
            print("%s [%s] %r: %s" % (tag, kind, r["input"], "; ".join(bad)))
    vals = [r["value"] for r in res["results"][:len(inputs)] if r["finite"]]
    if vals:
        print("sample outputs: n=%d min=%.6g max=%.6g distinct=%d" % (len(vals), min(vals), max(vals), len(set(vals))))
        if len(set(vals)) == 1 and len(vals) > 1:
            print("WARN: every sample input got the same score; the ranking would be all ties")
    print("probe %s" % ("FAILED" if problems else "OK"))
    return 1 if problems else 0


# ---------------------------------------------------------------- selftest
def cmd_selftest(_args):
    fails = []

    def check(name, cond):
        if not cond:
            fails.append(name)
        print("%s %s" % ("ok  " if cond else "FAIL", name))

    # hand-computed: dcg = 1 + 0.5 = 1.5 ; ideal = 1 + 1/log2(3)
    v = ndcg_at_k([0.9, 0.8, 0.7], [1, 0, 1], 3)
    check("ndcg hand value", abs(v - 1.5 / (1 + 1 / math.log2(3))) < 1e-12)
    # tie rule: equal scores keep evaluation order -> rels seen [0,1]
    v = ndcg_at_k([5, 5, 5], [0, 1, 1], 2)
    check("ndcg tie keeps input order", abs(v - (1 / math.log2(3)) / (1 + 1 / math.log2(3))) < 1e-12)
    check("ndcg perfect ranking is 1", abs(ndcg_at_k([3, 2, 1], [2, 1, 0], 2) - 1) < 1e-12)
    check("ndcg undefined without positives", ndcg_at_k([1, 2], [0, 0], 2) is None)
    tmp = tempfile.mkdtemp(prefix="campchk_")
    try:
        def w(name, text):
            p = os.path.join(tmp, name)
            with open(p, "w") as fh:
                fh.write(text)
            return p
        prev = w("prev.csv", "id,y\na,1\nb,2\n")
        ns = argparse.Namespace
        import contextlib
        sink = io.StringIO()
        with contextlib.redirect_stdout(sink):
            ok = cmd_batch(ns(round_csv=w("r1.csv", "id\nc\nd\n"), size=2, id_column="id",
                              previous=[prev], catalog=None, catalog_column=None))
            dup = cmd_batch(ns(round_csv=w("r2.csv", "id\nc\nc\n"), size=2, id_column="id",
                               previous=[prev], catalog=None, catalog_column=None))
            old = cmd_batch(ns(round_csv=w("r3.csv", "id\na\nd\n"), size=2, id_column="id",
                               previous=[prev], catalog=None, catalog_column=None))
            short = cmd_batch(ns(round_csv=w("r4.csv", "id\nc\n"), size=2, id_column="id",
                                 previous=[], catalog=None, catalog_column=None))
            hdr = cmd_batch(ns(round_csv=w("r5.csv", "wrong\nc\nd\n"), size=2, id_column="id",
                               previous=[], catalog=None, catalog_column=None))
        check("batch accepts clean round", ok == 0)
        check("batch flags in-batch duplicate", dup == 1)
        check("batch flags earlier order", old == 1)
        check("batch flags wrong size", short == 1)
        check("batch flags wrong header", hdr == 1)
        if shutil.which("node"):
            model = w("m.js", "function predict(x){ return x.length * 0.5; }\n")
            bad = w("bad.js", "function predict(x){ return x === '' ? NaN : Math.random(); }\n")
            with contextlib.redirect_stdout(sink):
                good = cmd_probe(ns(model=model, input=["ab", "abcd"], inputs_file=None,
                                    edge_file=None, timeout=60))
                notgood = cmd_probe(ns(model=bad, input=["ab", "abcd"], inputs_file=None,
                                       edge_file=None, timeout=60))
            check("probe accepts a finite deterministic model", good == 0)
            check("probe rejects a random model", notgood == 1)
        else:
            print("skip probe checks (node not found)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("selftest %s" % ("FAILED" if fails else "OK"))
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("batch", help="check a round CSV before `asb run` (use '-' for stdin)")
    b.add_argument("round_csv")
    b.add_argument("--size", type=int, help="exact number of rows required")
    b.add_argument("--id-column", help="expected header, e.g. the single column name from the task")
    b.add_argument("--previous", nargs="*", help="earlier round or results CSVs whose ids may not repeat")
    b.add_argument("--catalog", help="CSV listing orderable ids")
    b.add_argument("--catalog-column", help="id column in the catalog (default: --id-column)")
    b.set_defaults(fn=cmd_batch)

    n = sub.add_parser("ndcg", help="local NDCG@k (use '-' for stdin)")
    n.add_argument("csv")
    n.add_argument("--pred", required=True, help="prediction column")
    n.add_argument("--rel", required=True, help="relevance column (already clipped/normalised as the task defines)")
    n.add_argument("--k", type=int, required=True)
    n.add_argument("--group", help="optional group column; adds per-group NDCG as a diagnostic")
    n.add_argument("--threshold", type=float, help="optional pass level to compare against")
    n.set_defaults(fn=cmd_ndcg)

    p = sub.add_parser("probe", help="run final_model.js under node on sample inputs")
    p.add_argument("model")
    p.add_argument("--input", action="append", help="sample input string (repeatable)")
    p.add_argument("--inputs-file", help="file with one sample input per line")
    p.add_argument("--edge-file", help="file with one extra input per line that must also score finitely")
    p.add_argument("--timeout", type=int, default=120)
    p.set_defaults(fn=cmd_probe)

    s = sub.add_parser("selftest", help="hand-computed self checks")
    s.set_defaults(fn=cmd_selftest)

    args = ap.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()

```

## tools/stop_audit.py

```
#!/usr/bin/env python3
"""One-shot stop hook: after a campaign model was delivered and time remains, ask for a held-out audit.

Reads the stop event JSON on stdin. Exit 0 lets the agent stop. Exit 2 blocks the stop once and feeds the
audit request (stderr) back to the agent. It never blocks twice per session, never blocks when the event says
a stop hook is already active, and never blocks outside a delivered-campaign context.
Stdlib only. Run with --selftest for a built-in check using temporary fixtures.
"""
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone

MARKER_ENV = "RSI_AUDIT_MARKER_DIR"
BUDGET_ENV = "RSI_AUDIT_BUDGET_S"
DEFAULT_BUDGET_S = 28800
MIN_REMAINING_S = 1800
DELIVERED = "deliverable accepted"
MODEL_NAME = "final_model.js"

MESSAGE = """Before stopping: a model has been delivered and time remains. The latest submission is the one scored, so
re-delivery is allowed. Spend a short audit on the held-out ranking gate. Everything you measured so far was
chosen by your own model, so a score over your own picks is biased upward.

1. Build a held-out stand-in. Use the broad first round (or the least model-selected measurements), or hold out whole
   groups of the ordered items (group the folds by the key that distinguishes held-out items). Fit on the rest, keeping
   the seed data in. Score with the official relevance transform exactly as the task states it:
   python3 /opt/rsi-harness/tools/campaign_check.py ndcg preds.csv --pred <col> --rel <col> --k <k> [--group <col>]
2. Compare the delivered model with at least one structurally different alternative on that same stand-in: a
   lower-dimensional or smoother model (fewer features, stronger shrinkage, log or clipped target), and the same
   model with versus without the seed data. Run long fits in the background (nohup ... &) and poll the log, because
   a single command is cut off after about two minutes.
3. Re-deliver only if an alternative beats the delivered model by a clear margin (state it, e.g. at least 0.05 NDCG)
   and the gap is not one or two items. Then: cp final_model.js final_model.prev.js, write the new file,
   python3 /opt/rsi-harness/tools/campaign_check.py probe <model> --inputs-file samples.txt,
   asb deliver <model> --validate-only, and only then the real deliver.
   If nothing wins by the margin, keep the current model: do not re-deliver, and report the stand-in scores.
This audit happens once; state the numbers you compared in the final message."""


def parse_ts(value):
    try:
        if isinstance(value, (int, float)):
            return float(value) / (1000.0 if value > 1e11 else 1.0)
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError, TypeError):
        return None


def read_transcript(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def first_timestamp(text):
    for line in text.splitlines()[:50]:
        m = re.search(r'"timestamp"\s*:\s*("[^"]+"|[0-9.]+)', line)
        if m:
            ts = parse_ts(json.loads(m.group(1)))
            if ts:
                return ts
    return None


def model_exists(cwd):
    for d in (cwd, os.getcwd(), "/app"):
        if d and os.path.isfile(os.path.join(d, MODEL_NAME)):
            return True
    return False


def marker_path(session):
    base = os.environ.get(MARKER_ENV) or os.path.join(tempfile.gettempdir(), "rsi_stop_audit")
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session or "nosession")[:80]
    return base, os.path.join(base, safe + ".done")


def decide(event):
    """Return True if the stop should be blocked for the audit."""
    if event.get("stop_hook_active"):
        return False
    cwd = event.get("cwd") or ""
    text = None
    tp = event.get("transcript_path")
    if tp:
        text = read_transcript(tp)
    if text is not None:
        if DELIVERED not in text or MODEL_NAME not in text:
            return False
        start = first_timestamp(text)
        if start is not None:
            try:
                budget = float(os.environ.get(BUDGET_ENV, DEFAULT_BUDGET_S))
            except ValueError:
                budget = DEFAULT_BUDGET_S
            if time.time() - start > budget - MIN_REMAINING_S:
                return False
    elif not model_exists(cwd):
        return False
    return True


def main():
    if "--selftest" in sys.argv:
        return selftest()
    try:
        event = json.loads(sys.stdin.read() or "{}")
        if not isinstance(event, dict):
            return 0
    except ValueError:
        return 0
    try:
        if not decide(event):
            return 0
        base, marker = marker_path(str(event.get("session_id") or ""))
        if os.path.exists(marker):
            return 0
        os.makedirs(base, exist_ok=True)
        with open(marker, "w") as fh:
            fh.write(str(time.time()))
    except OSError:
        return 0
    sys.stderr.write(MESSAGE + "\n")
    return 2


def selftest():
    import subprocess
    import shutil
    tmp = tempfile.mkdtemp(prefix="stopaudit_")
    fails = []
    try:
        env = dict(os.environ, **{MARKER_ENV: os.path.join(tmp, "m")})

        def run(event):
            p = subprocess.run([sys.executable, os.path.abspath(__file__)], input=json.dumps(event),
                               capture_output=True, text=True, env=env, timeout=30)
            return p.returncode

        def check(name, cond):
            print("%s %s" % ("ok  " if cond else "FAIL", name))
            if not cond:
                fails.append(name)

        now = datetime.now(timezone.utc).isoformat()
        good = os.path.join(tmp, "good.jsonl")
        with open(good, "w") as fh:
            fh.write(json.dumps({"timestamp": now, "text": "asb deliver final_model.js"}) + "\n")
            fh.write(json.dumps({"text": "local validation passed\n" + DELIVERED + " (submission 1)"}) + "\n")
        undelivered = os.path.join(tmp, "undelivered.jsonl")
        with open(undelivered, "w") as fh:
            fh.write(json.dumps({"timestamp": now, "text": "writing final_model.js"}) + "\n")
        late = os.path.join(tmp, "late.jsonl")
        with open(late, "w") as fh:
            fh.write(json.dumps({"timestamp": "2020-01-01T00:00:00Z", "text": "final_model.js " + DELIVERED}) + "\n")
        check("active stop hook never blocks", run({"stop_hook_active": True, "transcript_path": good, "session_id": "a"}) == 0)
        check("no delivery in transcript does not block", run({"transcript_path": undelivered, "session_id": "b"}) == 0)
        check("out of time does not block", run({"transcript_path": late, "session_id": "c"}) == 0)
        check("garbage input does not block", subprocess.run([sys.executable, os.path.abspath(__file__)], input="not json",
                                                            capture_output=True, text=True, env=env).returncode == 0)
        check("delivered with time left blocks once", run({"transcript_path": good, "session_id": "d"}) == 2)
        check("second stop in same session passes", run({"transcript_path": good, "session_id": "d"}) == 0)
        os.makedirs(os.path.join(tmp, "w"))
        open(os.path.join(tmp, "w", MODEL_NAME), "w").close()
        check("no transcript but model file present blocks", run({"cwd": os.path.join(tmp, "w"), "session_id": "f"}) == 2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("selftest %s" % ("FAILED" if fails else "OK"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

```

