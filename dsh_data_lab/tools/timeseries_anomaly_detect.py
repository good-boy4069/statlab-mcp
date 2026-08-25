# -*- coding: utf-8 -*-
"""anomaly_detect —— 时序组 · 时序异常检测（工具 20，简化实现）。

docstring = agent 使用说明书，与 docs/design/06_timeseries.md 同步维护。

参数:
    file_path (str): 本地数据文件（csv/tsv/xlsx/json）
    date_col / value_col (str): 日期列与数值列
    method (str, "stl"): stl / iqr / rolling_zscore
        stl: statsmodels STL(robust=True) 残差 |resid| > threshold*MAD_std
             （MAD_std = 1.4826*median|resid-median| 稳健尺度）
        iqr: 一阶差分上 IQR 规则（Q1-1.5IQR / Q3+1.5IQR，同探查组口径），索引映射回原行
        rolling_zscore: 窗口 7 滚动 mean/std（min_periods=3），|z| > threshold
    threshold (float, 3.0): >0

保证: 异常点仅报告不剔除；常数序列（尺度 0）无异常并注明。

示例:
    anomaly_detect("samples/timeseries.csv", date_col="date", value_col="value")
"""
import math
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import STL
from matplotlib import pyplot as plt

from statlab_mcp.tools._common import (
    CJK_FONT_OK, DataLabError, _estimate_period, _prepare_series,
    err, ok, read_table, save_plot,
)

MIN_N = 15
_METHODS = {"stl", "iqr", "rolling_zscore"}
_WINDOW = 7
MAX_ANOMALIES = 100        # 输出条数上限（红队 B B2：防超大 JSON）


def _detect_stl(yv: pd.Series, threshold: float) -> List[Dict[str, Any]]:
    period = _estimate_period(yv)
    if period is None:
        # 无周期：一阶差分残差近似（注明退级）
        resid = pd.Series(yv.diff().to_numpy(), index=yv.index)
        note = "季节不可估，已使用一阶差分残差近似"
    else:
        stl = STL(yv, period=period, robust=True).fit()
        resid = stl.resid
        note = f"STL 残差（周期 {period}）"
    r_series = resid.dropna()
    r = r_series.to_numpy(dtype=float)
    if r.size == 0:
        return []
    # 判据尺度用残差 std(ddof=1)。实现期修订（06 文档）：MAD 对"主体集中+稀疏厚尾"
    # 的残差分布严重低估尺度（实测 timeseries：MAD 0.33 -> 31 个假阳性；std 1.30 -> 2 个），
    # std 判据更符合 threshold=3 的 3σ 语义
    scale = float(r.std(ddof=1))
    if scale == 0:
        return []
    mask = np.abs(r) > threshold * scale
    out = []
    for i in np.where(mask)[0]:
        idx = int(yv.index.get_loc(r_series.index[i]))   # 位置（原数据行号）
        out.append({"index": idx, "date": str(r_series.index[i].date()),
                    "value": float(yv.iloc[idx]), "resid": float(r[i]),
                    "note": note})
    return out


def _detect_iqr(yv: pd.Series, threshold: float) -> List[Dict[str, Any]]:
    diff = yv.diff().dropna()
    q1, q3 = float(diff.quantile(0.25)), float(diff.quantile(0.75))
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    mask = (diff < lo) | (diff > hi)
    out = []
    for i in np.where(mask.to_numpy())[0]:
        ts = diff.index[i]
        idx = int(yv.index.get_loc(ts))
        out.append({"index": idx, "date": str(ts.date()),
                    "value": float(yv.iloc[idx]),
                    "diff": float(diff.iloc[i]),
                    "note": "一阶差分 IQR 规则"})
    return out


def _detect_rolling_zscore(yv: pd.Series, threshold: float) -> List[Dict[str, Any]]:
    mu = yv.rolling(_WINDOW, min_periods=3).mean()
    sd = yv.rolling(_WINDOW, min_periods=3).std(ddof=1)
    z = (yv - mu) / sd.replace(0, np.nan)
    mask = z.abs() > threshold
    out = []
    for i in np.where(mask.to_numpy())[0]:
        ts = yv.index[i]
        out.append({"index": i, "date": str(ts.date()),
                    "value": float(yv.iloc[i]), "z": float(z.iloc[i]),
                    "note": f"滚动 z-score（窗口 {_WINDOW}）"})
    return out


