# -*- coding: utf-8 -*-
"""tests/test_seasonal_decompose.py —— 工具 18 测试（规范 10）。

独立性：timeseries.csv 生成公式已知（趋势 10->35 + 5*sin(2pi t/30) + σ=1.5 噪声）：
显式 additive 分解时季节幅度应 ≈10（峰峰值）、趋势末端 ≈35、周期自动估计 =30。
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools.timeseries_seasonal_decompose import seasonal_decompose

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


def _call(p, **kw) -> dict:
    r = seasonal_decompose(str(p), **kw)
    assert r["status"] == "ok", r.get("message", r)
    return r


def _csv(tmp_path, dates, values, dc="date", vc="value"):
    p = tmp_path / "sd.csv"
    pd.DataFrame({dc: dates, vc: values}).to_csv(p, index=False, encoding="utf-8-sig")
    return p


# ---------------- 生成公式数学核验 ----------------

def test_timeseries_additive_hand_checked():
    """additive 分解：period 自动=30、季节幅度≈10（5*sin 峰峰）、趋势末端≈35。"""
    r = _call(SAMPLES / "timeseries.csv", date_col="date", value_col="value",
              model="additive")
    rs = r["result"]
    assert rs["period"] == 30
    # 幅度=10 为生成公式理论值；相位平均仅有 4 点/相位，噪声极值统计使估计
    # 天然偏大（实测 11~13），断言取统计现实区间 8~15
    assert 8.0 < rs["components"]["seasonal"]["amplitude"] < 15.0
    assert rs["components"]["trend"]["last"] == pytest.approx(34.0, abs=2.0)
    assert 8.0 < rs["components"]["trend"]["mean"] < 26.0
    assert len(rs["seasonal_factors"]) == 30
    md = rs["metadata"]
    assert md["interpolated"] == 3
    img = Path(r["__image__"])
    assert img.suffix == ".png" and img.exists()


def test_auto_model_choice_and_positive(tmp_path):
    """全正序列 -> auto 选 multiplicative；含非正 -> additive 并注明。"""
    rng = np.random.default_rng(8)
    dates = pd.date_range("2025-01-01", periods=60, freq="D").strftime("%Y-%m-%d")
    vals = 20 + 5 * np.sin(2 * np.pi * np.arange(60) / 12) + rng.normal(0, 1, 60)
    p = _csv(tmp_path, dates, vals)
    r1 = _call(p, date_col="date", value_col="value")        # auto -> multiplicative
    assert r1["result"]["model"] == "multiplicative"
    vals2 = vals.copy()
    vals2[5] = -3.0                                           # 注入非正值
    p2 = _csv(tmp_path, dates, vals2)
    r2 = _call(p2, date_col="date", value_col="value")       # auto -> additive + 注明
    assert r2["result"]["model"] == "additive"
    assert "additive" in r2["summary"]


# ---------------- 校验与边界 ----------------

def test_errors(tmp_path):
    dates = pd.date_range("2025-01-01", periods=30).strftime("%Y-%m-%d")
    p = _csv(tmp_path, dates, np.arange(30.0) + 5)
    assert "model 仅支持" in seasonal_decompose(str(p), date_col="date",
                                                 value_col="value",
                                                 model="holidays")["message"]
    assert "period 必须在" in seasonal_decompose(str(p), date_col="date",
                                                 value_col="value",
                                                 period=100)["message"]
    assert "period 必须在" in seasonal_decompose(str(p), date_col="date",
                                                 value_col="value",
                                                 period=1)["message"]
    assert "period 必须是整数" in seasonal_decompose(str(p), date_col="date",
                                                      value_col="value",
                                                      period=6.5)["message"]
    # multiplicative + 非正值
    vals = np.arange(10.0, 40.0)
    vals[3] = -1.0
    p2 = _csv(tmp_path, dates, vals)
    r = seasonal_decompose(str(p2), date_col="date", value_col="value",
                           model="multiplicative")
    assert r["status"] == "error" and "全正值" in r["message"]
    # 短样本
    p3 = _csv(tmp_path, dates[:12], np.arange(12.0))
    r3 = seasonal_decompose(str(p3), date_col="date", value_col="value")
    assert r3["status"] == "error" and "样本过短" in r3["message"]
    assert seasonal_decompose(str(SAMPLES / "nope.csv"), date_col="d",
                              value_col="v")["status"] == "error"


def test_explicit_period_used(tmp_path):
    r = _call(SAMPLES / "timeseries.csv", date_col="date", value_col="value",
              period=10, model="additive")
    assert r["result"]["period"] == 10
    assert len(r["result"]["seasonal_factors"]) == 10


def test_json_safe_and_deterministic():
    r1 = _call(SAMPLES / "timeseries.csv", date_col="date", value_col="value")
    json.dumps(r1, allow_nan=False, ensure_ascii=False)
    r2 = seasonal_decompose(str(SAMPLES / "timeseries.csv"), date_col="date",
                            value_col="value")
    assert json.dumps(r1["result"], sort_keys=True, ensure_ascii=False) == json.dumps(
        r2["result"], sort_keys=True, ensure_ascii=False)