# -*- coding: utf-8 -*-
"""tests/test_anomaly_detect.py —— 工具 20 测试（规范 10）。

独立性：注入已知 spike（+10σ）后三种方法都应检出的语义核验；
平滑序列（timeseries.csv，σ=1.5）应无/极少异常（3.0σ 阈值）。
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools.timeseries_anomaly_detect import anomaly_detect

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


def _call(p, **kw) -> dict:
    r = anomaly_detect(str(p), **kw)
    assert r["status"] == "ok", r.get("message", r)
    return r


# ---------------- 平滑序列：应无/极少异常 ----------------

def test_clean_series_few_anomalies():
    """平滑序列应极少异常（判据=残差 std：实测 3σ 检出 2 个；MAD 版 31 个过度检出，
    已实现期修订为 std，见工具 docstring）。"""
    r = _call(SAMPLES / "timeseries.csv", date_col="date", value_col="value",
              method="stl")
    assert r["result"]["n_anomalies"] <= 2
    for method in ("iqr", "rolling_zscore"):
        rs = _call(SAMPLES / "timeseries.csv", date_col="date", value_col="value",
                   method=method)["result"]
        assert rs["n_anomalies"] <= 2, method
    img = Path(r["__image__"])
    assert img.suffix == ".png" and img.exists()


# ---------------- 注入 spike：应检出 ----------------

def test_injected_spike_detected(tmp_path):
    """120 天平滑序列注入 +12 跳变（远大于 σ=1.5）。stl/iqr 用 3.0；
    rolling_zscore 用 2.0（窗口 std 被尖峰污染导致的"自我宽恕"是方法固有特性，实测 z≈2.0）。"""
    rng = np.random.default_rng(5)
    n = 120
    t = np.arange(n)
    base = 30 + 5 * np.sin(2 * np.pi * t / 30) + rng.normal(0, 1.5, n)
    base[60] += 12.0
    dates = pd.date_range("2025-01-01", periods=n).strftime("%Y-%m-%d")
    p = tmp_path / "spike.csv"
    pd.DataFrame({"date": dates, "value": base}).to_csv(p, index=False,
                                                        encoding="utf-8-sig")
    for method, th in (("stl", 3.0), ("iqr", 3.0), ("rolling_zscore", 2.0)):
        rs = _call(p, date_col="date", value_col="value", method=method,
                   threshold=th)["result"]
        hit = any(a["index"] == 60 for a in rs["anomalies"])
        assert hit, method
        assert any(a["note"] for a in rs["anomalies"])


def test_lower_threshold_more_sensitive(tmp_path):
    rng = np.random.default_rng(6)
    n = 80
    dates = pd.date_range("2025-01-01", periods=n).strftime("%Y-%m-%d")
    vals = rng.normal(50, 2, n)
    vals[40] += 6.0
    p = tmp_path / "th.csv"
    pd.DataFrame({"date": dates, "value": vals}).to_csv(p, index=False,
                                                        encoding="utf-8-sig")
    r3 = _call(p, date_col="date", value_col="value", method="rolling_zscore",
               threshold=3.0)
    r2 = _call(p, date_col="date", value_col="value", method="rolling_zscore",
               threshold=1.5)
    assert r2["result"]["n_anomalies"] >= r3["result"]["n_anomalies"]   # 阈值越低越敏感
    assert any(a["index"] == 40 for a in r2["result"]["anomalies"])


# ---------------- 校验与边界 ----------------

def test_errors():
    assert "method 仅支持" in anomaly_detect(
        str(SAMPLES / "timeseries.csv"), date_col="date", value_col="value",
        method="isolation")["message"]
    r = anomaly_detect(str(SAMPLES / "timeseries.csv"), date_col="date",
                       value_col="value", threshold=0.0)
    assert r["status"] == "error" and "threshold 必须 >0" in r["message"]
    assert "缺少必需列" in anomaly_detect(str(SAMPLES / "clean.csv"), date_col="nope",
                                           value_col="score")["message"]
    assert anomaly_detect(str(SAMPLES / "nope.csv"), date_col="d",
                          value_col="v")["status"] == "error"


def test_constant_series_no_anomalies(tmp_path):
    dates = pd.date_range("2025-01-01", periods=30).strftime("%Y-%m-%d")
    p = tmp_path / "c.csv"
    pd.DataFrame({"date": dates, "value": [7.0] * 30}).to_csv(p, index=False,
                                                              encoding="utf-8-sig")
    for method in ("stl", "iqr", "rolling_zscore"):
        rs = _call(p, date_col="date", value_col="value", method=method)["result"]
        assert rs["n_anomalies"] == 0, method     # 尺度 0 防护


def test_json_safe_and_deterministic():
    r1 = _call(SAMPLES / "timeseries.csv", date_col="date", value_col="value")
    json.dumps(r1, allow_nan=False, ensure_ascii=False)
    r2 = anomaly_detect(str(SAMPLES / "timeseries.csv"), date_col="date",
                        value_col="value")
    assert json.dumps(r1["result"], sort_keys=True, ensure_ascii=False) == json.dumps(
        r2["result"], sort_keys=True, ensure_ascii=False)