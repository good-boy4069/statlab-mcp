"""correlation_matrix —— 数据探查组 · 相关矩阵（工具 4，核心实现）。

docstring = agent 使用说明书，与 statlab_mcp/docs/design/02_data_exploration_batch2.md 同步维护。

参数:
    file_path (str): 本地数据文件（csv/tsv/xlsx/json），仅接受本地路径
    method (str, "pearson"): pearson / spearman / kendall / kendalltau（逐对取 scipy，
        返回对象取 .statistic/.pvalue；pandas corr 无 p 值故不用；kendall 为
        kendalltau 的官方别名 v1.1.0 起，两者结果完全相同）
    p_adjust (str, "fdr_bh"): none / bonferroni / fdr_bh；默认 BH-FDR 并标注；
        校正单元 = 实际可计算的上三角对数（常量列对 r/p=null 不参与校正）
        （statsmodels.multipletests）

返回: 成功 {"status":"ok","result":{...},"summary":"..."}；失败 {"status":"error",...}
result: {method, n_pairs, p_adjust_method, excluded_columns,
         correlation, p_value, n_pairwise}（嵌套全矩阵；对角 r=1.0、p=null；
         常量列对 r/p=null；n_pairwise 为成对完整样本量）

口径（红队裁决 11）：每对成对完整样本；常量列 r/p=null 不参与校正；
数值列 >20 拒绝；排除非数值/全缺失列后 <2 列拒绝；p<0.001 只出现在 summary 文案。

示例:
    correlation_matrix("samples/clean.csv")
    correlation_matrix("samples/clean.csv", method="spearman", p_adjust="none")
"""
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sps

from statlab_mcp.tools._common import EC, DataLabError, err, ok, read_table

_METHODS = {"pearson": sps.pearsonr, "spearman": sps.spearmanr,
            "kendall": sps.kendalltau,          # v1.1.0 官方别名（SPEC 第 3 节）
            "kendalltau": sps.kendalltau}       # v1.0.3 起的历史枚举名，向后兼容保留
_P_ADJUST = {"none", "bonferroni", "fdr_bh"}
MAX_COLS = 20
STRONG_R = 0.7
MEDIUM_R = 0.3


def _fmt_p(p: float) -> str:
    return "<0.001" if p < 0.001 else f"{p:.4f}"


