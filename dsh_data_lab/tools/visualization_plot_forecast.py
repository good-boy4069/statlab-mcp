# -*- coding: utf-8 -*-
"""plot_forecast —— 可视化组 · 时序折线图（工具 24，核心实现）。

原值折线 + 7 日移动平均线；**仅作图不预测**（预测见工具 17）。
五项统一前置由 _common._prepare_series 承载（插值/聚合/时区均报告）。
"""
from typing import Any, Dict

import pandas as pd
from matplotlib import pyplot as plt

from statlab_mcp.tools._common import (
    CJK_FONT_OK, DataLabError, _prepare_series,
    err, ok, read_table, save_plot,
)

MIN_N = 5
MA_WINDOW = 7


def plot_forecast(file_path: str, date_col: str, value_col: str) -> dict:
    """时序折线图 + 7 日均线（仅作图，不预测）。"""
    try:
        df = read_table(file_path)
        y, meta = _prepare_series(df, date_col, value_col)
        n = int(y.size)
        if n < MIN_N:
            raise DataLabError(f"样本过短（n={n}<{MIN_N}），无法作图")
        ma = y.rolling(MA_WINDOW, min_periods=3).mean()

        fig, ax = plt.subplots(figsize=(9, 4.0))
        ax.plot(y.index, y.values, lw=0.9, color="#4C72B0",
                label="原值" if CJK_FONT_OK else "Series")
        ax.plot(ma.index, ma.values, lw=1.4, color="red",
                label=f"{MA_WINDOW} 日均线" if CJK_FONT_OK else f"MA{MA_WINDOW}")
        ax.set_title(f"{value_col} 时间序列（n={n}）" if CJK_FONT_OK
                     else f"{value_col} time series (n={n})")
        ax.legend()
        fig.tight_layout()
        img = save_plot(fig, "plot_forecast_all")

        result = {
            "n": n, "series_min": float(y.min()), "series_max": float(y.max()),
            "series_last": float(y.iloc[-1]),
            "metadata": {k: v for k, v in meta.items() if k != "n_before_resample"},
        }
        summary = (f"时序图已保存：{value_col}（n={n}，范围 "
                   f"[{result['series_min']:.2f}, {result['series_max']:.2f}]，"
                   f"末端 {result['series_last']:.2f}，含 {MA_WINDOW} 日均线）")
        if meta["interpolated"]:
            summary += f"；已插值 {meta['interpolated']} 个缺失点"
        if meta["utc_note"]:
            summary += f"；{meta['utc_note']}"
        res = ok(result, summary)
        res["__image__"] = img
        return res
    except DataLabError as e:
        return err(str(e))
    except Exception as e:
        return err(f"计算失败: {e}")


def register(mcp) -> None:
    mcp.add_tool(plot_forecast)