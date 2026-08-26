"""hypothesis_test —— 统计推断组 · 假设检验（工具 6，核心实现）。

docstring = agent 使用说明书，与 docs/design/03_inference_batch1.md 同步维护。

参数:
    file_path (str): 本地数据文件（csv/tsv/xlsx/json）
    column (str): 分析列（须为数值列）
    test (str, "one_sample"): one_sample / independent / paired
    group_col (str|None): test=independent 时必填，须恰好 2 组且每组 n>=2
    sample2_col (str|None): test=paired 时必填（与 column 成对对齐）
    mu0 (float, 0.0): one_sample 的 H0 假设均值
    alternative (str, "two_sided"): two_sided / less / greater
    alpha (float, 0.05): 显著性水平 ∈ (0,1)

方法（设计文档口径）:
    one_sample -> scipy.stats.ttest_1samp；independent -> ttest_ind(equal_var=False)
    （Welch's t，规格硬性规定，df 用 Welch-Satterthwaite 公式手算，跨版本稳定）；
    paired -> ttest_rel（差值 = column - sample2_col，成正态预检对象）。
    检验前 Shapiro 预检（3<=n<=5000）：违反只警示不阻断，建议非参检验（未实现）。
    CI 一律双侧（1-alpha，t 分布）；效应量 Cohen's d（单样本|mean-mu0|/sd、
    独立 pooled sd、配对差值 sd）。结论文案固定模板 p<alpha 拒绝 H0 / p>=alpha 不能拒绝。

示例:
    hypothesis_test("samples/clean.csv", column="score", test="one_sample", mu0=70.0)
    hypothesis_test("samples/clean.csv", column="score", test="independent", group_col="category")
"""
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sps

from statlab_mcp.tools._common import DataLabError, err, ok, read_table

_TESTS = {"one_sample", "independent", "paired"}
_ALTERNATIVES = {"two_sided", "less", "greater"}
SHAPIRO_MIN_N, SHAPIRO_MAX_N = 3, 5000


def _fmt_p(p: float) -> str:
    return "<0.001" if p < 0.001 else f"{p:.4f}"


def _welch_df(s1: float, s2: float, n1: int, n2: int) -> float:
    """Welch-Satterthwaite 自由度（手算公式，不依赖 scipy 版本属性）。"""
    a, b = s1 ** 2 / n1, s2 ** 2 / n2
    denom = a ** 2 / (n1 - 1) + b ** 2 / (n2 - 1)
    return float((a + b) ** 2 / denom) if denom > 0 else float("nan")


def _shapiro_check(x: np.ndarray) -> dict[str, Any]:
    """Shapiro 预检（官方建议 3~5000，out of range 跳过并注明）。"""
    n = int(x.size)
    if not (SHAPIRO_MIN_N <= n <= SHAPIRO_MAX_N):
        return {"statistic": None, "p_value": None, "normal": None,
                "note": f"n={n} 超出 Shapiro 适用范围 3~{SHAPIRO_MAX_N}，自动跳过"}
    stat, p = sps.shapiro(x)
    return {"statistic": float(stat), "p_value": float(p),
            "normal": bool(p > 0.05), "note": None}


def _t_critical(alpha: float, df: float) -> float:
    return float(sps.t.ppf(1 - alpha / 2, df))


def _conclusion_text(p: float, alpha: float, desc: str) -> str:
    if p < alpha:
        return f"p<α 拒绝 H0（p={_fmt_p(p)} < α={alpha}）：{desc}"
    return f"p≥α 不能拒绝 H0（p={_fmt_p(p)} ≥ α={alpha}）：{desc}"


