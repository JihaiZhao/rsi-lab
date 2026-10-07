# Working agreement

Read README.md and REQUIREMENTS.md before making changes.

- The user resumed experiments on 2026-10-07. Prepare and run the fresh experiment,
  subject to its recorded budget. Do not start paid/model calls while the requested
  budget answer remains pending. No background monitors are requested.
- Policy, proposer, critic, analyst and subagent models must all be Sonnet 5.5.
- H0 is native Claude Code, without a custom extension bundle. Do not change its
  archived manifest or call a thin one-turn model wrapper H0.
- Keep the native conversation/tool loop. Candidate extensions are separate from
  the fixed bridge, task environments, measurement data and verifier.
- Do not read other project directories, old transcripts, old result archives or
  previous harness candidates as evidence for new proposals.
- All official Bio and Chem tasks at the pinned benchmark commit are evolve.
  Evolve one independent harness per domain from H0. There is no OOD set.
  Protein is archived upstream and outside the pinned dataset allowlist.
  Report development performance honestly; do not claim unseen-task generalization.
- Do not inspect private benchmark truth or solutions. Only official task-public
  inputs and in-episode measurements may reach the task agent.
- Do not silently resume or retry interrupted runs. Preserve all outcomes.
- Runtime credentials belong outside this repository. Never copy account tokens,
  user settings, global memory, or .claude credentials into this workspace.
- Commit concrete changes promptly. Do not claim results that have not run.
