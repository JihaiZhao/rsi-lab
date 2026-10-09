# 用户需求与讨论交接

## 核心问题

用户关心的不是换更强模型，而是：同样的 Sonnet 5.5，在原生 Claude Code
harness 下表现有限，经过自己的 RSI 改进后，能否表现更好？
结论必须由实际评估支持，不保证一定提升，不为通过而改评分器或挑选结果。

## 已确定

1. 所有实验模型角色均为 Sonnet 5.5，包括独立 proposer、critic 和执行 agent。
   不能让其他更强模型写改进，再把它称为全 Sonnet 的 RSI。
2. H₀ 是原生 Claude Code + Sonnet 5.5，保留工具使用、执行代码和多轮对话。
   不能将其替换成无工具的单轮调用。
3. 使用 AS-Bench 原始任务、实验预算、实验室 API 和官方 verifier；不混入旧的
   120 seed / 30 picks、glass-model 或自定义 twin 协议。
4. 单独的 proposer 改写我们拥有的 harness 扩展代码。它不代替执行 agent 选实验，
   不修改模型权重，也不修改 Claude Code 的闭源内部实现。
5. 可改的不仅是几份固定策略文本；允许策略、skills、工具、上下文/记忆机制、
   子调用和扩展层流程。先明确原生 Claude Code 接口能承载哪些改动，不夸大可编辑范围。
6. 实际递归过程应为：运行当前版本 → 从其轨迹获得反馈 → proposer 提案 → 检查 →
   评估 → 按预定规则接受/拒绝。接受的版本成为后续修改的父版本。
7. 每个新实验可以从固定 H₀ 重启；同时重置 proposer 会话、记忆和证据目录。
   不继承旧运行的候选工具、失败结论或 OOD 成绩。
8. Evolve 成绩可以公开报告。必须标注 role，不能把开发集成绩写成泛化成绩。
9. 网站最终需要清楚展示角色模型、任务数和试跑数、真实提案/diff、接受过程、成本，
   以及各领域 evolve 搜索成绩与最终复测成绩；不再把所有阶段混成不明含义的 H₀/H₁/H₂ 表格。
10. 代码及时 commit；记录失败与中断，不静默删结果或补造分数。

## 最新用户确认：Chem-only，从头开始

只使用 Propylene 与 Suzuki 两个正式 Chem 任务，不再运行 Bio。
新 experiment_id 为 chem-rsi-fresh-20261007。此前本地 H0 批次按用户要求停止，
保留原始记录，但不得把任何旧评分、轨迹、候选或结论传给新角色。

每个候选：2 个任务 × 3 次 trials = 6 次评估。每轮 1 个候选，最多修改 5 轮。
拒绝轮次也计入上限。不另跑本地 H0 或额外最终复测。
用户指定 benchmark 的 33.3% 作为外部参考；不能声称与本地完全匹配或归因提升。
首个本地候选至少通过 3/6 次才接受；之后与已接受本地版本比较，严格提高总体
通过率且逐任务通过率无回退才接受。同分保留父版本。没有候选获接受时保留未测的 H0，
仍报告所有实测候选。最终选定版本的成绩是参与选择的 evolve 成绩。
第一轮只有官方公开任务输入，没有本地基线轨迹；从 Sonnet 提案直接开始。

## 模型与费用

policy、proposer、critic、analyst、subagent 全部 Sonnet 5.5。
仅使用现有 Claude Max 订阅；付费 API 为零，额外计费必须关闭。额度耗尽停止，
不切换计费方式、不自动重试中断运行。凭据只在仓库外与进程内使用。
H0 仍为不可变原生 Claude Code，不修改其归档 manifest。

## 网站交付

展示真实流程、源码哈希、每轮提案和 diff、critic 结论、接受或拒绝、
每任务通过数/3 与总通过数/6、token 与标价估算。33.3% 单独标为外部参考。
不混入此前 Bio 或本地基线数据，不隐去失败和中断，不宣称完整复现 RRSI。

## Framework identity

The project is RSI Lab, a model-independent RSI framework concept. Sonnet 5.5 is the fixed backend for the current chemistry experiment, not the framework name. The website must use plain English and explain the actual improvement loop before presenting performance. Other model backends require compatible runtime adapters and have not been validated in this experiment.

## Authorized round 5 reevaluation

The user explicitly requested rerunning round 5 after OAuth failures. Run a new, separately named batch with the unchanged candidate and three trials per task. Preserve the original six outcomes and stop record. Compare the new complete batch with the retained candidate under the existing selection rule. This adds no proposal or sixth modification round and does not authorize automatic retries or paid billing.

## Fresh Bio RSI (user authorized)

Run the two official Bio tasks directly through RSI, three trials per task and at most five modification rounds, with no local baseline or OOD phase. The task agent uses native Codex 0.154.0 with GPT-5.6 Terra at max effort, using the existing ChatGPT/Codex subscription only. Analyst, proposer and critic remain Sonnet 5.5 under the existing Claude Max subscription. Keep this mixed-model experiment separate from Chem; do not claim all-Terra self-improvement. Start with an empty extension and no earlier trial evidence. The first complete, valid candidate establishes the incumbent without a baseline-improvement claim; later acceptance requires strict aggregate improvement with no per-task regression. Do not transfer Chem's 33.3% reference to Bio. Stop on authentication, quota, model audit or execution errors without automatic retry. Credentials stay outside the repository; the native Harbor bridge injects only runtime auth into the isolated task container, never user settings or memory.

## Superseding Bio model correction

The user requires ALL Bio roles (policy, analyst, proposer, critic, and any child agents) to use GPT-5.6 Terra at max effort through the existing Codex subscription only. The mixed-model batches are interrupted and excluded from new evidence. Start from an empty extension in a new experiment. Chem remains unchanged.

## Latest Chem Luna authorization

Run a fresh independent Chem RSI with GPT-5.6 Luna in every role, max effort, native Codex and existing subscription only. Two official Chem tasks, three trials each, at most five modification rounds. Use config/chem-luna.json; empty initial extension, no old candidate or trajectory evidence, no baseline rerun. First valid candidate establishes the measured incumbent; do not treat Sonnet external scores as a Luna baseline. Preserve earlier experiments unchanged.

## Framework v2 Chem Sonnet run (authorized 2026-10-09)

The user authorized a fresh run of framework v2 (docs/DESIGN.md) with config/chem-sonnet-v2.json:
Sonnet 5.5 for policy and every role, the two official Chem tasks, at most five rounds, cascade
evaluation (1 screen trial per task, top-up to 3), pre-registered noise-aware selection, existing
Claude Max subscription only, no local H0 rerun and no evidence from earlier experiments.
