# auto_analysis 方案设计（附录 A · 方案 A：client 侧工作流，默认）
> **工具索引**：本文件为 auto_analysis 方案 A（client 侧工作流）文档，不注册 MCP 工具、无 manual 小节。
> 「需要多少样本量/功效多大」类问题 → power_analysis（工具 27，v1.1.0 起；solve_n/detect_effect/verify 三模式，参数见 statlab_mcp/docs/design/10_power_analysis.md）。
> 「帮我规划分析步骤」类问题 → **analysis_plan（工具 30，v1.2.0 起已实现）**：方案 B 确定性
> 规则引擎，输入问题+数据源即产出 `{intent, chosen_methods, tool_calls_plan}` 计划
> （词表/伪键/边界见 statlab_mcp/docs/design/11_analysis_plan.md）；本文件方案 A 仍是
> client 侧工作流的完整决策树版本，两者互补。

> 定位：编排层（第二层）。**不是 MCP 工具**，而是一份交付物：
> ①《分析方法选择决策树》②《报告模板》③《示例 agent 提示词》。
> 由外层 agent（Claude Code / Cursor / DSH 等）按决策树调用第一层 30 个工具、
> 套模板生成报告。本方案不向 server 增加任何代码，零风险。

## 一、与方法选择决策树（外层 agent 的调用地图）

输入：数据文件 + 自然语言问题 → 先跑 **describe_statistics + data_type_check + missing_report**
（数据概览三件套，任何问题都先看），再按下表选方法：

| 问题类型（大白话） | 判定线索 | 工具链（按顺序） | 关键输出 |
|---|---|---|---|
| 数据长什么样 | "分布/概况/描述" | describe ✓ type_check ✓ missing ✓ + plot_histogram | n/mean/缺失率 |
| 哪两列一起变 | "相关/关系"（连续列） | correlation_matrix → plot_heatmap → plot_scatter | r、p、热力图 |
| 类别有没有关联 | 两列都是类别 | chi_square_test | χ²、V、Fisher 自动 |
| 一组均值是不是 X | "均值是不是/是否等于" | normality_test → hypothesis_test(one_sample) → effect_size | t、p、d |
| 两组谁高 | "A 组比 B 组" | normality_test → hypothesis_test(independent) | Welch t、CI、d |
| 多组谁高 | "三组/分部门对比" | anova_test（自动 Levene→Welch→Tukey/Games-Howell） | F、事后对 |
| 预测连续值 | "预测/影响收入" | linear_regression → feature_importance | R²、VIF、重要性 |
| 预测是/否 | "能不能确定/会不会买" | logistic_regression（二分类） | AUC、OR |
| 把人分几堆 | "分成几类人/分群" | cluster_analysis(k±1 对照) → pca_analysis | 轮廓、质心 |
| 未来怎么走 | "下月/趋势/预测" | trend_analysis → seasonal_decompose → time_series_forecast | tau、斜率、预测 |
| 预测可信吗 | "预测准不准/回测" | backtest_forecast（v1.2.0 工具 29：滚动回测，验证窗只认原始观测） | MAE、RMSE、MAPE |
| 缺失想直接补 | "补齐缺失/插补后分析" | impute_missing（v1.2.0 工具 28：五策略，结果落 reports/imputed/，绝不覆写输入） | 补齐数、输出文件 |
| 有没有异常 | "异常/突变/离群" | outlier_detect / anomaly_detect（时序） | 异常点+图 |

**决策规则（agent 必须遵守）**：
1. 先跑数据概览三件套再选型；描述里注明"已确认 n=xx、缺失率 xx%"
2. 目标列类型决定工具：类别→chi_square/Logit；连续→t/ANOVA/回归；日期列→时序组
3. 样本量门槛照抄工具报错（n<50 特征重要性拒算时如实转告，不硬跑）
4. **想用的方法未实现 → 如实告知"暂不支持"，禁止心算替代**（如数据非正态的后续可选
   nonparametric_test（工具 26）：Wilcoxon/Mann-Whitney/Kruskal-Wallis）

## 二、报告模板（固定五章节）

标题：`<文件名> 数据分析报告（生成时间）`

```
## 1. 数据概览
- 样本量 N=xx，列数 M=xx；缺失率 xx%（高缺失列：xxx）
- 列类型摘要：数值 x 列、类别 y 列、日期 z 列（脏值提示：xxx）   [来源: describe_statistics / data_type_check / missing_report]

## 2. 方法选择理由
- 问题类型：<从决策树选择的类型>
- 使用工具：<工具链列表>；理由：<1-2 句，如"score 为连续列、比较两组均值 → Welch t" >
- 未采用的方法及原因：<如"数据非正态，已转用 nonparametric_test（工具 26）"或"暂不支持，如实告知">（若有）

## 3. 结果
- 每个小节：结论句 + 关键数字表/图（`__image__` 路径注明）
- 引用格式：`数值（来源: <工具名> 的 <字段，如 score.mean>）`
- 图：`图 1：xxx（__image__ 路径）`

## 4. 结论
- 每一条结论必须对应一个来源数字（格式同上）；无来源数字禁止出现

## 5. 局限
- 固定声明：样本量 N=xx（<30 注明功效弱）；p 值是否经多重比较校正
  （</u>如 fdr_bh/Tukey 族校正）；相关≠因果；模型未做外部验证
```

**防幻觉铁律（agent 硬约束，写入提示词）**：
1. 报告中每个统计数字必须来自第一层工具返回 JSON 并标注 `[来源: 工具名.字段]`
2. 任何无来源数字禁止出现；LLM 只能解释和转述数字，不能产生数字
3. 想用的方法未实现 → 如实告知，禁止心算替代

## 三、示例 agent 提示词（可直接粘贴给 Claude Code / Cursor / DSH）

```
你是数据分析助手。规则（必须遵守）：
1. 分析开始前，把数据文件路径告诉我确认；所有数字必须来自 MCP 工具返回的 JSON。
2. 先调用 describe_statistics、data_type_check、missing_report 三个工具，用真实输出填写
   "数据概览"章节。
3. 按下列决策树选择方法并说明理由（"方法选择"章节）：
   [粘贴上文决策树表格]
4. 调用所选工具时，把完整 JSON 保留在对话；报告中引用数字一律写 [来源: <工具名>.<字段>]。
5. 生成固定五章节报告（数据概览/方法选择理由/结果/结论/局限），局限章节必须包含：
   样本量、p 值是否多重比较校正（以工具输出为准）、相关≠因果、未做外部验证。
6. 任何时候不得自己计算或估算数字（心算=造假）；工具报错时，把错误原文放进报告并说明。
7. 图类工具返回 __image__ 绝对路径时，用你的图片读取能力看图并描述所见，
   不要编造图中没有的特征。
```

## 四、验收建议（方案 A 的测试方式）
- 用 samples/clean.csv 跑一遍「数据概览三件套 → correlation_matrix → plot_heatmap」，
  人工核对报告数字与工具 JSON 一致；
- 用 data/销量.csv 跑「describe → histogram → 时序（若含日期）」，核对图与数字；
- 抽查报告：任意数字随机挑 3 个，在对应工具 JSON 里定位到字段（来源标注有效性）。

## 五、本方案的取舍声明（附录 A 二选一，选 A）
- 不向 server 加代码 → 第一层 27 工具全保持纯计算（可测可追责）；
- 报告质量依赖外层 agent 遵守提示词——铁律写在提示词里，验收按第四节抽查；
- 若未来想 server 侧自动化（方案 B 规则工具），需另出设计文档，不混用。
```
