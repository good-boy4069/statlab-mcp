"""nonparametric_test —— 统计推断组 · 非参数检验（工具 26，核心实现）。

docstring = agent 使用说明书，与 docs/design/09_inference_batch3.md 同步维护。

参数:
    file_path (str): 本地数据文件（csv/tsv/xlsx/json）
    test (str, "wilcoxon"): wilcoxon（配对）/ mann_whitney（两组独立）/ kruskal_wallis（多组）
    column (str): test=wilcoxon 时必填（配对的第一组测量）
    sample2_col (str): test=wilcoxon 时必填（配对第二组测量）
    group_col (str): test=mann_whitney / kruskal_wallis 时必填（分组列）
    value_col (str): test=mann_whitney / kruskal_wallis 时必填（数值列）
    alpha (float, 0.05): 显著性水平 ∈ (0,1)
    alternative (str, "two_sided"): two_sided / less / greater（仅 wilcoxon 与
        mann_whitney 生效；kruskal_wallis 恒为双侧）

口径（设计文档 09 钉死）:
    wilcoxon: scipy.stats.wilcoxon(zero_method="wilcox", correction=False,
        method="auto")——0 差剔除（zero_method=wilcox 语义）；method="auto"：
        小样本无 ties 用精确分布，否则正态近似；效应量 matched rank-biserial
        r = 2×(正秩和)/n(n+1) − 1，等价式 1 − 4W/(n(n+1))（W=scipy 返回的较小秩和），
        方向以 mean(column − sample2_col) 符号定（column 高为正侧），n=剔除 0 差后的对数。
    mann_whitney: scipy.stats.mannwhitneyu(use_continuity=True, method="auto")
        ——注明 ties 时用正态近似含连续性校正；效应量 rank-biserial
        r = 2U/(n1·n2) − 1（U=scipy 对 group1 的统计量），方向 group1 高为正侧。
    kruskal_wallis: scipy.stats.kruskal——统计量 H（未做 ties 校正，注明）；
        效应量 epsilon² = H/(N−1)（= (ΣᵢRᵢ²/nᵢ − 3(N+1))/(N−1)，N 为总样本量），
        近似解释为"组间秩差异占总秩变异的比例"。
    结论固定模板：p<α 拒绝 H0 / p≥α 不能拒绝；局限声明（非参检验功效通常低于
    参数检验、ties 处理、样本量）。

边界: 样本不足（wilcoxon 有效对数 n<5；mann_whitney 每组 n<2；kruskal 组数
    2~20 且每组 n>=2）、差值无变异/常量组、alpha/alternative 非法、NaN/Inf 防御——
    一律中文报错；无图。

示例:
    nonparametric_test("samples/clean.csv", test="mann_whitney",
                       group_col="category", value_col="score")
"""
import math
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sps

from statlab_mcp.tools._common import EC, DataLabError, err, ok, read_table

_TESTS = {"wilcoxon", "mann_whitney", "kruskal_wallis"}
_ALTERNATIVES = {"two_sided", "less", "greater"}
MIN_PAIRS = 5        # wilcoxon 有效对数下限（小样本精确性）
MIN_N_PER_GROUP = 2  # mann_whitney 每组下限（与 effect_size 一致）
MAX_GROUPS = 20      # kruskal_wallis 组数上限（与 anova_test 一致）


def _fmt_p(p: float) -> str:
    return "<0.001" if p < 0.001 else f"{p:.4f}"


