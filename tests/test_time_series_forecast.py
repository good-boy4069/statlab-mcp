"""tests/test_time_series_forecast.py —— 工具 17 测试（规范 10）。

独立性：timeseries.csv 已知生成公式（趋势 10→35 + 周期 30 + σ=1.5 噪声），
预测值应落在趋势延伸附近（语义核验）；插值数人工核数=3；
重复聚合/时区/非法日期用构造数据验证前置逻辑。
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools.timeseries_time_series_forecast import time_series_forecast

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


def _call(p, **kw) -> dict:
    r = time_series_forecast(str(p), **kw)
    assert r["status"] == "ok", r.get("message", r)
    return r


def _csv(tmp_path, dates, values, dc="date", vc="value"):
    p = tmp_path / "ts.csv"
    pd.DataFrame({dc: dates, vc: values}).to_csv(p, index=False, encoding="utf-8-sig")
    return p


# ---------------- 语义核验（生成公式已知） ----------------

def test_timeseries_forecast_semantics():
    r = _call(SAMPLES / "timeseries.csv", date_col="date", value_col="value", horizon=14)
    rs = r["result"]
    assert rs["n"] == 120 and rs["horizon"] == 14
    assert rs["model"]["seasonal"] is True             # 季节可估 -> SARIMA
    assert rs["model"]["seasonal_order"][-1] == 30     # FFT 检出的周期必须=30（生成公式）
    f1 = rs["forecast"][0]
    assert 30 < f1["value"] < 40                       # 趋势末端 ~35，预测应在其附近
    assert f1["ci_lower"] <= f1["value"] <= f1["ci_upper"]
    assert len(rs["forecast"]) == 14
    md = rs["metadata"]
    assert md["interpolated"] == 3                     # 人工核数：3 个缺失点
    assert md["freq"] == "D"
    assert "已插值 3 个缺失点" in r["summary"]
    img = Path(r["__image__"])
    assert img.is_absolute() and img.suffix == ".png" and img.exists()


# ---------------- 前置：重复聚合 / 时区 / 非法日期 ----------------

def test_monthly_frequency_ok(tmp_path):
    """外部评审 S1 盲区：月频（MonthEnd 非固定频率）此前 100% 报错。
    48 个月线性趋势（2020-01 起）→ forecast horizon=6 必须成功且预测 6 步。"""
    dates = pd.date_range("2020-01-31", periods=48, freq="ME")
    vals = [10 + i * 0.5 for i in range(48)]
    p = tmp_path / "monthly.csv"
    pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "value": vals}).to_csv(
        p, index=False, encoding="utf-8-sig")
    r = _call(p, date_col="date", value_col="value", horizon=6)
    rs = r["result"]
    assert rs["n"] == 48
    assert len(rs["forecast"]) == 6
    assert rs["freq"] in ("ME", "M") or "M" in str(rs["freq"])   # 月频识别
    f1 = rs["forecast"][0]
    assert 32 < f1["value"] < 38                       # 趋势末端 ~33.5，首步预测应在其附近
    assert f1["ci_lower"] <= f1["value"] <= f1["ci_upper"]


def test_quarterly_frequency_ok(tmp_path):
    """外部评审 S1 盲区扩展：季频（QuarterEnd）同样必须可用。"""
    dates = pd.date_range("2021-03-31", periods=24, freq="QE")
    vals = [50 + i * 2 for i in range(24)]
    p = tmp_path / "quarterly.csv"
    pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "value": vals}).to_csv(
        p, index=False, encoding="utf-8-sig")
    r = _call(p, date_col="date", value_col="value", horizon=4)
    rs = r["result"]
    assert rs["n"] == 24 and len(rs["forecast"]) == 4
    assert rs["freq"] in ("QE", "Q") or "Q" in str(rs["freq"])


def test_non_seasonal_not_labelled_sarima(tmp_path):
    """外部评审 M2 盲区：无周期数据拟合后 seasonal_order 全零（seed=42 实测
    PERIOD_EST=6 -> auto_arima 跑 seasonal 但 P=D=Q=0），method 必须为 ARIMA，
    summary 不得出现 "SARIMA……；ARIMA" 自相矛盾。"""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2025-01-01", periods=90).strftime("%Y-%m-%d")
    vals = np.linspace(10, 30, 90) + rng.normal(0, 0.5, 90)   # 纯线性趋势 + 小噪声
    p = tmp_path / "nonseason.csv"
    pd.DataFrame({"date": dates, "value": vals}).to_csv(p, index=False,
                                                        encoding="utf-8-sig")
    r = _call(p, date_col="date", value_col="value", horizon=5)
    rs = r["result"]
    assert rs["model"]["seasonal"] is False                 # 拟合结果确认非季节
    assert rs["model"]["seasonal_order"] is None
    assert rs["method"] == "ARIMA"
    assert "SARIMA" not in r["summary"]
    assert "ARIMA" in r["summary"]


def test_tail_nan_preserved_not_extrapolated(tmp_path):
    """红队复检新发现 2：尾部缺失必须保留（pandas 默认 forward 会用末值常量外推），
    如实报告 tail_nan，且不得把外推值当真实数据参与预测。"""
    dates = pd.date_range("2025-01-01", periods=30).strftime("%Y-%m-%d")
    vals = [float(i) for i in range(27)] + [None, None, None]   # 尾部 3 个缺失
    p = tmp_path / "tailnan.csv"
    pd.DataFrame({"date": dates, "value": vals}).to_csv(p, index=False,
                                                        encoding="utf-8-sig")
    r = _call(p, date_col="date", value_col="value", horizon=3)
    md = r["result"]["metadata"]
    assert md["tail_nan"] == 3                     # 尾部缺失保留，未外推
    assert md["interpolated"] == 0                 # 无中间缺失可插
    assert "两端缺失 3 个未插值" in r["summary"]


def test_duplicate_dates_merged(tmp_path):
    """20 天中 3 天各有 2 个重复行（共 26 行）-> 按天求和聚合为 20 点。"""
    dates = []
    vals = []
    for d in range(20):
        for _rep in range(2 if d in (0, 7, 15) else 1):
            dates.append(f"2025-01-{d + 1:02d}")
            vals.append(float(d + 1))
    p = _csv(tmp_path, dates, vals)
    r = _call(p, date_col="date", value_col="value", horizon=1)
    md = r["result"]["metadata"]
    assert md["merged_duplicates"] == 3                # 26 行 -> 20 天
    assert md["n"] == 20
    assert "按天求和" in r["summary"]


def test_timezone_unified_utc(tmp_path):
    dates = list(pd.date_range("2025-01-01", periods=20, freq="D",
                               tz="Asia/Shanghai"))
    vals = np.arange(20.0)
    p = _csv(tmp_path, dates, vals)
    r = _call(p, date_col="date", value_col="value", horizon=2)
    md = r["result"]["metadata"]
    assert md["utc_note"] == "时区已统一为 UTC"
    assert md["freq"] == "D"                           # tz 转换后频率保留
    assert "UTC" in r["summary"]


def test_invalid_dates_dropped_counted(tmp_path):
    dates = [f"2025-01-{i + 1:02d}" for i in range(30)]
    dates[3] = "2024-02-30"
    dates[17] = "not-a-date"
    vals = list(np.arange(30.0))
    vals[3] = 99.0
    p = _csv(tmp_path, dates, vals)
    r = _call(p, date_col="date", value_col="value", horizon=1)
    md = r["result"]["metadata"]
    assert md["dropped_invalid_dates"] == 2
    assert md["n"] == 30                     # 28 有效 + asfreq 补齐 2 个缺失日期（插值）


def test_constant_series_degenerates(tmp_path):
    dates = pd.date_range("2025-01-01", periods=20, freq="D").strftime("%Y-%m-%d")
    p = _csv(tmp_path, dates, [5.0] * 20)
    r = _call(p, date_col="date", value_col="value", horizon=3)
    rs = r["result"]
    assert all(f["value"] == 5.0 for f in rs["forecast"])
    assert "退化" in r["summary"]


# ---------------- 校验与边界 ----------------

def test_errors(tmp_path):
    dates = pd.date_range("2025-01-01", periods=20).strftime("%Y-%m-%d")
    p = _csv(tmp_path, dates, np.arange(20.0))
    assert "horizon 必须是" in time_series_forecast(str(p), date_col="date",
                                                     value_col="value",
                                                     horizon=0)["message"]
    assert "超过样本量一半" in time_series_forecast(str(p), date_col="date",
                                                     value_col="value",
                                                     horizon=11)["message"]  # 11 > 10
    small = _csv(tmp_path, dates[:10], np.arange(10.0))
    assert "样本过短" in time_series_forecast(str(small), date_col="date",
                                               value_col="value",
                                               horizon=1)["message"]
    assert "缺少必需列" in time_series_forecast(str(SAMPLES / "clean.csv"),
                                                 date_col="nope",
                                                 value_col="score",
                                                 horizon=1)["message"]
    assert "不是数值列" in time_series_forecast(str(SAMPLES / "clean.csv"),
                                                 date_col="date",
                                                 value_col="category",
                                                 horizon=1)["message"]
    assert time_series_forecast(str(SAMPLES / "nope.csv"), date_col="d",
                                value_col="v", horizon=1)["status"] == "error"


def test_json_safe_and_deterministic():
    r1 = _call(SAMPLES / "timeseries.csv", date_col="date", value_col="value", horizon=5)
    json.dumps(r1, allow_nan=False, ensure_ascii=False)
    r2 = time_series_forecast(str(SAMPLES / "timeseries.csv"), date_col="date",
                              value_col="value", horizon=5)
    assert json.dumps(r1["result"], sort_keys=True, ensure_ascii=False) == json.dumps(
        r2["result"], sort_keys=True, ensure_ascii=False)
