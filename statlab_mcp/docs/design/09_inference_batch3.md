# 统计推断组 · 接口设计文档（批 3：非参数检验）
> **工具索引**（v1.1.0 起 statlab://tools/<名>/manual 取本文件对应小节，锚点=一级标题行“# 工具 N：<函数名>(”）：nonparametric_test（工具26）

> 交付物：nonparametric_test（工具 26）完整接口定义。
> 背景：hypothesis_test / normality_test 长期以"建议 Wilcoxon/Mann-Whitney（未实现）"
> 警示用户（第三份锐评点名这是"用户会真实撞上的墙"），v1.0.3 落地工具 26 闭环。

# 工具 26：nonparametric_test(file_path, test, column?, sample2_col?, group_col?, value_col?, alpha, alternative)

一句话用途：数据不满足正态/参数前提时的三把非参钥匙——配对 Wilcoxon、两组 Mann-Whitney、多组 Kruskal-Wallis，全部输出统计量/p 值/效应量。

## 参数表

| 参数名 | 类型 | 默认值 | 校验规则 | 例子 |
|---|---|---|---|---|
| file_path | str | 必填 | 本地 csv/tsv/xlsx/json | `"data/clean.csv"` |
| test | str | "wilcoxon" | ∈ {wilcoxon, mann_whitney, kruskal_wallis}；非法中文报错 | `test="mann_whitney"` |
| column | str\|None | None | test=wilcoxon 必填；须为数值列 | `column="before"` |
| sample2_col | str\|None | None | test=wilcoxon 必填；须为数值列 | `sample2_col="after"` |
| group_col | str\|None | None | test=mann_whitney/kruskal_wallis 必填 | `group_col="category"` |
| value_col | str\|None | None | 同上；须为数值列 | `value_col="score"` |
| alpha | float | 0.05 | ∈(0,1) 且有限（拒绝 NaN/Inf） | `alpha=0.01` |
| alternative | str | "two_sided" | two_sided/less/greater；仅 wilcoxon/mann_whitney 生效（kruskal 恒双侧） | `alternative="greater"` |

## 统计口径（钉死）

1. **Wilcoxon 配对**（scipy.stats.wilcoxon）：
   - `zero_method="wilcox"`（0 差剔除，如实报告 n_pairs_used / n_dropped_zero_diff）；
   - `correction=False`；`method="auto"`——**披露**：小样本无 ties 走精确分布，否则正态近似；
   - 效应量 **matched rank-biserial r**：|r| = 1 − 4W/(n(n+1))（W=scipy 返回的较小秩和，
     n=剔 0 差后的对数），**方向**以 mean(column−sample2_col) 符号定（column 高为正侧）。
2. **Mann-Whitney 两组独立**（scipy.stats.mannwhitneyu）：
   - `use_continuity=True`、`method="auto"`——**披露**：含 ties 或大样本用正态近似+连续性校正；
   - 效应量 **rank-biserial r** = 2U/(n1·n2) − 1（U=scipy 对 group1 的统计量；group1 高为正侧）。
3. **Kruskal-Wallis 多组**（scipy.stats.kruskal）：
   - 统计量 H（**未做 ties 校正，如实披露**）；效应量 **epsilon²** = H/(N−1)
     （恒等：ε² = (ΣᵢRᵢ²/nᵢ − 3(N+1))/(N−1)，N=总样本量；近似解释为组间秩差异占比例）。
4. 结论固定模板：`p<α 拒绝 H0（p=... < α=...）：...` / `p≥α 不能拒绝 H0...`；
   固定局限声明：非参检验功效通常低于参数检验（数据满足前提时优先 t/ANOVA）；
   含 ties 时正态近似并注明。
5. 确定性：无随机过程，两次调用逐字节一致；无图。

## 边界行为表

| 场景 | 行为 |
|---|---|
| wilcoxon 有效对数 n<5（剔除缺失与 0 差后） | error："配对有效样本不足（n=k<5），Wilcoxon 检验不可靠" |
| 配对差值全为 0 | error："配对差值全为 0（无变异），无法做 Wilcoxon 检验" |
| mann_whitney 组数 ≠2 | error："需要恰好 2 组；多组请用 kruskal_wallis" |
| 任意一组 n<2 | error："组 X(n=k) 样本量不足 2，无法做 Mann-Whitney 检验" |
| kruskal 组数 <2 或 >20 | error（>20：与 anova_test 同口径"组数超过 20，请合并类别"） |
| kruskal 任一组 n<2 | error |
| 列不存在 / 非数值列 | error（中文，列名点名） |
| alpha 越界或 NaN/Inf | error："alpha 必须在 (0,1) 之间且为有限数" |
| alternative 非法 | error："alternative 仅支持 two_sided/less/greater" |
| 中文列名 / GBK 文件 | 正常（read_table 通用链路） |

## 返回（成功）示例

```jsonc
{
  "status": "ok",
  "result": {
    "test": "wilcoxon", "alpha": 0.05,
    "method": "wilcoxon", "n_pairs_used": 3, "n_dropped_zero_diff": 2,
    "statistic": 0.0, "statistic_name": "W（较小秩和）",
    "p_value": 0.25, "effsize": -1.0, "effsize_type": "matched rank-biserial r",
    "alternative": "two_sided",
    "conclusion": "p≥α 不能拒绝 H0（p=0.2500 ≥ α=0.05）：未发现两次测量差异",
    "note": "scipy 实现；参数化设置见设计文档 09"
  },
  "summary": "p≥α 不能拒绝 H0（...）；W（较小秩和）=0.000，p=0.2500，效应量 matched rank-biserial r=-1.000；非参数检验功效通常低于参数检验（...）；含 ties 时正态近似并注明"
}
```

## 与工具 6/9 的关系

- hypothesis_test（工具 6）：正态时用；其 `normality_warning` 提示转用本工具。
- normality_test（工具 9）：判定非正态后 → 本工具。
- 设计 08（方案 A 决策树）已更新：非正态分支落点 = 本工具 26。

## 验证命令与预期值来源（可复算）

```powershell
& .\.venv\Scripts\python.exe -c "from statlab_mcp.tools.inference_nonparametric_test import nonparametric_test; import json, pandas as pd, tempfile, os; fd,p=tempfile.mkstemp(suffix='.csv'); os.close(fd); pd.DataFrame({'a':[1,2,3,4,5],'b':[2,4,5,4,5]}).to_csv(p,index=False); print(json.dumps(nonparametric_test(p,test='wilcoxon',column='a',sample2_col='b'), ensure_ascii=False, indent=1)); os.unlink(p)"
```

- 手算样例（pytest 断言基准，Excel 无法直接验证秩检验可手工枚举）：
  - wilcoxon([1..5],[2,4,5,4,5])：diff=[−1,−2,−2,0,0] → 剔 0 差 n=3，|diff| 秩=[1,2.5,2.5]，
    负秩和 6、正秩和 0 → W=0；精确双侧 p=0.25；r=−1（方向 a<b）
  - mannwhitney([1,2,3],[4,5,6,7])：全 x<y → U=0；双侧 p=2×1/C(7,3)=2/35≈0.0571；r=−1
  - kruskal(1..3 / 4..6 / 7..9)：R=[6,15,24]，ΣR²/n=279，H=12/90×279−30=7.2；ε²=7.2/8=0.9
- 准确的 p 值以 pytest 断言为准（scipy 输出与手算分布一致）。
