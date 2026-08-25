# -*- coding: utf-8 -*-
"""tests/test_trend_analysis.py —— 工具 19 测试（规范 10）。

独立性：Theil-Sen 斜率手算硬编码（小样本点对枚举，Excel 可复核）；
timeseries.csv 已知线性趋势（25/119≈0.21/天）语义核验。
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools.timeseries_trend_analysis import trend_analysis

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


def _call(p, **kw) -> dict:
    r = trend_analysis(str(p), **kw)
    assert r["status"] == "ok", r.get("message", r)
    return r


def _csv(tmp_path, dates, values, dc="date", vc="value"):
    p = tmp_path / "tr.csv"
    pd.DataFrame({dc: dates, vc: values}).to_csv(p, index=False, encoding="utf-8-sig")
    return p


# ---------------- Theil-Sen 手算硬编码 ----------------

def test_theil_sen_hand_calculated(tmp_path):
    """10 点 y=0.5t（t=0..9）：所有点对斜率均为 0.5 -> 中位数 0.5（手算显然）。
    另：y=2t+1 -> 所有点对斜率 2.0。"""
    dates = pd.date_range("2025-01-01", periods=10).strftime("%Y-%m-%d")
    p = _csv(tmp_path, dates, 0.5 * np.arange(10))
    assert _call(p, date_col="date", value_col="value",
                 method="theil_sen")["result"]["slope"] == pytest.approx(0.5)
    p2 = _csv(tmp_path, dates, 2 * np.arange(10) + 1)
    assert _call(p2, date_col="date", value_col="value",
                 method="theil_sen")["result"]["slope"] == pytest.approx(2.0)


# ---------------- 语义核验（timeseries 已知趋势） ----------------

def test_timeseries_significant_upward():
    r = _call(SAMPLES / "timeseries.csv", date_col="date", value_col="value")
    rs = r["result"]
    assert rs["monotonic"] is True
    assert rs["trend_direction"] == "上升"
    assert rs["p_value"] < 0.001
    assert 0.18 < rs["slope"] < 0.30                 # 线性趋势 25/119≈0.21/天 ±季节扰动
    assert rs["tau"] > 0.5                        # 实测基准 0.633（季节成分拉低 tau）
    assert "季节成分" in r["summary"]                # 季节警示
    assert rs["metadata"]["interpolated"] == 3


def test_downward_series(tmp_path):
    dates = pd.date_range("2025-01-01", periods=40).strftime("%Y-%m-%d")
    p = _csv(tmp_path, dates, np.linspace(50, 10, 40))
    rs = _call(p, date_col="date", value_col="value")["result"]
    assert rs["trend_direction"] == "下降" and rs["monotonic"] is True


def test_constant_series(tmp_path):
    dates = pd.date_range("2025-01-01", periods=30).strftime("%Y-%m-%d")
    p = _csv(tmp_path, dates, [7.0] * 30)
    rs = _call(p, date_col="date", value_col="value")["result"]
    assert rs["tau"] == pytest.approx(0.0)
    assert rs["slope"] == pytest.approx(0.0)
    assert rs["trend_direction"] == "无" and rs["monotonic"] is False


# ---------------- 校验与边界 ----------------

def test_errors(tmp_path):
    assert "method 仅支持" in trend_analysis(str(SAMPLES / "timeseries.csv"),
                                              date_col="date", value_col="value",
                                              method="slope_test")["message"]
    dates = pd.date_range("2025-01-01", periods=6).strftime("%Y-%m-%d")
    p = _csv(tmp_path, dates, np.arange(6.0))
    r = trend_analysis(str(p), date_col="date", value_col="value")
    assert r["status"] == "error" and "样本过短" in r["message"]
    assert "缺少必需列" in trend_analysis(str(SAMPLES / "clean.csv"), date_col="nope",
                                           value_col="score")["message"]
    assert trend_analysis(str(SAMPLES / "nope.csv"), date_col="d",
                          value_col="v")["status"] == "error"


def test_both_methods_agree_direction():
    a = _call(SAMPLES / "timeseries.csv", date_col="date", value_col="value",
              method="mann_kendall")
    b = _call(SAMPLES / "timeseries.csv", date_col="date", value_col="value",
              method="theil_sen")
    assert a["result"]["trend_direction"] == b["result"]["trend_direction"] == "上升"
    assert a["result"]["slope"] == pytest.approx(b["result"]["slope"])   # 同斜率口径


def test_json_safe_and_deterministic():
    r1 = _call(SAMPLES / "timeseries.csv", date_col="date", value_col="value")
    json.dumps(r1, allow_nan=False, ensure_ascii=False)
    r2 = trend_analysis(str(SAMPLES / "timeseries.csv"), date_col="date",
                        value_col="value")
    assert json.dumps(r1, sort_keys=True, ensure_ascii=False) == json.dumps(
        r2, sort_keys=True, ensure_ascii=False)