def hypothesis_test(file_path: str, column: str, test: str = "one_sample",
                    group_col: str | None = None, sample2_col: str | None = None,
                    mu0: float = 0.0, alternative: str = "two_sided",
                    alpha: float = 0.05) -> dict:
    """单样本/独立/配对 t 检验：统计量、p、均值差、CI、效应量 d、固定结论文案。"""
    try:
        if test not in _TESTS:
            raise DataLabError(f"test 仅支持 {'/'.join(sorted(_TESTS))}")
        if alternative not in _ALTERNATIVES:
            raise DataLabError("alternative 仅支持 two_sided/less/greater")
        if not (0 < alpha < 1):
            raise DataLabError("alpha 必须在 (0,1) 之间")
        if isinstance(mu0, bool) or not isinstance(mu0, (int, float, np.integer, np.floating)) \
                or not np.isfinite(mu0):
            raise DataLabError("mu0 必须是有限数值（拒绝 NaN/Inf）")   # Qoder 锐评 #1 防御补全
        df_all = read_table(file_path)
        scipy_alt = "two-sided" if alternative == "two_sided" else alternative  # scipy 枚举用连字符
        if column not in df_all.columns:
            raise DataLabError(f"缺少必需列: {column}；实际列: {list(df_all.columns)}")
        if not pd.api.types.is_numeric_dtype(df_all[column]):
            raise DataLabError(f"列 {column} 不是数值列，无法做假设检验")
        x = df_all[column].dropna().to_numpy(dtype=float)

        # ---- 三路数据准备 ----
        if test == "one_sample":
            if x.size < 2:
                raise DataLabError(f"单样本至少需要 2 个有效值，当前 {x.size}")
            res = sps.ttest_1samp(x, mu0, alternative=scipy_alt)
            stat, p = float(res.statistic), float(res.pvalue)
            df = float(x.size - 1)
            mean = float(x.mean())
            sd = float(x.std(ddof=1))
            mean_diff = mean - mu0
            se = sd / np.sqrt(x.size)
            d = abs(mean_diff) / sd if sd > 0 else 0.0
            out_mean: dict[str, Any] = {"mean": mean, "mean1": None, "mean2": None}
            checks = {"data": _shapiro_check(x)}
        elif test == "independent":
            if group_col is None:
                raise DataLabError("test=independent 时必须提供 group_col")
            if group_col not in df_all.columns:
                raise DataLabError(f"缺少必需列: {group_col}；实际列: {list(df_all.columns)}")
            groups = df_all[group_col].dropna()
            keys = list(dict.fromkeys(groups.values))          # 保持出现顺序
            if len(keys) != 2:
                raise DataLabError(f"分组列应有 2 组，当前 {len(keys)} 组；多组比较请使用 anova_test")
            g1, g2 = keys[0], keys[1]
            m1 = df_all.loc[groups.index[groups == g1], column].dropna().to_numpy(dtype=float)
            m2 = df_all.loc[groups.index[groups == g2], column].dropna().to_numpy(dtype=float)
            if m1.size < 2 or m2.size < 2:
                raise DataLabError(f"组 {g1}(n={m1.size}) / {g2}(n={m2.size}) 样本量不足 2")
            res = sps.ttest_ind(m1, m2, equal_var=False, alternative=scipy_alt)
            stat, p = float(res.statistic), float(res.pvalue)
            mean1, mean2 = float(m1.mean()), float(m2.mean())
            s1, s2 = float(m1.std(ddof=1)), float(m2.std(ddof=1))
            df = _welch_df(s1, s2, int(m1.size), int(m2.size))
            mean_diff = mean1 - mean2
            se = float(np.sqrt(s1 ** 2 / m1.size + s2 ** 2 / m2.size))
            pooled = float(np.sqrt(((m1.size - 1) * s1 ** 2 + (m2.size - 1) * s2 ** 2)
                                   / (m1.size + m2.size - 2)))
            d = abs(mean_diff) / pooled if pooled > 0 else 0.0
            out_mean = {"mean": None, "mean1": mean1, "mean2": mean2}
            checks = {"group1": _shapiro_check(m1), "group2": _shapiro_check(m2)}
        else:  # paired
            if sample2_col is None:
                raise DataLabError("test=paired 时必须提供 sample2_col")
            if sample2_col not in df_all.columns:
                raise DataLabError(f"缺少必需列: {sample2_col}；实际列: {list(df_all.columns)}")
            if not pd.api.types.is_numeric_dtype(df_all[sample2_col]):
                raise DataLabError(f"列 {sample2_col} 不是数值列，无法做假设检验")
            m = df_all[[column, sample2_col]].dropna()
            if len(m) < 2:
                raise DataLabError("配对后有效样本不足 2，无法检验")
            xp = m[column].to_numpy(dtype=float)
            yp = m[sample2_col].to_numpy(dtype=float)
            res = sps.ttest_rel(xp, yp, alternative=scipy_alt)
            stat, p = float(res.statistic), float(res.pvalue)
            df = float(len(m) - 1)
            diffs = xp - yp
            mean_diff = float(diffs.mean())
            sd_diff = float(diffs.std(ddof=1))
            if sd_diff == 0:
                raise DataLabError("配对差值无变异（所有差值相同），无法检验")
            se = sd_diff / np.sqrt(len(m))
            d = abs(mean_diff) / sd_diff
            out_mean = {"mean": None, "mean1": float(xp.mean()), "mean2": float(yp.mean())}
            checks = {"diff": _shapiro_check(diffs)}

        # ---- 双侧 CI（1-alpha）与结论 ----
        t_crit = _t_critical(alpha, df)
        ci_lower, ci_upper = float(mean_diff - t_crit * se), float(mean_diff + t_crit * se)
        violated = any(c.get("normal") is False for c in checks.values())
        normality_warning = ("数据可能非正态，建议 Wilcoxon/Mann-Whitney（非参检验未实现）"
                             if violated else None)

        if test == "one_sample":
            base_desc = (f"总体均值与 {mu0} 的差异"
                         if alternative == "two_sided" else
                         (f"总体均值{'小于' if alternative == 'less' else '大于'} {mu0}"))
            desc = (f"发现{base_desc}显著" if p < alpha else f"未发现{base_desc}显著")
            method = "one_sample_t"
        elif test == "independent":
            base = (f"组 {g1} 与 {g2} 均值差异" if alternative == "two_sided" else
                    f"组 {g1} 均值{'小于' if alternative == 'less' else '大于'}组 {g2}")
            desc = (f"发现{base}显著" if p < alpha else f"未发现{base}显著")
            method = "welch_t"
        else:
            base = ("两次测量均值差异" if alternative == "two_sided" else
                    f"测量1{'小于' if alternative == 'less' else '大于'}测量2")
            desc = (f"发现{base}显著" if p < alpha else f"未发现{base}显著")
            method = "paired_t"

        conclusion = _conclusion_text(p, alpha, desc)
        check_note = next((c["note"] for c in checks.values() if c.get("note")), None)  # L1：结果须进 summary

        result = {
            "test": test, "method": method,
            "n": int(x.size if test != "independent" else m1.size + m2.size),
            "n1": int(m1.size) if test == "independent" else None,
            "n2": int(m2.size) if test == "independent" else None,
            "statistic": stat, "p_value": p, "df": df,
            **out_mean,
            "mean_diff": mean_diff, "ci_lower": ci_lower, "ci_upper": ci_upper,
            "effect_size": d, "effect_size_type": "cohens_d",
            "mu0": mu0 if test == "one_sample" else None,
            "alternative": alternative, "alpha": alpha,
            "normality_shapiro": checks,
            "normality_warning": normality_warning,
            "conclusion": conclusion,
        }

        ci_txt = f"均值差 {mean_diff:.2f}（{int((1 - alpha) * 100)}% CI [{ci_lower:.2f}, {ci_upper:.2f}]）"
        norm_txt = "；非正态警示" if normality_warning else ""
        note_txt = f"；{check_note}" if check_note else ""
        summary = (f"{method}：{ci_txt}，{conclusion}{norm_txt}{note_txt}；"
                   f"效应量 d={d:.2f}（{'小' if d < 0.2 else '中' if d < 0.5 else '大' if d < 0.8 else '很大'}）；"
                   f"相关≠因果")
        return ok(result, summary)
    except DataLabError as e:
        return err(str(e))
    except Exception:
        return err("计算失败，请检查数据内容与参数设置（详见服务端日志）")


def register(mcp) -> None:
    """注册到 MCPServer（mcp 2.x，工具名 = 函数名）。"""
    mcp.add_tool(hypothesis_test, description=__import__("sys").modules[__name__].__doc__)


