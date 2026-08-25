# -*- coding: utf-8 -*-
"""plot_box —— 可视化组 · 箱线图（工具 25，核心实现）。

单列箱线图：图上标五数概括（min/q1/中位/q3/max）与 IQR 异常数（同 outlier_detect 口径，
但仅单列、无异常点导出表——异常定位请用工具 5）。
"""
from typing import Any, Dict

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

from statlab_mcp.tools._common import (
    CJK_FONT_OK, DataLabError, err, ok, read_table, save_plot,
)

MIN_N = 4


def plot_box(file_path: str, column: str) -> dict:
    """单列箱线图（图上标五数 + 异常数）。"""
    try:
        df = read_table(file_path)
        if column not in df.columns:
            raise DataLabError(f"缺少必需列: {column}；实际列: {list(df.columns)}")
        if not pd.api.types.is_numeric_dtype(df[column]):
            raise DataLabError(f"列 {column} 不是数值列，无法画箱线图")
        v = df[column].dropna()
        n = int(v.size)
        if n == 0:
            raise DataLabError(f"列 {column} 无有效数据")
        n_missing = int(len(df) - n)

        q1 = float(v.quantile(0.25)) if n >= MIN_N else None
        q3 = float(v.quantile(0.75)) if n >= MIN_N else None
        median = float(v.median())
        n_outliers = 0
        if n >= MIN_N:
            iqr = q3 - q1
            lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            arr = v.to_numpy(dtype=float)
            if iqr == 0:
                n_outliers = 0                      # 常量列无异常（同 outlier_detect）
            else:
                n_outliers = int(np.sum((arr < lo) | (arr > hi)))
        else:
            lo = hi = None

        fig, ax = plt.subplots(figsize=(3.6, 4.4))
        ax.boxplot(v.to_numpy(dtype=float))
        ax.set_xticks([])
        ax.set_ylabel(column)
        stats_txt = f"n={n}"
        if q1 is not None:
            stats_txt += f"，Q1={q1:.2f}，中位={median:.2f}，Q3={q3:.2f}"
        stats_txt += f"，异常={n_outliers}"
        ax.set_title(f"{column} 箱线图（{stats_txt}）" if CJK_FONT_OK
                     else f"{column} boxplot ({stats_txt})")
        fig.tight_layout()
        img = save_plot(fig, f"plot_box_{column}")

        result = {"column": column, "n": n, "n_missing": n_missing,
                  "q1": q1, "median": median, "q3": q3,
                  "lower_bound": lo, "upper_bound": hi,
                  "n_outliers": n_outliers}
        summary = (f"箱线图已保存：{column}（n={n}"
                   + (f"，Q1={q1:.2f}/中位 {median:.2f}/Q3={q3:.2f}" if q1 is not None
                      else "，样本不足 4 无法定义 IQR")
                   + f"，IQR 异常 {n_outliers} 个"
                   + (f"，缺失 {n_missing}" if n_missing else "") + "）")
        res = ok(result, summary)
        res["__image__"] = img
        return res
    except DataLabError as e:
        return err(str(e))
    except Exception as e:
        return err("计算失败，请检查数据内容与参数设置（详见服务端日志）")


def register(mcp) -> None:
    mcp.add_tool(plot_box, description=__import__("sys").modules[__name__].__doc__)

