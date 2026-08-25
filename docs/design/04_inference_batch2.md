# 统计推断组 · 接口设计文档（批 2）

> 交付物：anova_test / chi_square_test / effect_size 三个工具。
> effect_size 为【简化】工具（规格 11）：只做"能出真实数字的最小版本"，已注明略过内容。
> 统计口径总纲沿用批 1（p<0.001 文案、固定结论文案、alpha/confidence 校验、原生类型、确定性）。

---

# 工具 7：anova_test(file_path, group_col, value_col, alpha=0.05)

一句话用途：三组及以上比均值——"组间差异是不是真的"，自动处理方差不齐，自动做事后两两比较。

## 参数表
| 参数名 | 类型 | 默认值 | 校验规则 | 例子 |
|---|---|---|---|---|
| file_path | str | 必填 | 同全局 | `file_path="clean.csv"` |
| group_col | str | 必填 | 存在；类别/数值均可（数值自动按唯一值分组）；须 ≥2 组 | `group_col="category"` |
| value_col | str | 必填 | 存在且数值列 | `value_col="score"` |
| alpha | float | 0.05 | ∈ (0,1) | `alpha=0.01` |

## 统计口径（钉死）
1. **前置检查**：每组 Shapiro（n 在 3~5000 内才做，违反警示不阻断）+ Levene（scipy.stats.levene，稳健中位数版）
2. **方差齐** → 标准 ANOVA：`scipy.stats.f_oneway`；**方差不齐（Levene p<α）** → **Welch ANOVA**：`statsmodels.stats.oneway.anova_oneway(use_var="unequal")`（返回 F、p、df，避免手写 Welch 公式出错）
3. **事后检验**：齐 → `statsmodels.stats.multicomp.pairwise_tukeyhsd`（Tukey HSD，自带族校正与 p 值）；不齐 → **Games-Howell**（statsmodels 无现成，手写：Studentized range 临界值用 `statsmodels.stats.libqsturng.qsturng(1-α, k, df)`，每对 `se=√(sᵢ²/nᵢ+sⱼ²/nⱼ)`、df 用 Welch-Satterthwaite，显著判定 = `\|差值\| > q·se/√2`；**p 值不输出**，以"CI 是否含 0"判定并在输出注明原因）
4. 标注：Tukey/Games-Howell 均为按族校正（family-wise），输出注明"已按族校正"
5. 结论模板：`p<α 拒绝 H0（组间均值存在差异）/ p≥α 不能拒绝 H0（组间均值无显著差异）`

## 返回（成功）
```jsonc
{
  "status": "ok",
  "result": {
    "n_groups": 3, "n": 50,
    "groups": {"A": {"n": 25, "mean": 71.3, "std": 8.9}, ...},   // 每个组样本量/均值/标准差
    "method": "anova" | "welch_anova",
    "statistic": 3.42, "p_value": 0.041, "df_between": 2, "df_within": 47,
    "levene": {"statistic": 1.2, "p_value": 0.31, "equal_variance": true},
    "shapiro_by_group": {"A": {"statistic": 0.98, "p_value": 0.61, "normal": true}, ...},
    "posthoc": {"method": "tukey_hsd" | "games_howell",
                "pairs": [{"pair": "A-B", "diff": 5.5, "ci_lower": 0.7, "ci_upper": 10.3,
                            "p_value": 0.02}],                   // games_howell 时 p_value=null
                "correction": "family-wise（按族校正）"},
    "conclusion": "p<α 拒绝 H0（F=3.42, p=0.041 < α=0.05）：组间均值存在显著差异"
  },
  "summary": "ANOVA：F=3.42, p=0.041<0.05 拒绝 H0；事后 Tukey：A-B 显著（p=0.02），其余对不显著；已按族校正"
}
```

## 边界行为表
| 场景 | 行为 |
|---|---|
| 组数 <2 | error："分组至少需要 2 组" |
| 任一组样本量 <2 | error："组 xxx 样本量不足 2" |
| 仅 2 组 | 正常运行（等价于 t 检验的 F 版；不特殊处理） |
| value_col 非数值 / group_col 全缺失 | error（同批 1 文案） |
| 组数过多（>20） | error："组数超过 20，请合并类别"（防事后矩阵爆炸） |
| Shapiro 违反 | 警示不阻断（同 hypothesis_test 语义） |
| 单行组 | 落入"样本量不足 2" |

## 错误路径（≥3 种）
1. `分组至少需要 2 组`
2. `组 xxx 样本量不足 2`
3. `组数超过 20，请合并类别`
4. `缺少必需列: value_col`

## 验证命令与预期值来源
```powershell
& .\.venv\Scripts\python.exe -c "from statlab_mcp.tools.inference_anova_test import anova_test; import json; print(json.dumps(anova_test('samples/clean.csv', group_col='category', value_col='score'), ensure_ascii=False, indent=1))"
```
- clean.csv 三组 A/B/C（25/15/10）：seed 固定，F/p 以 statsmodels/scipy 输出为准（Excel 的 ANOVA 单因素功能可人工复算——两个库公式同为标准 F 检验）
- 手算校验例：三组 [1,2,3],[2,3,4],[5,6,7] → 组间差异明显，F 大 p 小

