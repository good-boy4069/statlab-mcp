# -*- coding: utf-8 -*-
"""plot_scatter —— 可视化组 · 散点图（工具 21，核心实现）。

生成 x-y 散点图，图上标注 Pearson r 与样本量；缺失按成对剔除并报数。
图协议走 _common.save_plot（附录 D）；返回顶层 __image__ 绝对路径。
"""
from typing import Any, Dict

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

from statlab_mcp.tools._common import (
    CJK_FONT_OK, DataLabError, err, ok, read_table, save_plot,
)


def plot_scatter(file_path: str, x_col: str, y_col: str) -> dict:
    """x-y 散点图（图上标 r 与 n）。"""
    try:
        df = read_table(file_path)
        for c in (x_col, y_col):
            if c not in df.columns:
                raise DataLabError(f"缺少必需列: {c}；实际列: {list(df.columns)}")
            if not pd.api.types.is_numeric_dtype(df[c]):
                raise DataLabError(f"列 {c} 不是数值列，无法画散点图")
        m = df[[x_col, y_col]].dropna()
        n = int(len(m))
        if n == 0:
            raise DataLabError(f"列 {x_col}/{y_col} 无有效数据（成对剔除后为空）")
        dropped = int(len(df) - n)
        x, y = m[x_col].to_numpy(dtype=float), m[y_col].to_numpy(dtype=float)

        r = None
        if n >= 2 and float(x.std(ddof=1)) > 0 and float(y.std(ddof=1)) > 0:
            r = float(np.corrcoef(x, y)[0, 1])

        fig, ax = plt.subplots(figsize=(6.5, 5))
        ax.scatter(x, y, s=18, alpha=0.7)
        ax.set_xlabel(x_col)
        ax.set_ylabel(y_col)
        r_txt = f"，r={r:.2f}" if r is not None else "，r 不可计算（常量列或 n<2）"
        ax.set_title(f"{x_col} vs {y_col}（n={n}{r_txt}）"
                     if CJK_FONT_OK else f"{x_col} vs {y_col} (n={n}, r={r})")
        fig.tight_layout()
        img = save_plot(fig, "plot_scatter_all")

        result = {"x_col": x_col, "y_col": y_col, "n": n,
                  "dropped_rows": dropped, "pearson_r": r}
        summary = (f"散点图已保存：{x_col} vs {y_col}（n={n}"
                   + (f"，r={r:.2f}" if r is not None else "，r 不可计算")
                   + (f"，成对剔除缺失 {dropped} 行" if dropped else "")
                   + "）；相关≠因果")
        res = ok(result, summary)
        res["__image__"] = img
        return res
    except DataLabError as e:
        return err(str(e))
    except Exception as e:
        return err(f"计算失败: {e}")


def register(mcp) -> None:
    mcp.add_tool(plot_scatter)