# RSI Lab

RSI Lab explores whether an agent can improve its own workflow by proposing changes, testing them, and learning from the results.

The idea is independent of a particular model. **Chem uses Sonnet 5.5 through native Claude Code. Bio uses GPT-5.6 Terra at max effort through native Codex for every role.** The Bio adapter is undergoing its first experimental run; other backends require adapters.

[Website](https://jihaizhao.github.io/rsi-lab/) · [AS-Bench](https://github.com/Yibo-Wen/as-bench) · [Method inspiration: RRSI](https://regularized-rsi.com/)

## How it works

1. **Analyze:** read public task instructions and, after the first round, this experiment’s scores and execution traces.
2. **Propose:** edit a copy of the retained harness and state the expected effect.
3. **Review:** a separate critic checks the proposal for leakage and changes outside the allowed boundaries.
4. **Evaluate:** run fresh task agents with the candidate; use the official benchmark verifier.
5. **Select:** keep an eligible improvement as the next parent. Preserve rejected proposals and their evidence too.

The editable harness can contain instructions, skills, helper scripts and supported native hooks. Instructions and helpers can also manage task-local notes and workflow checks. The model weights, native conversation/tool loop, task environments and scoring rules remain fixed.

This is an experimental implementation inspired by recursive self-improvement. It does not reproduce the full RRSI paper or its held-out evaluation protocol.

## Current chemistry experiment

- Tasks: Propylene active learning and Suzuki condition screening.
- All model roles: `claude-sonnet-5-5`, high effort.
- Each candidate: three trials per task, six trials total.
- Budget: at most five modification rounds, one candidate per round.
- First acceptance: at least three official passes out of six, with no execution errors.
- Later acceptance: more total passes than the retained candidate, with no decline on either task. Ties retain the parent.
- No local H0 baseline rerun and no additional final repeats.
- The user-specified **33.3%** benchmark value is an external reference, not a paired local baseline.
- Results are evolve-task scores used during selection, not evidence of generalization.

The website includes a dated snapshot of observed results. Pending evaluations are not zero scores. Full local trajectories and credentials are excluded from Git.

## Repository map

| Path | Purpose |
| --- | --- |
| `src/evolve.py` | Analyst → proposer → critic → evaluation → selection controller |
| `src/native_agent.py` | Fixed bridge that loads a candidate into native Claude Code |
| `src/native_bundle.py` | Bundle validation and source hashing |
| `src/run_job.py` | Subscription guard and Harbor job launcher |
| `src/evaluation.py` | Official rewards and execution/model audits |
| `src/subscription_auth.py` | Load subscription credentials into process memory |
| `src/update_website.py` | Export the active experiment’s public snapshot |
| `config/experiment.json` | Recorded experimental protocol |
| `harness/H0/` | Immutable baseline definition and provenance |
| `harness/working/` | Empty extension starting point |
| `website/dist/` | Static English website and interactive process diagram |
| `tests/` | Offline protocol and adapter checks |
| `reference/harbor/` | Upstream adapter snapshot with its license |

`src/final_evaluate.py` is a legacy helper from an earlier protocol. It is not used by the current experiment, which has no final repeat phase.

## Local setup

Requires Python 3.12, Docker, Node.js, and a Claude Max account already authenticated through Claude Code. The role container installs Claude Code 2.1.293; Harbor is pinned to 0.21.0.

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

git clone https://github.com/Yibo-Wen/as-bench external/as-bench
git -C external/as-bench checkout 86159f8b9e6ab3ba08777209d095c1415abf97a5

docker build -f infrastructure/roles.Dockerfile -t rsi-sonnet-roles:2.1.293 .
python -m unittest discover -s tests
```

Keep runtime credentials outside this repository. The current adapter reads an existing Claude Code OAuth session from `~/.claude/.credentials.json`. It requires extra-usage billing to be disabled, checks subscription availability before calls, and stops on limits rather than switching to paid API billing. This authentication path is specific to the current runtime, not a universal model API.

## Run a fresh experiment

Review `config/experiment.json` and set a new, unused `experiment_id` before starting. A completed or interrupted run is never silently resumed.

```bash
python src/evolve.py --domain chemistry
```

This starts real model calls and task containers using the configured subscription. The controller archives each proposal, diff, critic decision, evaluation and selection under `runs/experiments/<experiment_id>/`. Earlier experiments are not passed into a fresh run. Do not give agents private benchmark truth or solutions.

The original H0 remains native Claude Code with no extension bundle; loading a candidate does not make it H0. Candidate code must not edit the fixed bridge or verifier.

## Preview the website

```bash
# Refresh only after local run records exist for the configured experiment.
python src/update_website.py
python -m http.server 8766 --directory website/dist
```

Open `http://localhost:8766`. The site is plain HTML, CSS and JavaScript; it needs no build step. The included `experiment.json` is a published snapshot, not a live stream. Website publication is separate from running the experiment.

## Provenance

The AS-Bench checkout is pinned in the experiment configuration and is not vendored here. The archived Harbor adapter retains its upstream license in `reference/harbor/LICENSE`. See `REQUIREMENTS.md` for the recorded experiment requirements.

The public website is deployed by `.github/workflows/pages.yml`. Pushing changes to `website/dist/` on `main` publishes the updated snapshot to GitHub Pages; it does not run experiments in GitHub Actions.

## Bio experiment

All four roles use GPT-5.6 Terra with max effort and the existing Codex subscription. Two official Bio tasks, three trials each, at most five modification rounds. No baseline rerun or external reference. Mixed-model interrupted batches are preserved and excluded. Build `infrastructure/codex-roles.Dockerfile` as `rsi-terra-roles:0.154.0`, then run `python src/evolve.py --domain biology --config config/bio-terra.json`. Role events stream to local logs, and model/effort are checked against native session records before advancing.