def _wilcoxon(column: str, sample2_col: str, df: pd.DataFrame,
              alternative: str, alpha: float) -> dict[str, Any]:
    m = df[[column, sample2_col]].dropna()
    if len(m) < MIN_PAIRS:
        raise DataLabError(f"配对有效样本不足（n={len(m)}<{MIN_PAIRS}，剔除缺失后），"
                           f"Wilcoxon 检验不可靠", EC.INSUFFICIENT)
    x = m[column].to_numpy(dtype=float)
    y = m[sample2_col].to_numpy(dtype=float)
    diff = x - y
    n_eff = int(np.count_nonzero(diff != 0))
    if n_eff == 0:
        raise DataLabError("配对差值全为 0（无变异），无法做 Wilcoxon 检验", EC.STRUCTURE)
    scipy_alt = "two-sided" if alternative == "two_sided" else alternative  # scipy 枚举用连字符
    res = sps.wilcoxon(x, y, zero_method="wilcox", correction=False,
                       alternative=scipy_alt, method="auto")
    w_stat, p = float(res.statistic), float(res.pvalue)
    # matched rank-biserial r：|r| = 1 − 4W/(n(n+1))，符号由 mean(diff) 方向定
    r_abs = 1.0 - 4.0 * w_stat / (n_eff * (n_eff + 1))
    r = -r_abs if float(np.mean(diff)) < 0 else r_abs
    return {
        "method": "wilcoxon", "n_pairs_used": n_eff, "n_dropped_zero_diff": int(len(m) - n_eff),
        "statistic": w_stat, "statistic_name": "W（较小秩和）",
        "p_value": p, "effsize": r, "effsize_type": "matched rank-biserial r",
        "alternative": alternative,
        "conclusion": (f"p<α 拒绝 H0（p={_fmt_p(p)} < α={alpha}）："
                       f"两次测量存在显著差异" if p < alpha else
                       f"p≥α 不能拒绝 H0（p={_fmt_p(p)} ≥ α={alpha}）："
                       f"未发现两次测量差异"),
    }


def _mann_whitney(group_col: str, value_col: str, df: pd.DataFrame,
                  alternative: str, alpha: float) -> dict[str, Any]:
    keys = list(dict.fromkeys(df[group_col].dropna().values))
    if len(keys) != 2:
        raise DataLabError(f"mann_whitney 需要恰好 2 组，当前 {len(keys)} 组；多组请用 kruskal_wallis", EC.STRUCTURE)
    g1, g2 = keys[0], keys[1]
    x = df.loc[df[group_col] == g1, value_col].dropna().to_numpy(dtype=float)
    y = df.loc[df[group_col] == g2, value_col].dropna().to_numpy(dtype=float)
    if x.size < MIN_N_PER_GROUP or y.size < MIN_N_PER_GROUP:
        raise DataLabError(f"组 {g1}(n={x.size}) / {g2}(n={y.size}) 样本量不足 "
                           f"{MIN_N_PER_GROUP}，无法做 Mann-Whitney 检验", EC.INSUFFICIENT)
    scipy_alt = "two-sided" if alternative == "two_sided" else alternative  # scipy 枚举用连字符
    res = sps.mannwhitneyu(x, y, use_continuity=True, alternative=scipy_alt, method="auto")
    u_stat, p = float(res.statistic), float(res.pvalue)
    r = 2.0 * u_stat / (x.size * y.size) - 1.0     # rank-biserial：group1 高为正
    return {
        "method": "mann_whitney", "n1": int(x.size), "n2": int(y.size),
        "statistic": u_stat, "statistic_name": "U（对 group1）",
        "p_value": p, "effsize": r, "effsize_type": "rank-biserial r",
        "groups": [str(g1), str(g2)], "alternative": alternative,
        "conclusion": (f"p<α 拒绝 H0（p={_fmt_p(p)} < α={alpha}）："
                       f"两组分布存在显著差异" if p < alpha else
                       f"p≥α 不能拒绝 H0（p={_fmt_p(p)} ≥ α={alpha}）："
                       f"未发现两组分布差异"),
    }


def _kruskal_wallis(group_col: str, value_col: str, df: pd.DataFrame,
                    alpha: float) -> dict[str, Any]:
    keys = list(dict.fromkeys(df[group_col].dropna().values))
    if len(keys) < 2:
        raise DataLabError("kruskal_wallis 至少需要 2 组", EC.STRUCTURE)
    if len(keys) > MAX_GROUPS:
        raise DataLabError(f"组数超过 {MAX_GROUPS}，请合并类别", EC.STRUCTURE)
    groups: list[tuple[str, np.ndarray]] = []
    total = 0
    for key in keys:
        vals = df.loc[df[group_col] == key, value_col].dropna().to_numpy(dtype=float)
        if vals.size < MIN_N_PER_GROUP:
            raise DataLabError(f"组 {key} 样本量不足 {MIN_N_PER_GROUP}", EC.INSUFFICIENT)
        groups.append((str(key), vals))
        total += int(vals.size)
    res = sps.kruskal(*[v for _, v in groups])
    h_stat, p = float(res.statistic), float(res.pvalue)
    eps2 = h_stat / (total - 1) if total > 1 else 0.0     # epsilon² = H/(N−1)
    return {
        "method": "kruskal_wallis", "n_groups": len(groups),
        "group_sizes": {k: int(v.size) for k, v in groups},
        "statistic": h_stat, "statistic_name": "H（未做 ties 校正）",
        "p_value": p, "effsize": eps2, "effsize_type": "epsilon² = H/(N−1)",
        "alternative": "two_sided", "n": total,
        "conclusion": (f"p<α 拒绝 H0（p={_fmt_p(p)} < α={alpha}）："
                       f"各组分布存在显著差异（至少一组与其他组不同）" if p < alpha else
                       f"p≥α 不能拒绝 H0（p={_fmt_p(p)} ≥ α={alpha}）："
                       f"未发现各组分布差异"),
    }