---

# 工具 8：chi_square_test(file_path, col_a, col_b)

一句话用途：两列"类别有没有关联"（如性别×购买与否）——列联表 + 卡方检验 + Cramér's V 效应量。

## 参数表
| 参数名 | 类型 | 默认值 | 校验规则 | 例子 |
|---|---|---|---|---|
| file_path | str | 必填 | 同全局 | 例子 |
| col_a / col_b | str | 必填 | 均须存在 | `col_a="category"` |

## 统计口径（钉死）
1. 两列按类别处理：**数值列自动等宽分箱 ≤8 箱**（pd.cut，箱数 = min(8, 唯一值数)）并在 summary 注明"数值列 xxx 已分箱"
2. 列联表：`pd.crosstab`；期望频数表用 `scipy.stats.chi2_contingency` 的 expected 输出
3. **Fisher 切换规则**：>20% 单元格期望频数 <5 → 若为 2×2 → `scipy.stats.fisher_exact`（输出 OR、双侧 p）；非 2×2 → error："期望频数过低的单元格超过 20%，且非 2×2 表无法用 Fisher 精确检验，请合并类别后重试"
4. 效应量：Cramér's V = √(χ²/(n·(min(rows,cols)−1)))（V 范围 0~1：0.1 小 / 0.3 中 / 0.5 大）
5. 无"显著=重要/因果"表述；summary 注明"关联≠因果"

## 返回（成功）
```jsonc
{
  "status": "ok",
  "result": {
    "test_used": "chi_square" | "fisher_exact",
    "n": 50,
    "contingency_table": {"A": {"X": 10, "Y": 15}, "B": {"X": 12, "Y": 13}},
    "statistic": 0.32, "df": 1, "p_value": 0.57,          // fisher 时 df=null、statistic 为 OR
    "cramers_v": 0.08,
    "expected_low_cell_ratio": 0.0,                       // 期望 <5 的单元格占比
    "binning_note": null,                                  // 数值列分箱时非 null
    "conclusion": "p≥α 不能拒绝 H0（p=0.57 ≥ α=0.05）：未发现两列关联"
  },
  "summary": "卡方检验：χ²=0.32, df=1, p=0.57 不能拒绝 H0；Cramér's V=0.08（弱）；关联≠因果"
}
```

## 边界行为表
| 场景 | 行为 |
|---|---|
| 任一列全缺失 | error："列 xxx 无有效数据" |
| 类别唯一值 =1 | error："列 xxx 只有 1 个类别，无法做关联检验" |
| 任一类别数 >50 | error："列 xxx 类别超过 50 个，请先合并类别"（防列联表爆炸） |
| 数值列 | 自动等宽分箱 ≤8 箱并注明 |
| 期望频数低且 2×2 | fisher_exact，statistic=OR（注明） |
| 期望频数低且非 2×2 | error（见口径 3） |
| 中文列名 | 键原样输出 |

## 错误路径（≥3 种）
1. `列 xxx 只有 1 个类别，无法做关联检验`
2. `期望频数过低的单元格超过 20%，且非 2×2 表无法用 Fisher 精确检验，请合并类别后重试`
3. `列 xxx 类别超过 50 个，请先合并类别`

## 验证命令与预期值来源
```powershell
& .\.venv\Scripts\python.exe -c "from statlab_mcp.tools.inference_chi_square_test import chi_square_test; import json; print(json.dumps(chi_square_test('samples/clean.csv', col_a='category', col_b='category'), ensure_ascii=False, indent=1))"
```
- 手算校验例（Excel 可复算）：[[10,15],[12,13]] → χ²=0.32（=CHISQ.TEST 或手算 Σ(O-E)²/E）、df=1、Cramér's V=√(0.32/(50·1))=0.08

---

# 工具 11：effect_size(file_path, group_col, value_col, method="cohens_d", paired=False)【简化】

一句话用途：两组差异的"实际大小"——不依赖样本量（p 值受 n 影响，效应量不受）。

## 参数表
| 参数名 | 类型 | 默认值 | 校验规则 | 例子 |
|---|---|---|---|---|
| file_path | str | 必填 | 同全局 | 例子 |
| group_col | str | 必填 | 须恰好 2 组 | `group_col="category"` |
| value_col | str | 必填 | 存在且数值列 | `value_col="score"` |
| method | str | "cohens_d" | ∈ {cohens_d, hedges_g, cliff_delta} | `method="hedges_g"` |
| paired | bool | False | True 时两组样本数必须相等且按行序配对（简化实现，见下） | `paired=True` |

