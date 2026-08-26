# 统计推断组 · 接口设计文档（批 1）

> 交付物：hypothesis_test / normality_test / confidence_interval 三个工具的完整接口定义。
> 批 2（anova_test / chi_square_test / effect_size）另行交付。
> 统计概念讲解在实现每个工具前给出（从零开始，分批确认）。
> 全局约定同探查组：error 无 result；数值全原生类型；NaN→null；summary 代码模板生成；确定性可复现。

## 本组统计口径总纲（三工具共用，先钉死再实现）
- 显著性门槛：只输出数字与结论文案，**禁止"显著=重要/因果"表述**；p<0.001 在 summary 显示 "<0.001"（result 存真实 float）
- 结论文案固定模板：`p<α 拒绝 H0（p=x < α=y）/ p≥α 不能拒绝 H0（p=x ≥ α=y）`，H0 以文字写明（如"总体均值等于 4"）
- 所有 CI 用 t 分布（mean_t 法）；效应量 Cohen's d 无偏修正（denominator 用 pooled sd, ddof=2 口径在实现三句话里钉死）
- alpha/confidence 参数校验：alpha ∈ (0,1) 浮点；confidence ∈ (0,1)，越界中文报错
- 缺失处理：列内 dropna（有效值不被缺失拖累）；paired 按成对同时非 NaN 对齐
- 大样本：n>5000 时 normality 自动跳过并注明（Shapiro 官方建议 3~5000，红队 S1）

---

# 工具 6：hypothesis_test(file_path, column, test="one_sample", group_col=None, sample2_col=None, mu0=0.0, alternative="two_sided", alpha=0.05)

一句话用途：回答"这列数据的均值跟一个数比（one_sample）、两组比（independent）、还是两次测量比（paired），差异是不是真的显著"——输出统计量、p 值、均值差、置信区间、效应量 d 和固定结论文案。

## 参数表
| 参数名 | 类型 | 默认值 | 校验规则 | 例子 |
|---|---|---|---|---|
| file_path | str | 必填 | 本地 csv/tsv/xlsx/json；拒绝 UNC | `file_path="clean.csv"` |
| column | str | 必填 | 必须存在于文件且为数值列，否则中文报错 | `column="score"` |
| test | str | "one_sample" | ∈ {one_sample, independent, paired} | `test="independent"` |
| group_col | str\|None | None | test="independent" 时必填且须存在；组数必须 =2（≠2 报"请使用 anova_test"）；组内样本量均 ≥2 | `group_col="category"` |
| sample2_col | str\|None | None | test="paired" 时必填且须存在、数值列；与 column 成对对齐 | `sample2_col="score2"` |
| mu0 | float | 0.0 | 仅 one_sample 使用；任意浮点 | `mu0=70.0` |
| alternative | str | "two_sided" | ∈ {two_sided, less, greater}；非法值中文报错 | `alternative="greater"` |
| alpha | float | 0.05 | ∈ (0,1)；非法值中文报错 | `alpha=0.01` |

## 方法选择（确定性代码，无 LLM）
| test | 方法 | 统计量 | 效应量 d |
|---|---|---|---|
| one_sample | 单样本 t（scipy.stats.ttest_1samp） | t | d=\|mean−mu0\|/sd |
| independent | **Welch's t**（scipy.stats.ttest_ind, equal_var=False，规格硬性规定） | t | 合并 d 修正（pooled sd） |
| paired | 配对 t（scipy.stats.ttest_rel，差值 = column − sample2_col） | t | d=mean(差)/sd(差) |
所有方法前：Shapiro 正态预检（n≤5000 且 n≥3），p<0.05 在 result 记 `normality_warning` 并提示"建议转用 nonparametric_test（Wilcoxon/Mann-Whitney，工具 26）"——**不阻断计算**，只警示。

