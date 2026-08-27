"""plot_heatmap —— 可视化组 · 相关热力图（工具 23，核心实现）。

全部数值列两两 Pearson 相关热力图（格内标 r；常量列对应 r=null）。
矩阵用 pandas .corr()（与 correlation_matrix 的 scipy pearsonr 同公式），
本工具不做 p 值与校正（与工具 4 明确分工）。
inline 数据:
    本工具支持可选 inline_data 参数（v1.2.0 起）：与 file_path 二选一，
    支持 records 数组或 {"header": [...], "rows": [[...], ...]} 对象两种形态；
    规模上限/类型域/data_source 来源标注见 statlab_mcp/docs/SPEC.md 第 12 节。

"""
from typing import Any

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

from statlab_mcp.tools._common import (
    CJK_FONT_OK,
    EC,
    DataLabError,
    err,
    ok,
    resolve_data,
    save_plot,
)

MAX_COLS = 20


def plot_heatmap(file_path: str | None = None,
                   inline_data: list | dict | None = None) -> dict:
    """数值列相关热力图（格内标 r）。"""
    try:
        df, data_source = resolve_data(file_path, inline_data)
        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        excluded = [c for c in df.columns if c not in numeric_cols]
        if len(numeric_cols) < 2:
            raise DataLabError("至少需要 2 个数值列才能画相关热力图", EC.INSUFFICIENT)
        if len(numeric_cols) > MAX_COLS:
            raise DataLabError(f"数值列超过 {MAX_COLS} 个，相关矩阵过大，请先挑选列", EC.SCALE)

        corr = df[numeric_cols].corr().to_numpy(dtype=float)
        n = len(df)

        fig, ax = plt.subplots(figsize=(max(5.0, 0.9 * len(numeric_cols)),
                                        max(4.0, 0.8 * len(numeric_cols))))
        im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
        ax.set_xticks(range(len(numeric_cols)))
        ax.set_xticklabels(numeric_cols, rotation=45, ha="right")
        ax.set_yticks(range(len(numeric_cols)))
        ax.set_yticklabels(numeric_cols)
        for i in range(len(numeric_cols)):
            for j in range(len(numeric_cols)):
                v = corr[i, j]
                txt = "—" if np.isnan(v) else f"{v:.2f}"
                ax.text(j, i, txt, ha="center", va="center",
                        fontsize=7 if len(numeric_cols) > 8 else 8)
        fig.colorbar(im, ax=ax, shrink=0.85)
        ax.set_title("数值列相关热力图（Pearson r）" if CJK_FONT_OK
                     else "Correlation heatmap (Pearson r)")
        fig.tight_layout()
        img = save_plot(fig, "plot_heatmap_all")

        matrix: dict[str, dict[str, Any]] = {}
        for i, a in enumerate(numeric_cols):
            matrix[a] = {}
            for j, b in enumerate(numeric_cols):
                v = corr[i, j]
                matrix[a][b] = None if np.isnan(v) else float(v)

        result = {"numeric_columns": numeric_cols, "n": n,
                  "excluded_columns": excluded, "matrix": matrix}
        summary = (f"相关热力图已保存（{len(numeric_cols)} 个数值列，n={n}"
                   + (f"，已排除 {len(excluded)} 列非数值" if excluded else "") + "）")
        res = ok(result, summary)
        res["data_source"] = data_source
        res["__image__"] = img
        return res
    except DataLabError as e:
        return err(e.code, str(e))
    except Exception:
        return err(EC.CALC, "计算失败，请检查数据内容与参数设置（详见服务端日志）")


def register(mcp) -> None:
    """注册到 MCPServer（mcp 2.x，工具名 = 函数名）。"""
    mcp.add_tool(plot_heatmap, description=__import__("sys").modules[__name__].__doc__)

