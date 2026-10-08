# Working agreement

Read README.md and REQUIREMENTS.md before making changes.

- The user resumed experiments on 2026-10-07. Prepare and run the fresh experiment,
  subject to its recorded budget: existing Claude Max subscription only. No paid API
  or extra-usage billing. Stop on quota exhaustion; never switch billing routes.
  No background monitors are requested.
- Policy, proposer, critic, analyst and subagent models must all be Sonnet 5.5.
- H0 is native Claude Code, without a custom extension bundle. Do not change its
  archived manifest or call a thin one-turn model wrapper H0.
- Keep the native conversation/tool loop. Candidate extensions are separate from
  the fixed bridge, task environments, measurement data and verifier.
- Do not read other project directories, old transcripts, old result archives or
  previous harness candidates as evidence for new proposals.
- Latest user scope: fresh Chem-only RSI on the two official chemistry tasks.
  Evaluate every candidate with 3 trials per task, at most 5 modification rounds.
  Do not run a local H0 baseline. Show the user-specified benchmark 33.3% only as
  an external reference, never as a paired local improvement estimate.
  Exclude all earlier runs, including this workspace's H0 batch, from new roles.
  There is no OOD set; report evolve performance without generalization claims.
- Do not inspect private benchmark truth or solutions. Only official task-public
  inputs and in-episode measurements may reach the task agent.
- Do not silently resume or retry interrupted runs. Preserve all outcomes.
- Runtime credentials belong outside this repository. Never copy account tokens,
  user settings, global memory, or .claude credentials into this workspace.
- Commit concrete changes promptly. Do not claim results that have not run.

- User permits Codex co-authorship: add `Co-authored-by: Codex <noreply@openai.com>` to future Codex-assisted commits; preserve the user as primary author and do not rewrite existing history.

## Latest Bio authorization

The user additionally authorized a fresh Bio-only RSI experiment with GPT-5.6 Terra (max) as the task policy through existing Codex subscription, two tasks × three trials, at most five modification rounds, no baseline rerun. Sonnet-only role constraints still apply to analyst, proposer and critic. Use config/bio-terra.json and isolated evidence; do not modify the archived Chem H0 or inherit its candidates. No paid API, extra credits or implicit retries.

## Superseding Bio model correction

The user requires ALL Bio roles (policy, analyst, proposer, critic, and any child agents) to use GPT-5.6 Terra at max effort through the existing Codex subscription only. The mixed-model batches are interrupted and excluded from new evidence. Start from an empty extension in a new experiment. Chem remains unchanged.
