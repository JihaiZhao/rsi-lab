# RSI Lab framework v2: design

Status: implemented offline (no model calls). A new experiment needs an explicit
budget authorization recorded in its config before `src/rsi_run.py` will start.
Archived experiments, `src/evolve.py` and its one-off helpers are unchanged and
remain the code of record for earlier runs.

## Goals

1. **Model- and harness-independent controller.** The loop, archive, gate and
   selection code never names a model or a CLI. Runtimes are adapters.
2. **Native harness stays fixed.** H0 is the unmodified native agent (Claude Code,
   Codex, ...). RSI only adds a portable extension bundle through the harness's
   supported interfaces.
3. **Spend evaluation quota only on candidates that can run.** Static checks,
   leakage scans, smoke tests and critic review happen before any task trial,
   with a bounded repair loop.
4. **Honest selection under a tiny, noisy budget.** Pre-registered rules, a
   noise floor, and simplicity/cost as the only in-band tie-breakers.
5. **Rich, navigable evidence.** Every candidate is archived and readable by later
   roles. Trial cards help navigation; raw trajectories stay available.

## Three layers

```
controller (src/rsi/controller.py)       model-agnostic loop, ledger, archive
  ├── RoleRuntime.run(...)               analyst / proposer / critic
  ├── PolicyRuntime.agent_spec(...)      task agent with bundle loaded
  └── gate, evidence, selection          pure Python, offline-testable
runtime adapters (src/rsi/runtimes/)     claude_code, codex; each has Capabilities
portable bundle (src/rsi/bundle.py)      one format, compiled per runtime
```

### Portable bundle

| Path | Component | Claude Code | Codex |
|---|---|---|---|
| `instructions.md` (required) | instructions | appended system prompt | developer instructions |
| `skills/<name>/SKILL.md` (+ scripts) | skill | native skills | native skills |
| `tools/*.py`, `tools/*.js` | tool | invoked by the agent | invoked by the agent |
| `mcp/servers.json` + `mcp/*.py` | mcp | native MCP (stdio) | native MCP (stdio) |
| `hooks.json` | hook | compiled to `settings.json` hooks | not supported (capability off) |
| `memory/` | memory | task-local files | task-local files |
| `smoke.json` | smoke tests | run by the gate, never by the task agent | same |

Neutral hook events are `session_start`, `pre_tool`, `post_tool` and `stop`.
Each runtime publishes `Capabilities`. The proposer only sees supported
components, and the validator rejects anything the target runtime cannot load.
MCP servers are stdio only, are launched with `python3` from `/opt/rsi-harness`,
and must not open network connections or call models.

## Round state machine

```
prepare → analyst → plan → implement → gate ⇄ repair → critic ⇄ repair
        → screen eval (1 trial/task) → [top-up eval (2 more/task)] → select → record
```

* Every step writes its files and a line to `ledger.jsonl` before the next one starts.
* There is no automatic resume and no retry of evaluations. Any exception writes
  `stopped.json` and ends the run.
* Repairs (default ≤3 per round, shared by gate and critic) are proposer edits
  before any trial is spent. They are not evaluation retries.
* A round that never passes the gate or critic counts against the round budget.

## Evaluation budget (cascade, pre-registered)

* Screen: 1 trial per task.
* Stop early only if the screen passes 0 trials **and** the incumbent pass rate
  is at least `screen.stop_if_zero_and_incumbent_at_least` (default 0.5).
* Otherwise top up to `trials_per_task` (default 3). Selection always uses the
  full set of planned trials. Screened-out candidates are reported as such and
  never as failed full evaluations.

## Selection (pre-registered)

Let S be the pass rate over all trials, `S*` the best score among accepted
candidates in this experiment (a lucky unaccepted score does not raise the floor), and δ the noise band (default 1/6, one trial out of six).

1. Any execution, model-audit or API error blocks selection and stops the run.
2. No incumbent yet: the first complete, valid candidate becomes the measured
   incumbent. No improvement claim against unmeasured H0.
3. Floor: reject if `S_c < S* − δ`.
4. Credible gain: accept if `S_c > S_i` and the Beta(1,1) posterior
   `P(p_c > p_i) ≥ p_accept` (default 0.8; with 6 vs 6 trials this needs +2 passes).
5. In band (`|S_c − S_i| ≤ δ`): accept only if the candidate is simpler
   (fewer non-blank lines) or uses at least `token_saving` (default 15%) fewer
   tokens per trial without being more complex. A gain inside the band alone
   never wins.
6. Otherwise keep the parent ("unresolved").

All results are evolve-set scores. With six binary trials per candidate the 95%
interval is roughly ±35–40 points, so reports must show trial counts and
posteriors, never a bare "improvement".

## Proposal contract

The planner returns a structured plan before any file is edited:

* `problem`, and `evidence` as a list of `{trial, step, observation}` references.
* `edits`: at most `edit_budget[round]` entries (default `[2, 2, 1, 1, 1]`), each
  with `component`, `hypothesis` and `files`.
* `predictions`: per task `improve | same | worsen`, plus `token_effect`.
* `why_not_simpler`, `regression_risk`, `retroactive_check`.

Changed files must be declared by an edit (supporting `instructions.md` edits are
allowed). After evaluation, predictions are scored and fed back as a scoreboard.
The hypothesis ledger records each mechanism as `supported`, `refuted`,
`unresolved` or `not_evaluated`. When the last two evaluated rounds produced no
accepted gain, the next plan must use a component not yet tried or give an
evidence-based waiver.

## Evidence

`evidence/` mounted read-only for every role:

* `INDEX.md`: rounds, decisions, scores, posteriors, hypothesis ledger, scoreboard.
* `archive/round-NN/`: candidate source, diff, plan, gate report, critic verdict,
  decision.
* `archive/round-NN/trials/<task>/<trial>/card.json` and `trajectory.json`.
  Cards are deterministic: step and tool-call counts, tool histogram, observed
  errors, duration, tokens, harness-component references, final message excerpt.
* `tasks/<task>/instruction.md`: official public instructions only.

Only official task inputs, in-episode measurements, official rewards and this
experiment's own records enter evidence. No earlier experiment is mounted.

## What is deliberately not here

* No improver-level recursion yet. Analyst/proposer/critic prompts are fixed
  controller code. Planned after several complete experiments exist.
* No hand-written domain mechanisms in the initial bundle. It starts empty so
  that any mechanism is attributable to the RSI loop.
* No open-source harness. Adding one means a new runtime adapter and its own
  billing authorization.