## 统计口径（钉死）
- cohens_d：|m1−m2| / pooled_sd（pooled_sd=√(((n1−1)s1²+(n2−1)s2²)/(n1+n2−2))，同 hypothesis_test 口径）
- hedges_g：d × (1 − 3/(4(n1+n2)−9))（小样本修正）
- cliff_delta：P(x1>x2) − P(x1<x2)（比较所有跨组值对，用 Mann-Whitney U 转换：δ = 2U/(n1·n2) − 1）
- **95% CI**：d/g 用正态近似 `se = √(1/n1 + 1/n2 + d²/(2(n1+n2)))`；cliff_delta 用 `se = √(δ(1−δ)… )` 采用保守近似 `√((1−δ²)/(n1·n2))`——CIs 注明"近似"
- **paired=True 简化语义**（规格"两次测量配对列"）：group_col 恰好 2 组，且两组样本数相等，按行序第 i 个 A 行与第 i 个 B 行配对；d 用配对差值：d = |mean(diff)|/sd(diff)
- 阈值解释输出固定：d/g：0.2 小 / 0.5 中 / 0.8 大（Cohen 建议）；cliff_delta：0.147 小 / 0.33 中 / 0.474 大（Romano 建议）——注"阈值为经验惯例，非统计硬标准"
- 【简化】略过声明：不做 bootstrap CI、不做分布假设检验、cliff_delta 无配对版本（paired=True 时仅支持 d/g，cliff_delta 报错）

## 返回（成功）
```jsonc
{
  "status": "ok",
  "result": {
    "method": "cohens_d", "paired": false, "n1": 25, "n2": 15,
    "mean1": 71.3, "mean2": 65.8,
    "effect_size": 0.65, "ci_lower": 0.08, "ci_upper": 1.22,
    "ci_note": "正态近似",
    "interpretation": {"label": "中等", "thresholds": "小<0.2，中<0.5，大<0.8（Cohen）"}
  },
  "summary": "Cohen's d=0.65（95% CI [0.08, 1.22]，正态近似），中等效应；CI 不含 0"
}
```

## 边界行为表
| 场景 | 行为 |
|---|---|
| 组数 ≠2 | error："effect_size 只支持恰好 2 组比较" |
| 任一组 n<2 | error："组 xxx 样本量不足 2" |
| paired=True 两组样本数不等 | error："paired=True 要求两组样本数相等（按行序配对）" |
| paired=True 且 method=cliff_delta | error："cliff_delta 暂不支持配对模式（简化实现）" |
| 常数列之一 | d=0（分母 pooled>0 时）或 error"组内无变异"；边界：任一组 sd=0 且另一组 sd>0 → 照常计算（混合可算）；全常量 → error |
| 中文列名 | 键原样输出 |

## 错误路径（≥3 种）
1. `effect_size 只支持恰好 2 组比较`
2. `paired=True 要求两组样本数相等（按行序配对）`
3. `cliff_delta 暂不支持配对模式（简化实现）`
4. `method 仅支持 cohens_d/hedges_g/cliff_delta`

## 验证命令与预期值来源
```powershell
& .\.venv\Scripts\python.exe -c "from statlab_mcp.tools.inference_effect_size import effect_size; import json; print(json.dumps(effect_size('samples/clean.csv', group_col='category', value_col='score', method='cohens_d'), ensure_ascii=False, indent=1))"
```
- 手算校验例：x=[1,2,3,4,5], y=[2,4,6,8,10] → pooled_sd=2.5、d=|3−6|/2.5=**1.2**（Excel 手算可复核）
- hedges_g 修正因子：g=1.2×(1−3/(4·10−9))=1.2×(1−3/31)=1.2×0.9032=1.0839

---

# 附录：批 2 自查（附录 C 组内 3 问）
- ⑦ 参数风格一致：group_col/value_col 命名与 hypothesis_test 对齐；alpha 同款校验
- ⑧ 无重叠：anova 与 hypothesis_test 的 independent 分支互补（规格明确"多组请用 anova_test"）；chi_square 处理类别对（连续工具不涉及）；effect_size 独立于假设检验（无 p 值、只报大小）
- ⑨ 使用条件写明：ANOVA 方差齐性前提 + Levene 自动检查 + Welch 兜底；卡方期望频数 ≥5 规则 + Fisher 切换；Games-Howell p 值省略的诚实说明；效应量阈值标注"经验惯例"

## 大白话三问（附录 C 必答）
1. **能在 Excel 里验证吗？** 部分能。卡方：2×2 表用 CHISQ.TEST 或手算 Σ(O−E)²/E 完全可复算；Cramér's V 手算√(χ²/(n·(min(r,c)−1)))。ANOVA：Excel 数据分析工具的单因素方差分析可对照 F/p；Tukey 事后需用其他统计软件复核。Games-Howell 与效应量 CI 标注"近似/省略 p"，Excel 复现不了的部分以 pytest 断言为准。
2. **真实数据接得住吗？** 接得住。三组以上自动走 ANOVA 而不是 t 检验；类别列直接用、数值列自动分箱（≤8 箱并注明）；方差不齐自动换 Welch；卡方条件不满足自动换 Fisher 或明确告诉你"合并类别"。
3. **同一文件跑两次一样吗？** 一样。全部确定性计算（无随机过程，CI 近似公式也是固定公式）。