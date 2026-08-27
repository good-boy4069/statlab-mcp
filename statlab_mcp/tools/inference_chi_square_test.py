"""chi_square_test —— 统计推断组 · 卡方独立性检验（工具 8，核心实现）。

docstring = agent 使用说明书，与 statlab_mcp/docs/design/04_inference_batch2.md 同步维护。

参数:
    file_path (str): 本地数据文件（csv/tsv/xlsx/json）
    col_a / col_b (str): 两列类别变量（均须存在；数值列自动等宽分箱 ≤8 箱并注明）

流程（确定性）:
    1. 分类化：数值列 pd.cut 等宽分箱（箱数=min(8, max(2, 唯一值数))）并注明；
       类别唯一值 =1 -> error；>50 -> error（防列联表爆炸）
    2. pd.crosstab 列联表；scipy.stats.chi2_contingency（含期望频数表）
    3. >20% 单元格期望频数 <5：2x2 -> scipy.stats.fisher_exact（statistic=OR、df=null）；
       非 2x2 -> 中文报错引导合并类别
    4. 效应量 Cramér's V = sqrt(chi2/(n*(min(rows,cols)-1)))（chi2 来自 chi2_contingency，
       fisher 路径同样给出并注明基于卡方近似）
    5. 结论固定模板；summary 注明"关联≠因果"

示例:
    chi_square_test("samples/clean.csv", col_a="category", col_b="category")
"""
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sps

from statlab_mcp.tools._common import EC, DataLabError, err, ok, read_table

MAX_CATEGORIES = 50
MAX_BINS = 8
LOW_EXPECTED_RATIO = 0.2


def _fmt_p(p: float) -> str:
    return "<0.001" if p < 0.001 else f"{p:.4f}"


def _to_categories(s: pd.Series, name: str) -> Any:
    """列 -> 类别 Series；数值列自动等宽分箱；返回 (类别, binning_note)。"""
    if pd.api.types.is_numeric_dtype(s):
        n_uniq = int(s.nunique())
        # 常量数值列等宽箱边界全等，pd.cut 会抛 ValueError；须先友好报错（外部评审 M8）
        if n_uniq <= 1:
            raise DataLabError(
                f"数值列 {name} 只有 {n_uniq} 个不同值，无法做关联检验"
                + ("（无有效数据）" if n_uniq == 0 else "（常量列无类别区分）"), EC.INSUFFICIENT)
        n_bins = min(MAX_BINS, max(2, n_uniq))
        cats = pd.cut(s, bins=n_bins, include_lowest=True).astype(str)
        return cats, f"数值列 {name} 已自动等宽分箱为 {n_bins} 箱"
    return s.astype(str), None