## 返回（成功）
```jsonc
{
  "status": "ok",
  "result": {
    "test": "independent", "method": "welch_t",
    "n": 50, "n1": 25, "n2": 25,            // n=有效样本总量（paired 为配对数）
    "statistic": -2.31, "p_value": 0.0241, "df": 47.9,
    "mean": null, "mean1": 71.3, "mean2": 65.8,      // one_sample 只有 mean；独立/配对用 mean1/mean2
    "mean_diff": 5.5,                       // one_sample: mean−mu0；independent: mean1−mean2；paired: mean(差)
    "ci_lower": 0.74, "ci_upper": 10.26,    // 均值差/均值 的 1−alpha 置信区间（t 分布）
    "effect_size": 0.65, "effect_size_type": "cohens_d",
    "mu0": null, "alternative": "two_sided", "alpha": 0.05,
    "normality_shapiro": {"statistic": 0.98, "p_value": 0.61, "normal": true},
    "normality_warning": null,              // 违反时: "数据可能非正态，建议转用 nonparametric_test（Wilcoxon/Mann-Whitney）"
    "conclusion": "p<α 拒绝 H0（p=0.0241 < α=0.05）：两组均值差异显著"
  },
  "summary": "Welch t 检验：均值差 5.5（95% CI [0.74, 10.26]），p=0.0241 <0.05 拒绝 H0；效应量 d=0.65 中等；相关≠因果"
}
```
| 键 | 类型 | 说明 |
|---|---|---|
| statistic / p_value / df | float | 真实 scipy 输出（df 可达小数，Welch 特性） |
| mean / mean1 / mean2 | float\|null | 按 test 类型取舍；one_sample 的 mean=列均值 |
| mean_diff | float | 上述口径；paired 为差值均值 |
| ci_lower / ci_upper | float | 与 mean_diff 同口径的 1−alpha 区间 |
| effect_size | float | Cohen's d（方向：independent 为 mean1−mean2 的绝对值） |
| conclusion | str | 固定模板文案（数字拼入，p<0.001 显示 "<0.001"） |
| normality_* | 见上 | Shapiro 预检结果；n>5000 时 statistic/p_value=null、normal=null、注明"n>5000 自动跳过" |

## 边界行为表（12 项）
| 场景 | 行为 |
|---|---|
| column 不存在 | error："缺少必需列: xxx；实际列: [...]" |
| column 非数值列 | error："列 xxx 不是数值列，无法做假设检验" |
| column 全缺失 | error："列 xxx 无有效数据" |
| 单样本 n=1 | error："单样本至少需要 2 个有效值" |
| independent 无 group_col | error："test=independent 时必须提供 group_col" |
| group_col 组数 ≠2 | error："分组列应有 2 组，当前 N 组；多组比较请使用 anova_test" |
| 某组样本量 <2 | error："组 xxx 样本量不足 2" |
| paired 无 sample2_col | error："test=paired 时必须提供 sample2_col" |
| paired 有一列全缺失 | error："列 xxx 无有效数据"（配对后无有效对时） |
| paired 两列各自缺失不同行 | 按同时非 NaN 成对对齐（n=配对数，mean_diff 用配对差） |
| alternative / alpha 非法 | error："alternative 仅支持 two_sided/less/greater" / "alpha 必须在 (0,1) 之间" |
| 中文列名 / 极端值 | 键原样输出；1e9 会如实参与计算（不剔除） |

## 错误路径（≥3 种）
1. `缺少必需列: xxx`
2. `test=independent 时必须提供 group_col`
3. `分组列应有 2 组，当前 3 组；多组比较请使用 anova_test`
4. `alpha 必须在 (0,1) 之间`

## 验证命令与预期值来源（可复算）
```powershell
& .\.venv\Scripts\python.exe -c "from statlab_mcp.tools.inference_hypothesis_test import hypothesis_test; import json; print(json.dumps(hypothesis_test('samples/clean.csv', column='score', test='one_sample', mu0=70.0), ensure_ascii=False, indent=1))"
```
- **Excel 可复算（one_sample）**：数据 [1,2,3,4,5]，mu0=4 → mean=3、sd=1.581（STDEV.S）、t=(3−4)/(1.581/√5)=−1.414、df=4、p=2×T.DIST.2T(|t|,4)≈0.230；CI mean±T.INV.2T(0.05,4)×sd/√5
- clean.csv 的 score 列 mean≈70.78（describe 已实测），mu0=70 时 t 很小、p 大（不能拒绝）

