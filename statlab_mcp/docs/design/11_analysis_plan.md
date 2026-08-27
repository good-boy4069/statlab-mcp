# analysis_plan 设计文档（v1.2.0 · 工具 30 · 编排层方案 B）
> **工具索引**（v1.1.0 起 statlab://tools/<名>/manual 取本文件对应小节，锚点=一级标题行“# 工具 N：<函数名>(”）：analysis_plan（工具30，v1.2.0）

# 工具 30：analysis_plan(question, file_path=None, inline_data=None, column_hints=None)

把 design/08 决策树变成 100% 确定性规则工具：显式关键词表 + 列类型规则 + 表序优先级；
零 LLM、零模糊匹配、零嵌入；只出计划不执行（执行由外层 agent 逐步调用第一层工具）。

## 一、意图关键词表（权威词表，与代码 KW_TABLE 双向一致性检查核对）

| 表序 | intent | reason_code | 关键词（子串包含） | 工具链（按顺序） |
|---|---|---|---|---|
| 1 | overview | R_OVERVIEW | 分布/概况/描述/长什么样 | describe_statistics → data_type_check → missing_report → plot_histogram |
| 2 | correlation | R_CORR | 相关/关系/一起变 | correlation_matrix → plot_heatmap → plot_scatter |
| 3 | cat_association | R_CAT_ASSOC | 关联/类别有没有关系 | chi_square_test |
| 4 | one_group_mean | R_ONE_MEAN | 均值是不是/是否等于/均值等于 | normality_test → hypothesis_test → effect_size |
| 5 | two_groups | R_TWO_GROUPS | 谁高/更高/两组/A 组比 B 组 | normality_test → hypothesis_test → effect_size |
| 6 | multi_groups | R_MULTI_GROUPS | 三组/分部门/多组 | anova_test |
| 7 | pred_continuous | R_PRED_CONT | 预测/影响收入/影响 | linear_regression → feature_importance |
| 8 | pred_binary | R_PRED_BIN | 能不能确定/会不会买/会不会 | logistic_regression |
| 9 | cluster | R_CLUSTER | 分成几类/分群/聚类 | cluster_analysis → pca_analysis |
| 10 | trend_forecast | R_TREND | 下月/趋势/未来 | trend_analysis → seasonal_decompose → time_series_forecast |
| 11 | anomaly | R_ANOMALY | 异常/突变/离群 | outlier_detect / anomaly_detect |
| 12 | power_sample | R_POWER | 需要多少样本/功效/检出 | power_analysis |

匹配规则：子串包含（问题文本含关键词即命中）；多意图命中 → 按 08 表格行序取先者；
全部未命中 → fallback（intent="fallback"，只出数据概览三件套+如实告知无法确定方法）。
种子词忠实转录自 08 表格"判定线索"列+提示词补充（功效行），扩充词不偏离原语义。

## 二、伪键命名空间（params 占位约定）

| 伪键 | 语义 |
|---|---|
| `{"__needs__": "file_path_or_inline"}` | 该步骤需外层 agent 注入数据源（未提供数据时的三件套占位） |
| `{"needs_column": "<列名>"}` | 结构感知已明确语义但对应类型列缺失（如两组比较无类别列） |

伪键只出现在 params 内；外层 agent 解析后替换为真实参数再调用。

## 三、结构感知与列引用

- 提供数据源（file/inline）→ 先做列类型划分：提供 column_hints 时以其为
  **全量划分**（D18 白名单语义：未标注列不参与选列，调用方未声明的角色不猜测）；
  未提供时按 dtype 自动判定（数值=is_numeric_dtype；日期=列名正则 date/时间/日期
  或 datetime64；其余=类别）；
- tool_calls_plan 中 params 引用**真实列名**（数值列首选 numeric[0] 等）；
  类型缺失 → 以 needs_column 占位，不编造列名；
- 功效意图特例：power_analysis 无列引用参数（只有 scenario/effect_size/alpha）；
- column_hints 值域 ∈ {数值,类别,日期}（非法 → E1001）；引用不存在列 → 忽略+summary 注明。

## 四、报告模板与局限（忠实转录）

- report_template 五章（SPEC §6/08）：数据概览 / 方法选择理由 / 结果 / 结论 / 局限；
- limitations 四条：①样本量以工具输出为准（<30 注明功效弱）②p 值是否经多重比较校正
  以工具输出为准 ③相关≠因果 ④未做外部验证；
- fallback 时第二章填法："方法选择理由=问题未能匹配已知方法，仅完成数据概览，
  如实告知暂不支持"。

## 五、错误路径

| 场景 | 码 |
|---|---|
| question 空/仅空白/含控制字符 | E1001 |
| file_path 与 inline_data 双给 | E1001 |
| column_hints 值域非法 | E1001 |
| column_hints 引用不存在列 | 忽略+summary 注明（不报错） |

## 六、验证（tests/test_analysis_plan.py ≥17）

12 意图 golden 用例（问题文案取自本词表关键词；期望 intent/reason_code 由 KW_TABLE
常量程序化导入驱动——词表是输入规约而非被测库输出，不违反铁律 3）+ fallback +
多命中表序裁决 + 结构感知真实列名 + 空白/控制字符 question + column_hints 非法值 +
确定性（同输入两次逐字节）+ JSON allow_nan=False + 双给/双缺数据源组合。