def chi_square_test(file_path: str, col_a: str, col_b: str) -> dict:
    """两列类别关联检验（卡方 / Fisher 精确 + Cramér's V）。"""
    try:
        df = read_table(file_path)
        for c in (col_a, col_b):
            if c not in df.columns:
                raise DataLabError(f"缺少必需列: {c}；实际列: {list(df.columns)}", EC.COLUMN_MISSING)
        sa, note_a = _to_categories(df[col_a].dropna(), col_a)
        sb, note_b = _to_categories(df[col_b].dropna(), col_b)
        if sa.size == 0:
            raise DataLabError(f"列 {col_a} 无有效数据", EC.INSUFFICIENT)
        if sb.size == 0:
            raise DataLabError(f"列 {col_b} 无有效数据", EC.INSUFFICIENT)
        if sa.nunique() < 2:
            raise DataLabError(f"列 {col_a} 只有 1 个类别，无法做关联检验", EC.STRUCTURE)
        if sb.nunique() < 2:
            raise DataLabError(f"列 {col_b} 只有 1 个类别，无法做关联检验", EC.STRUCTURE)
        if sa.nunique() > MAX_CATEGORIES:
            raise DataLabError(f"列 {col_a} 类别超过 {MAX_CATEGORIES} 个，请先合并类别", EC.STRUCTURE)
        if sb.nunique() > MAX_CATEGORIES:
            raise DataLabError(f"列 {col_b} 类别超过 {MAX_CATEGORIES} 个，请先合并类别", EC.STRUCTURE)

        # 两列对齐（同时非 NaN 的行）
        m = df[[col_a, col_b]].dropna()
        ct = pd.crosstab(
            _to_categories(m[col_a], col_a)[0], _to_categories(m[col_b], col_b)[0])
        obs = ct.to_numpy(dtype=float)
        n = int(obs.sum())

        chi2_stat, chi2_p, chi2_df, expected = sps.chi2_contingency(obs, correction=False)
        # 注明：correction=False（与 Excel CHISQ.TEST 及教科书 Σ(O-E)^2/E 一致，不做 Yates 校正）
        low_ratio = float(np.mean(expected < 5))
        binning_note = "；".join(x for x in (note_a, note_b) if x) or None

        if low_ratio > LOW_EXPECTED_RATIO:
            if obs.shape != (2, 2):
                raise DataLabError(
                    "期望频数过低的单元格超过 20%，且非 2×2 表无法用 Fisher 精确检验，"
                    "请合并类别后重试", EC.PARAM)
            or_val, p_val = sps.fisher_exact(obs, alternative="two-sided")
            test_used = "fisher_exact"
            statistic = float(or_val)
            df_val: int | None = None
            p_value = float(p_val)
        else:
            test_used = "chi_square"
            statistic = float(chi2_stat)
            df_val = int(chi2_df)
            p_value = float(chi2_p)

        cramers_v = float(np.sqrt(chi2_stat / max(n * (min(ct.shape) - 1), 1e-12)))

        if p_value < 0.05:
            conclusion = (f"p<α 拒绝 H0（p={_fmt_p(p_value)} < α=0.05）："
                          f"两列存在关联（非独立性）")
        else:
            conclusion = (f"p≥α 不能拒绝 H0（p={_fmt_p(p_value)} ≥ α=0.05）："
                          f"未发现两列关联")

        method_txt = "Fisher 精确检验" if test_used == "fisher_exact" else "卡方检验"
        stat_txt = (f"OR={statistic:.2f}" if test_used == "fisher_exact"
                    else f"χ²={statistic:.2f}, df={df_val}")
        v_txt = (f"Cramér's V={cramers_v:.2f}"
                 f"（{'小' if cramers_v < 0.1 else '中' if cramers_v < 0.3 else '大'}）")
        summary = (f"{method_txt}：{stat_txt}, p={_fmt_p(p_value)}，"
                   f"{'拒绝 H0（两列关联）' if p_value < 0.05 else '不能拒绝 H0'}；"
                   f"{v_txt}; 关联≠因果")
        if binning_note:
            summary += f"；{binning_note}"
        if test_used == "fisher_exact":
            summary += "；期望频数过低已自动改用 Fisher 精确检验"

        result = {
            "test_used": test_used,
            "n": n,
            "contingency_table": {str(i): {str(j): float(ct.iat[i, j])
                                           for j in range(ct.shape[1])}
                                  for i in range(ct.shape[0])},
            "statistic": statistic, "df": df_val, "p_value": p_value,
            "cramers_v": cramers_v,
            "expected_low_cell_ratio": low_ratio,
            "binning_note": binning_note,
            "conclusion": conclusion,
        }
        return ok(result, summary)
    except DataLabError as e:
        return err(e.code, str(e))
    except Exception:
        return err(EC.CALC, "计算失败，请检查数据内容与参数设置（详见服务端日志）")


def register(mcp) -> None:
    """注册到 MCPServer（mcp 2.x，工具名 = 函数名）。"""
    mcp.add_tool(chi_square_test, description=__import__("sys").modules[__name__].__doc__)