---

# 工具 9：normality_test(file_path, column, method="auto")

一句话用途：回答"这列数据像不像正态分布"——为后续选 t 检验还是非参检验提供依据。

## 参数表
| 参数名 | 类型 | 默认值 | 校验规则 | 例子 |
|---|---|---|---|---|
| file_path | str | 必填 | 同全局 | `file_path="clean.csv"` |
| column | str | 必填 | 存在且数值列 | `column="score"` |
| method | str | "auto" | ∈ {auto, shapiro, dagostino}；auto 按 n 自动选（见下） | `method="shapiro"` |

## 方法选择（确定性）
| 条件 | 方法 | 依据 |
|---|---|---|
| n ≤ 5000 | Shapiro–Wilk（scipy.stats.shapiro，官方建议样本 3~5000，红队 S1） | 功效最好的小样本检验 |
| 5000 < n ≤ 100000 | D'Agostino–Pearson（scipy.stats.normaltest） | 大样本下 shapiro 不可用 |
| n > 100000 | 不计算 → error："样本过大（N 行），请随机抽样后重试" | 防内存/时间爆炸 |
| n < 3 | error："至少需要 3 个有效值" | 检验前提 |

## 返回（成功）
```jsonc
{
  "status": "ok",
  "result": {
    "method_used": "shapiro", "n": 50,
    "statistic": 0.9812, "p_value": 0.61,
    "skew": -0.11, "kurtosis": -0.72,       // Fisher 口径（同 describe，spec 3 要求）
    "normal": true,                          // 判定: p_value > 0.05 视为"不拒绝正态"；固定 0.05 并在输出注明
    "threshold_alpha": 0.05
  },
  "summary": "Shapiro-Wilk 检验：p=0.6100 ≥0.05，不能拒绝正态假设（数据近似正态）；偏度 -0.11、峰度 -0.72"
}
```
判定文案模板：`p<α 拒绝正态假设（p=x < α=0.05）/ p≥α 不能拒绝正态假设（近似正态）`。

## 边界行为表
| 场景 | 行为 |
|---|---|
| 列不存在 / 非数值 / 全缺失 | error（同 hypothesis_test 文案） |
| n<3 | error："至少需要 3 个有效值" |
| n>100000 | error："样本过大（N 行），请随机抽样后重试" |
| 常量列（std=0） | 统计量可算但无意义 → 直接 error："常数列方差为 0，正态检验无意义" |
| 极端值 | 如实参与（正态检验对极值敏感，这正是它要发现的） |
| 中文列名 | 键原样输出 |

## 验证命令与预期值来源
```powershell
& .\.venv\Scripts\python.exe -c "from statlab_mcp.tools.inference_normality_test import normality_test; import json; print(json.dumps(normality_test('samples/clean.csv', column='score'), ensure_ascii=False, indent=1))"
```
- 注意：clean.csv 的 score 是正态抽样，p 值应 >0.05（近似正态）；Excel 无法直接复算 Shapiro（无内置函数），**pytest 以 scipy 官方行为为基准 + 手算偏度/峰度公式复核**；独立对照偏度 = Σ((x−x̄)/s)³·n/((n−1)(n−2))（Excel SKEW 同式，可复算）

---

# 工具 10：confidence_interval(file_path, column, confidence=0.95, method="mean_t")

一句话用途：给"均值（或中位数）大概落在哪个范围"一个区间答案——比单点估计诚实。

## 参数表
| 参数名 | 类型 | 默认值 | 校验规则 | 例子 |
|---|---|---|---|---|
| file_path | str | 必填 | 同全局 | 例子 |
| column | str | 必填 | 存在且数值列 | `column="income"` |
| confidence | float | 0.95 | ∈ (0,1)；越界或其他类型中文报错 | `confidence=0.90` |
| method | str | "mean_t" | ∈ {mean_t, bootstrap_median} | `method="bootstrap_median"` |