def nonparametric_test(file_path: str, test: str = "wilcoxon",
                       column: str | None = None, sample2_col: str | None = None,
                       group_col: str | None = None, value_col: str | None = None,
                       alpha: float = 0.05, alternative: str = "two_sided") -> dict:
    """非参数检验（Wilcoxon 配对 / Mann-Whitney 两组 / Kruskal-Wallis 多组）。"""
    try:
        if test not in _TESTS:
            raise DataLabError(f"test 仅支持 {'/'.join(sorted(_TESTS))}", EC.PARAM)
        if alternative not in _ALTERNATIVES:
            raise DataLabError("alternative 仅支持 two_sided/less/greater", EC.PARAM)
        if isinstance(alpha, bool) or not isinstance(alpha, (int, float, np.integer, np.floating)) \
                or not math.isfinite(float(alpha)) or not (0 < alpha < 1):
            raise DataLabError("alpha 必须在 (0,1) 之间且为有限数", EC.PARAM)
        alpha = float(alpha)

        df = read_table(file_path)
        if test == "wilcoxon":
            for c in (column, sample2_col):
                if c is None or c not in df.columns:
                    raise DataLabError(f"test=wilcoxon 需要 column 与 sample2_col 两列；"
                                       f"缺少列: {c}", EC.PARAM)
            if not pd.api.types.is_numeric_dtype(df[column]) \
                    or not pd.api.types.is_numeric_dtype(df[sample2_col]):
                raise DataLabError("wilcoxon 的两列必须都是数值列", EC.COLUMN_TYPE)
            out = _wilcoxon(column, sample2_col, df, alternative, alpha)
        else:
            for c in (group_col, value_col):
                if c is None or c not in df.columns:
                    raise DataLabError(f"test={test} 需要 group_col 与 value_col 两列；"
                                       f"缺少列: {c}", EC.PARAM)
            if not pd.api.types.is_numeric_dtype(df[value_col]):
                raise DataLabError(f"列 {value_col} 不是数值列，无法做非参数检验", EC.COLUMN_TYPE)
            if df[group_col].notna().sum() == 0:
                raise DataLabError(f"列 {group_col} 无有效数据", EC.INSUFFICIENT)
            out = (_mann_whitney(group_col, value_col, df, alternative, alpha)
                   if test == "mann_whitney"
                   else _kruskal_wallis(group_col, value_col, df, alpha))

        limitation = ("；非参数检验功效通常低于参数检验（数据满足时优先用 t/ANOVA）；"
                      "含 ties 时正态近似并注明")
        summary = (f"{out['conclusion']}；{out['statistic_name']}={out['statistic']:.3f}"
                   f"，p={_fmt_p(out['p_value'])}，效应量 {out['effsize_type']}="
                   f"{out['effsize']:.3f}{limitation}")
        result = {"test": test, "alpha": alpha, **out,
                  "note": "scipy 实现；参数化设置见设计文档 09"}
        return ok(result, summary)
    except DataLabError as e:
        return err(e.code, str(e))
    except Exception:
        return err(EC.CALC, "计算失败，请检查数据内容与参数设置（详见服务端日志）")


def register(mcp) -> None:
    """注册到 MCPServer（mcp 2.x，工具名 = 函数名）。"""
    mcp.add_tool(nonparametric_test, description=__import__("sys").modules[__name__].__doc__)