def correlation_matrix(file_path: str, method: str = "pearson", p_adjust: str = "fdr_bh") -> dict:
    """输出数值列两两相关矩阵 + 逐对 p 值（默认 fdr_bh 校正）+ 成对样本量。"""
    try:
        if method not in _METHODS:
            raise DataLabError(f"method 仅支持 {'/'.join(sorted(_METHODS))}", EC.PARAM)
        if p_adjust not in _P_ADJUST:
            raise DataLabError("p_adjust 仅支持 none/bonferroni/fdr_bh", EC.PARAM)
        df = read_table(file_path)

        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        keep = [c for c in numeric_cols if df[c].notna().any()]   # 剔除全缺失数值列
        excluded = [c for c in df.columns if c not in keep]
        if len(keep) < 2:
            raise DataLabError("至少需要 2 个数值列才能计算相关矩阵", EC.INSUFFICIENT)
        if len(keep) > MAX_COLS:
            raise DataLabError(f"数值列超过 {MAX_COLS} 个，相关矩阵过大，请先挑选列", EC.SCALE)

        k = len(keep)
        pairs: list[tuple[int, int, Any, Any, int]] = []   # (i, j, stat, p, n)
        for i in range(k):
            x = df[keep[i]]
            for j in range(i + 1, k):
                y = df[keep[j]]
                m = x.notna() & y.notna()
                xv, yv = x[m], y[m]
                n = int(m.sum())
                stat = p = None
                if n >= 2 and float(xv.std(ddof=1)) > 0 and float(yv.std(ddof=1)) > 0:
                    res = _METHODS[method](xv.to_numpy(dtype=float), yv.to_numpy(dtype=float))
                    stat, p = float(res.statistic), float(res.pvalue)
                    p = min(p, 1.0)
                pairs.append((i, j, stat, p, n))

        # 多重比较校正（只对可计算的 p 校正，校正单元 k 对）
        computable = [(i, j, p) for (i, j, _, p, _) in pairs if p is not None]
        if p_adjust != "none" and computable:
            raw = np.array([p for _, _, p in computable])
            from statsmodels.stats.multitest import multipletests  # 延迟导入（P1-1）
            corrected = multipletests(
                raw, method="fdr_bh" if p_adjust == "fdr_bh" else "bonferroni")[1]
            adj_map = {(i, j): float(min(pc, 1.0)) for (i, j, _), pc in zip(computable, corrected, strict=False)}
        else:
            adj_map = {(i, j): p for (i, j, p) in computable}

        # 装配对称矩阵（对角 r=1.0、p=null、n=该列有效样本）
        corr: dict[str, dict[str, Any]] = {}
        pval: dict[str, dict[str, Any]] = {}
        npw: dict[str, dict[str, int]] = {}
        for i in range(k):
            a = keep[i]
            corr[a], pval[a], npw[a] = {}, {}, {}
            for j in range(k):
                b = keep[j]
                if i == j:
                    corr[a][b] = 1.0
                    pval[a][b] = None
                    npw[a][b] = int(df[a].notna().sum())
                else:
                    stat = p = None
                    for (ii, jj, s, pp, nn) in pairs:
                        if (ii == i and jj == j) or (ii == j and jj == i):
                            stat, p, _n = s, pp, nn
                            break
                    corr[a][b] = stat
                    pval[a][b] = adj_map.get((i, j), adj_map.get((j, i), p))
                    npw[a][b] = _n

        n_pairs = k * (k - 1) // 2
        n_adj = len(computable)   # 实际参与校正的对数（常量列对 r/p=null 不参与，外部评审 M7）
        if p_adjust == "none":
            adj_note = "未做多重比较校正"
            adj_short = adj_note
        elif p_adjust == "fdr_bh":
            adj_note = f"fdr_bh（Benjamini-Hochberg 校正，实际校正 {n_adj} 对）"
            adj_short = f"已应用 fdr_bh 校正（共 {n_adj} 对）"
        else:
            adj_note = f"bonferroni（Bonferroni 校正，实际校正 {n_adj} 对）"
            adj_short = f"已应用 bonferroni 校正（共 {n_adj} 对）"

        # summary 由代码模板拼数字生成（固定尾注"相关≠因果"）
        strong, medium, shown = [], [], 0
        for i in range(k):
            for j in range(i + 1, k):
                r = corr[keep[i]][keep[j]]
                if r is None:
                    continue
                shown += 1
                if abs(r) >= STRONG_R:
                    strong.append(f"{keep[i]}–{keep[j]} r={r:.2f}")
                elif abs(r) >= MEDIUM_R:
                    medium.append(f"{keep[i]}–{keep[j]} r={r:.2f}")
        parts = [f"{method} 相关（可算对 {shown}/{n_pairs}）"]
        parts.append(f"强相关对 {len(strong)} 个：{'; '.join(strong)}" if strong
                     else "无强相关对（|r|<0.7）")
        if medium:
            parts.append("中等： " + "; ".join(medium))
        parts.append(f"p 值：{adj_short}")
        if excluded:
            parts.append(f"已排除 {len(excluded)} 列非数值/全缺失")
        summary = "；".join(parts) + "；相关≠因果"

        result = {
            "method": method,
            "n_pairs": n_pairs,
            "p_adjust_method": adj_note,
            "excluded_columns": excluded,
            "correlation": corr,
            "p_value": pval,
            "n_pairwise": npw,
        }
        return ok(result, summary)
    except DataLabError as e:
        return err(e.code, str(e))
    except Exception:
        return err(EC.CALC, "计算失败，请检查数据内容与参数设置（详见服务端日志）")


def register(mcp) -> None:
    """注册到 MCPServer（mcp 2.x，工具名 = 函数名）。"""
    mcp.add_tool(correlation_matrix, description=__import__("sys").modules[__name__].__doc__)