## 方法口径
- mean_t（默认）：`mean ± t_{1−α/2, n−1} × sd/√n`（sd 用 ddof=1，与 describe 同口径；scipy.stats.t.ppf）
- bootstrap_median：**numpy 局部 default_rng(42)** 重采样 1000 次取中位数，CI = 2.5%/97.5% 分位数（percentile 法）；**每次调用独立可复现**（局部 seed，不依赖全局 rng 状态，spec 4 可复现性增强）
- 两种方法 n<3 均报错："至少需要 3 个有效值"

## 返回（成功）
```jsonc
{
  "status": "ok",
  "result": {
    "method": "mean_t", "confidence": 0.95, "n": 50,
    "point_estimate": 8005.3, "estimate_type": "mean",     // bootstrap_median 时为 median
    "ci_lower": 7451.2, "ci_upper": 8559.4,
    "std_error": 281.1, "margin": 553.9,                   // mean_t 才有
    "n_bootstrap": null, "seed": null                      // bootstrap_median 时: 1000 / 42
  },
  "summary": "均值 8005.30 的 95% 置信区间为 [7451.20, 8559.40]（t 分布，n=50）"
}
```

## 边界行为表
| 场景 | 行为 |
|---|---|
| 列不存在 / 非数值 / 全缺失 | error（同前文案） |
| n<3 | error："至少需要 3 个有效值" |
| confidence ≤0 或 ≥1 | error："confidence 必须在 (0,1) 之间" |
| method 非法 | error："method 仅支持 mean_t/bootstrap_median" |
| 常数列 | CI 退化为点（sd=0 → 区间=均值本身），照常输出并 summary 注明"常数列" |
| 极端值 | 如实参与（bootstrap 中位数对其稳健，这正是 median 法的意义） |

## 验证命令与预期值来源（可复算）
```powershell
& .\.venv\Scripts\python.exe -c "from statlab_mcp.tools.inference_confidence_interval import confidence_interval; import json; print(json.dumps(confidence_interval('samples/clean.csv', column='income'), ensure_ascii=False, indent=1))"
```
- **Excel 可复算（mean_t）**：[1,2,3,4,5] 95% CI → mean=3、sd=1.581、t=2.776（=T.INV.2T(0.05,4)）→ CI=[3−2.776×1.581/√5, 3+...]=[1.037, 4.963]
- bootstrap_median：Excel 无法精确复现（随机重采样），**pytest 断言仅做可复现性 + 区间包含样本中位数**；期望值来源注明"同进程内同输入必得同结果（局部 seed=42）"

---

# 附录：批 1 自查（附录 C 组内 3 问）
- ⑦ 参数风格一致：均 file_path→column 开头；枚举参数（test/method/alternative）均有默认值+非法值中文报错；alpha/confidence 同款 (0,1) 校验
- ⑧ 与已确认组无重叠：描述统计 output 数字、本组做推断（检验/区间）；effect_size 工具（批 2）与本组 hypothesis 输出的 d 不重复（批 2 是独立组比较工具）
- ⑨ 使用条件写明：t 检验近似正态前提（自动 Shapiro 预检+警示）、Welch 不等方差稳健、bootstrap 适用于分布未知/偏态（中位数），Shapiro 官方 3~5000 限制——全部落入输出与边界表

## 大白话三问（附录 C 必答）
1. **能在 Excel 里验证吗？** 能（除 bootstrap）。单样本 t 手算例子和 95% CI 例子都给了可复算公式；Excel 的 T.DIST.2T / T.INV.2T / STDEV.S 直接对应。bootstrap 中位数法靠固定种子可复现，但 Excel 复现不了随机重采样。
2. **真实数据接得住吗？** 接得住。中文列名原样；缺失自动按有效值/成对处理；两组比时分组列多组会明确提示"用 anova_test"；极端值如实参与不偷偷删。
3. **同一文件跑两次一样吗？** 一样。t 检验/CI 无随机；bootstrap 用局部固定 seed=42，每次调用独立复现——比"全局 seed"更严格。