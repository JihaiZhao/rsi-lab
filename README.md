# Sonnet 5.5 RSI · 全新工作区

**状态：用户已授权开始实验；使用现有 Max 订阅开始运行；禁止付费 API 与额外计费。**

目标是在同一个 Sonnet 5.5 模型下，检验 RSI 改进的 harness 是否比原生
Claude Code harness 更有效。实验 policy、proposer、critic、analyst 和 subagent
全部使用 `claude-sonnet-5-5`。模型不换，权重不训练。

先读 [需求总结](REQUIREMENTS.md)，再讨论 [实验草案](config/experiment.json)。
这里没有旧项目的提案、结果、失败轨迹、实验真值、会话记忆或凭据。
这意味着新 proposer 可以从空白上下文开始，不意味着历史实验从未发生。

## 基础版本 H₀

[H₀ manifest](harness/H0/manifest.json) 定义：原生 Claude Code + Sonnet 5.5，
high effort，无自定义 prompt、工具、skills 或 hooks。保持原生对话和工具循环，
不是单次 LLM 调用。软件版本固定为 Harbor 0.21.0、Claude Code 2.1.293。

[原生适配器快照](reference/harbor/claude_code.py) 是 Harbor 启动 Claude Code 的
公开 Python 适配器，不是 Claude Code 内部运行循环的全部源码。
实际 H₀ 通过已安装 Harbor 的 `claude-code` agent 加载；快照仅用于审计。
[文件哈希](harness/H0/provenance.json) 用于核对起点。

`harness/working/instructions.md` 是空的扩展入口，没有任何演化策略。
未来的候选可以添加策略、skills、工具与 hooks。它还不是一个已评估版本，
更不可以把加载了扩展包的运行冒充裸 H₀。

## 已剥离的基础代码

- `src/native_agent.py`：保持 Harbor 原生 `ClaudeCode.run`，加载候选扩展包；不是 proposer。
- `src/native_bundle.py`：源码哈希、文件和语法检查；它是检查器，不是安全沙箱。
- `src/job_spec.py`：只生成配置，区分裸 H₀ 与候选；不会调用模型或启动 Docker。
- `reference/harbor/`：原生适配器快照及许可证。
- `runs/`：每个实验独立封存配置、角色模型、轨迹、成绩与用量。
- `external/`：已准备固定版本的官方 benchmark。

没有搬运旧的自定义模型循环、Chemistry 优化工具、搜索控制器和网页成绩。
多轮 RSI 控制器已实现，候选由隔离容器中的 Sonnet 原生循环产生；搜索预算和接受规则已在 config/experiment.json 记录。Bio、Chem 分别独立演化，四个正式任务全部为 evolve，不设 OOD。

## 只读检查

建议使用 Python 3.12。依赖版本见 `requirements.txt`；这里没有自动安装或运行脚本。

```bash
python -m unittest discover -s tests
PYTHONPATH=src python src/job_spec.py --arm baseline --task biology/jewett-lab/biosensor-active-learning
```

第二条命令只把 Harbor job 配置打印到终端。没有后台任务，没有定时任务，
没有调用模型，也不会下载任务数据。已获恢复授权；仅使用现有订阅执行模型调用。

## 参考方法

- [AS-Bench](https://github.com/Yibo-Wen/as-bench)：官方任务与实验室 API、评分器。
- [RRSI](https://github.com/google-research/rrsi)：领域内演化，再冻结做 OOD 测试。
- [Meta-Harness](https://github.com/stanford-iris-lab/meta-harness)：开放 harness 的自动改进。

这些是方法参考。本项目目前只准备了干净的起点，不能宣称已复现 RRSI。
