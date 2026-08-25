# -*- coding: utf-8 -*-
"""tests/test_missing_report.py —— 工具 3 测试（规范 10）。

独立性：总缺失/缺失率期望值来自 fixtures 生成脚本的人工检查表
（samples/make_sample_data.py 中缺失位置固定且可人工核数）。
"""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools.data_exploration_missing_report import missing_report

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
FIX = ROOT / "tests" / "fixtures"


def _call(path: Path) -> dict:
    r = missing_report(str(path))
    assert r["status"] == "ok", r.get("message", r)
    return r


# ---------------- dirty.csv：人工核数（make_sample_data 固定位置） ----------------

def test_dirty_totals_hand_counted():
    """dirty.csv 手工核数：value=1(row0)、name=1(row1 空串)、empty_col=20、extreme=1(row2)。
    total = 1+1+20+1 = 23；率 = 23/(20*5) = 0.23；empty_col 导致每行都有缺失 → complete_rows=0。
    """
    r = _call(SAMPLES / "dirty.csv")
    res = r["result"]
    assert res["n_rows"] == 20 and res["n_columns"] == 5
    assert res["total_missing"] == 23
    assert res["overall_missing_rate"] == pytest.approx(0.23)
    assert res["columns"]["value"]["n_missing"] == 1
    assert res["columns"]["value"]["missing_rate"] == pytest.approx(0.05)
    assert res["columns"]["empty_col"]["n_missing"] == 20
    assert res["columns"]["empty_col"]["missing_rate"] == pytest.approx(1.0)
    assert res["complete_rows"] == 0            # 全缺失列使每行都含缺失
    assert res["rows_with_missing"] == 20


def test_dirty_patterns_full_missing_first():
    r = _call(SAMPLES / "dirty.csv")
    pats = r["result"]["patterns"]
    assert pats[0] == {"columns": ["empty_col"], "rows": 20, "note": "全缺失列"}
    pair = [p for p in pats if len(p["columns"]) == 2 and set(p["columns"]) == {"value", "empty_col"}]
    assert pair and pair[0]["rows"] == 1        # row0 同时缺 value 与 empty_col


# ---------------- clean.csv：无缺失 ----------------

def test_clean_no_missing():
    r = _call(SAMPLES / "clean.csv")
    res = r["result"]
    assert res["total_missing"] == 0
    assert res["overall_missing_rate"] == 0.0
    assert res["patterns"] == []
    assert res["complete_rows"] == 50
    assert "无缺失" in r["summary"]


# ---------------- timeseries.csv ----------------

def test_timeseries_missing_3():
    r = _call(SAMPLES / "timeseries.csv")
    res = r["result"]
    assert res["columns"]["value"]["n_missing"] == 3
    assert res["columns"]["value"]["missing_rate"] == pytest.approx(3 / 120)
    assert res["columns"]["date"]["n_missing"] == 0
    assert res["rows_with_missing"] == 3


# ---------------- 其余边界 ----------------

def test_single_row_complete():
    r = _call(FIX / "single_row.csv")
    assert r["result"]["complete_rows"] == 1 and r["result"]["rows_with_missing"] == 0


def test_chinese_columns_ok():
    r = _call(FIX / "chinese_columns.csv")
    assert r["result"]["columns"]["姓名"]["n_missing"] >= 0      # 键原样输出不崩溃


def test_errors():
    assert missing_report(str(SAMPLES / "nope.csv"))["status"] == "error"
    assert missing_report(str(FIX / "empty.csv"))["status"] == "error"


def test_json_safe_and_deterministic():
    r1 = _call(SAMPLES / "dirty.csv")
    json.dumps(r1, allow_nan=False, ensure_ascii=False)
    r2 = missing_report(str(SAMPLES / "dirty.csv"))
    assert json.dumps(r1, sort_keys=True, ensure_ascii=False) == json.dumps(
        r2, sort_keys=True, ensure_ascii=False)