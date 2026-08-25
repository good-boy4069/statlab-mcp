# -*- coding: utf-8 -*-
"""plot_histogram —— 可视化组 · 直方图（工具 22，核心实现）。

单列分布直方图，图上标 n/mean/std；分箱 = min(40, max(8, ceil(sqrt(n))))。
"""
import math
from typing import Any, Dict

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

from statlab_mcp.tools._common import (
    CJK_FONT_OK, DataLabError, err, ok, read_table, save_plot,
)


def plot_histogram(file_path: str, column: str) -> dict:
    """单列直方图（图上标 n/mean/std）。"""
    try:
        df = read_table(file_path)
        if column not in df.columns:
            raise DataLabError(f"缺少必需列: {column}；实际列: {list(df.columns)}")
        if not pd.api.types.is_numeric_dtype(df[column]):
            raise DataLabError(f"列 {column} 不是数值列，无法画直方图")
        v = df[column].dropna()
        n = int(v.size)
        if n < 2:
            raise DataLabError(f"至少需要 2 个有效值，当前 {n}")
        n_missing = int(len(df) - n)
        mean, std = float(v.mean()), float(v.std(ddof=1))
        bins = min(40, max(8, int(math.ceil(math.sqrt(n)))))

        fig, ax = plt.subplots(figsize=(6.5, 4.2))
        ax.hist(v.to_numpy(dtype=float), bins=bins, edgecolor="white", color="#4C72B0")
        ax.set_xlabel(column)
        ax.set_ylabel("频数" if CJK_FONT_OK else "Count")
        ax.set_title(f"{column} 分布（n={n}，均值 {mean:.2f}，sd {std:.2f}）"
                     if CJK_FONT_OK else f"{column} (n={n}, mean={mean:.2f}, sd={std:.2f})")
        fig.tight_layout()
        img = save_plot(fig, f"plot_histogram_{column}")

        result = {"column": column, "n": n, "n_missing": n_missing,
                  "mean": mean, "std": std, "bins": bins}
        summary = (f"直方图已保存：{column}（n={n}，均值 {mean:.2f}，sd {std:.2f}，"
                   f"{bins} 箱" + (f"，缺失 {n_missing}" if n_missing else "") + "）")
        res = ok(result, summary)
        res["__image__"] = img
        return res
    except DataLabError as e:
        return err(str(e))
    except Exception as e:
        return err("计算失败，请检查数据内容与参数设置（详见服务端日志）")


def register(mcp) -> None:
    mcp.add_tool(plot_histogram, description=__import__("sys").modules[__name__].__doc__)

