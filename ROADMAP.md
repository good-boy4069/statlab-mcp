# 路线图（ROADMAP）

> 依据 2026-08-26 第三份外部锐评（Qoder）的"下一步迭代大方向"整理；状态随版本更新。
> 所有承诺都遵循项目铁律：确定性（seed 42）、第一层零 LLM、手算对照测试、中文全链路。

## 短期（1-2 周）—— v1.0.3 ✅ 已全部完成

- [x] **PyPI 发布 + 一行启动**：`pip install statlab-mcp` / `uvx statlab-mcp` / `pipx run statlab-mcp`（console script `statlab-mcp`）
- [x] **packaging 惯例修复**：pyproject 写入 dependencies（范围约束，下限=锁定版本），双轨说明（requirements=开发/CI 锁定权威）
- [x] **CI 覆盖率证据**：pytest `--cov=statlab_mcp --cov-fail-under=80` + 覆盖率进 job summary；README 真实 Actions 徽章
- [x] **README 数字防漂移**：`tests/check_readme_claims.py`（pytest 数、工具数 26 与实现比对，不符 CI 红）
- [x] **非参检验落地**：`nonparametric_test`（工具 26：Wilcoxon / Mann-Whitney / Kruskal-Wallis + 效应量 + 12 个手算对照用例），hypothesis_test / normality_test 的"未实现"警示闭环
- [x] **参数命名文档化**：SPEC 第 2 节命名约定表（不重命名既有工具，见"决策记录"）
- [x] **社区基建**：CONTRIBUTING.md、ROADMAP.md（本文）、CHANGELOG.md、issue 模板（bug/feature）
- [x] **Docker**：Dockerfile（python:3.13-slim + Noto CJK + PYTHONUTF8）+ .dockerignore + README 段

## 中期（1-2 个月）

- [ ] **时序回测/滚动验证**：forecast 的预测可信度自评（滚动窗口 backtest + MAE/RMSE），随工具输出或独立工具
- [ ] **auto_analysis 方案 B 落地**：把决策树（design 08）变成确定性规则工具，输出 `{chosen_methods, tool_calls_plan}`（第一层工具原则不变）
- [ ] **依赖双版本兼容矩阵**：CI 增加"依赖下限" job（如 pandas 3.0.x 下限组合），为 PyPI 范围约束提供实测背书
- [ ] **inline 小数据通道**：允许直接传数组参数（如 `values=[...]`），免去小数据落盘（需同步收紧安全边界：inline 数据的来源说明）
- [ ] **缺失值插补工具**：简单可复现的确定性插补（均值/中位数/前向），与 missing_report 互补

## 长期（3 个月+）

- [ ] **StreamableHTTP transport + 多用户服务化**：从本地 stdio 到可远程的统计后端服务（架构级，需重设计鉴权/限流/数据隔离；与"仅本地路径"安全模型冲突，需先立新安全规范）
- [ ] **英文 README 与国际化**：走国际社区；DOCS_EN.md 或 i18n 全量并行
- [ ] **第二位维护者与社区**：CONTRIBUTING 已就绪，欢迎 PR；bus factor 从 1 起步
- [ ] **数据集注册/会话机制**：避免每次调用重复读文件（配合服务化一起设计）

## 决策记录（为何这样取舍）

| 决策 | 理由 |
|---|---|
| 参数命名**文档化而非全面重命名** | 既有命名有内在分场景一致性（SPEC 第 2 节）；25→26 工具已是破坏性变更窗口，全面重命名代价高收益低；若未来生态反馈强烈，可再立"重命名计划 + 别名兼容期" |
| 依赖**双轨而非单一范围** | 确定性承诺（逐字节可复现）依赖锁定；发布可用性依赖范围。requirements=锁定权威 + pyproject=范围下限，CI 以锁定验证 |
| PyPI 版本不可删（只能 yank） | PyPI 平台规则；发布顺序冻结（详见 CONTRIBUTING 发布流程），错误发布用 yank+补丁版处置 |
| STL/IQR/zscore 之外不画蛇添足 | 每加一法都要手算对照测试与 design 文档；宁缺毋滥（"25 工具零 LLM"的纪律优先于功能堆砌） |