# -*- coding: utf-8 -*-
"""tests/test_plot_forecast.py —— 工具 24 测试。
独立性：与工具 17 共用 _prepare_series（插值 3 核数）；仅作图不预测断言。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools.visualization_plot_forecast import plot_forecast

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


def test_timeseries_plot():
    r = plot_forecast(str(SAMPLES / "timeseries.csv"), date_col="date",
                      value_col="value")
    assert r["status"] == "ok", r.get("message")
    rs = r["result"]
    assert rs["n"] == 120
    assert rs["metadata"]["interpolated"] == 3
    assert rs["series_min"] < rs["series_max"]
    assert "已插值 3 个缺失点" in r["summary"]
    assert "均线" in r["summary"]                    # 7 日均线
    assert "预测" not in r["summary"]                # 仅作图不预测
    img = Path(r["__image__"])
    assert img.suffix == ".png" and img.exists()


def test_errors(tmp_path):
    import pandas as pd
    p = tmp_path / "s.csv"
    pd.DataFrame({"date": ["2025-01-01", "2025-01-02", "2025-01-03"],
                  "value": [1.0, 2.0, 3.0]}).to_csv(p, index=False,
                                                     encoding="utf-8-sig")
    r = plot_forecast(str(p), date_col="date", value_col="value")
    assert r["status"] == "error" and "样本过短" in r["message"]
    assert plot_forecast(str(SAMPLES / "nope.csv"), date_col="d",
                         value_col="v")["status"] == "error"


def test_json_safe():
    r = plot_forecast(str(SAMPLES / "timeseries.csv"), date_col="date",
                      value_col="value")
    json.dumps(r, allow_nan=False, ensure_ascii=False)