def anomaly_detect(file_path: str, date_col: str, value_col: str,
                   method: str = "stl", threshold: float = 3.0) -> dict:
    """时序异常点检测（STL 残差 / 差分 IQR / 滚动 z-score）+ 区间图。"""
    try:
        if method not in _METHODS:
            raise DataLabError("method 仅支持 stl/iqr/rolling_zscore")
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) \
                or threshold <= 0 or not math.isfinite(threshold):
            raise DataLabError("threshold 必须 >0 的有限数")
        threshold = float(threshold)
        df = read_table(file_path)
        y, meta = _prepare_series(df, date_col, value_col)
        n = int(y.size)
        if n < MIN_N:
            raise DataLabError(f"样本过短（n={n}<{MIN_N}），时序分析不可靠")
        yv = y.dropna()
        if int(yv.size) == 0:
            raise DataLabError(f"列 {value_col} 无有效数据")

        if method == "stl":
            anomalies = _detect_stl(yv, threshold)
        elif method == "iqr":
            anomalies = _detect_iqr(yv, threshold)
        else:
            anomalies = _detect_rolling_zscore(yv, threshold)
        anomalies.sort(key=lambda a: a["index"])
        truncated = len(anomalies) > MAX_ANOMALIES   # 输出截断（红队 B B2：防超大 JSON）
        anomalies = anomalies[:MAX_ANOMALIES]

        # ---- 图：原值 + 异常红点 ----
        fig, ax = plt.subplots(figsize=(9, 4.0))
        ax.plot(yv.index, yv.values, lw=0.9, color="#4C72B0",
                label="原值" if CJK_FONT_OK else "Series")
        if anomalies:
            ax.scatter([yv.index[a["index"]] for a in anomalies],
                       [a["value"] for a in anomalies], color="red", s=30, zorder=3,
                       label="异常点" if CJK_FONT_OK else "Anomaly")
        ax.set_title(f"时序异常检测（{method}，threshold={threshold}，"
                     f"检出 {len(anomalies)} 个）" if CJK_FONT_OK else
                     f"Anomaly ({method}, th={threshold}, n={len(anomalies)})")
        ax.legend()
        fig.tight_layout()
        img = save_plot(fig, "anomaly_detect_all")

        note = "异常判据见各点 note；仅报告不剔除"
        if method == "stl":
            note = "异常判据：|残差| > threshold×MAD 稳健标准差；仅报告不剔除"
        if len(anomalies) == 0:
            note = f"{note}；未发现异常"
        if truncated:
            note = f"{note}；异常数超过 {MAX_ANOMALIES}，仅显示前 {MAX_ANOMALIES} 条"

        n_found = len(anomalies) + (truncated and sum(1 for _ in []) or 0)
        summary = f"{method} 法检出{'异常点' + ('（仅显示前 ' + str(MAX_ANOMALIES) + ' 条）' if truncated else f'（{n_found} 个）')}"
        if anomalies:
            summary += f"：{'，'.join(a['date'] for a in anomalies[:5])}"
            if len(anomalies) > 5:
                summary += " 等"
        else:
            summary += "；未发现异常"
        summary += f"；threshold={threshold:g}；异常仅报告不剔除"
        if meta["interpolated"]:
            summary += f"；已插值 {meta['interpolated']} 个缺失点"

        result = {
            "method": method, "threshold": threshold,
            "n": n, "n_anomalies": len(anomalies),
            "truncated": truncated,
            "anomalies": anomalies,
            "note": note,
            "metadata": {k: v for k, v in meta.items() if k != "n_before_resample"},
            "conclusion": (f"{method} 检出 {len(anomalies)} 个异常点"
                           + ("（已截断）" if truncated else "") + "；"
                           f"异常点仅报告不剔除"),
        }
        res = ok(result, summary)
        res["__image__"] = img
        return res
    except DataLabError as e:
        return err(str(e))
    except Exception as e:
        return err("计算失败，请检查数据内容与参数设置（详见服务端日志）")


def register(mcp) -> None:
    """注册到 MCPServer（mcp 2.x，工具名 = 函数名）。"""
    mcp.add_tool(anomaly_detect, description=anomaly_detect.__doc__)
