# Working agreement

Read README.md and REQUIREMENTS.md before making changes.

- This is a fresh RSI workspace. Experiments are PAUSED at the user's request.
  Setup, documentation and offline tests are allowed; do not run model calls,
  benchmark jobs or background monitors until the user resumes experiments.
- Policy, proposer, critic, analyst and subagent models must all be Sonnet 5.5.
- H0 is native Claude Code, without a custom extension bundle. Do not change its
  archived manifest or call a thin one-turn model wrapper H0.
- Keep the native conversation/tool loop. Candidate extensions are separate from
  the fixed bridge, task environments, measurement data and verifier.
- Do not read other project directories, old transcripts, old result archives or
  previous harness candidates as evidence for new proposals.
- Biosensor=evolve and Nuclease=OOD is a DRAFT pending protocol discussion. Never
  send OOD instructions, outcomes or trajectories to the proposer. Fix the selected
  source hash before OOD evaluation; never select a version by its OOD performance.
- Do not inspect private benchmark truth or solutions. Only official task-public
  inputs and in-episode measurements may reach the task agent.
- Do not silently resume or retry interrupted runs. Preserve all outcomes.
- Runtime credentials belong outside this repository. Never copy account tokens,
  user settings, global memory, or .claude credentials into this workspace.
- Commit concrete changes promptly. Do not claim results that have not run.
