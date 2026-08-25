# -*- coding: utf-8 -*-
"""tests/test_data_type_check.py —— 工具 2 测试（规范 10）。

独立性：类型判定为确定性规则，期望值来自 pandas 官方语义与人工检查表
（每条用例的期望类型在 fixtures 生成脚本中可人工复核）。
"""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools.data_exploration_data_type_check import data_type_check

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
FIX = ROOT / "tests" / "fixtures"


def _call(path: Path) -> dict:
    r = data_type_check(str(path))
    assert r["status"] == "ok", r.get("message", r)
    return r


# ---------------- clean.csv 期望类型表（人工复核） ----------------

def test_clean_types_expected():
    """clean.csv：id/age=integer，score/income=numeric，category=category，date=date。"""
    r = _call(SAMPLES / "clean.csv")
    cols = r["result"]["columns"]
    assert cols["id"]["detected_type"] == "integer"
    assert cols["age"]["detected_type"] == "integer"
    assert cols["score"]["detected_type"] == "numeric"
    assert cols["income"]["detected_type"] == "numeric"
    assert cols["category"]["detected_type"] == "category"
    assert cols["date"]["detected_type"] == "date"
    assert [c for c in cols.values() if c["detected_type"] == "missing"] == []


# ---------------- dirty.csv 边界 ----------------

def test_dirty_types_and_invalid_date():
    """dirty.csv：value/extreme=numeric，empty_col=missing，bad_date=date+非法日期，name=text。"""
    r = _call(SAMPLES / "dirty.csv")
    cols = r["result"]["columns"]
    assert cols["value"]["detected_type"] == "numeric"
    assert cols["value"]["n_valid"] == 19 and cols["value"]["n_missing"] == 1
    assert cols["empty_col"]["detected_type"] == "missing"
    assert cols["empty_col"]["n_missing"] == 20
    assert cols["bad_date"]["detected_type"] == "date"
    assert cols["bad_date"]["dirty_count"] == 1
    assert "2024-02-30" in cols["bad_date"]["note"]      # 非法日期示例进 note
    assert cols["extreme"]["detected_type"] == "numeric"
    assert cols["name"]["detected_type"] == "text"
    iss = r["result"]["issue_summary"]
    assert iss["fully_missing_columns"] == ["empty_col"]
    assert iss["invalid_date_columns"] == ["bad_date"]


# ---------------- 判定顺序：数值先于日期（实现期修订） ----------------

def test_numeric_strings_not_misjudged_as_date(tmp_path):
    """纯数字字符串列 ["123","456","789"] 必须判数值类型（integer），不是 date。"""
    p = tmp_path / "numstr.csv"
    pd.DataFrame({"v": ["123", "456", "789"]}).to_csv(p, index=False, encoding="utf-8-sig")
    r = _call(p)
    assert r["result"]["columns"]["v"]["detected_type"] == "integer"


def test_thousand_separator_mixed(tmp_path):
    """千分位脏值列 ["1000","2,000","3000"] → mixed，dirty_count=1，note 给示例。"""
    p = tmp_path / "mixed.csv"
    pd.DataFrame({"v": ["1000", "2,000", "3000"]}).to_csv(p, index=False, encoding="utf-8-sig")
    r = _call(p)
    col = r["result"]["columns"]["v"]
    assert col["detected_type"] == "mixed"
    assert col["dirty_count"] == 1
    assert "2,000" in col["note"]


# ---------------- 其余边界 ----------------

def test_constant_and_single_row():
    r = _call(FIX / "constant_col.csv")
    assert r["result"]["columns"]["x"]["detected_type"] == "integer"
    assert r["result"]["columns"]["y"]["detected_type"] == "numeric"
    r2 = _call(FIX / "single_row.csv")      # 单行不崩溃
    assert r2["status"] == "ok"


def test_chinese_columns_ok():
    r = _call(FIX / "chinese_columns.csv")
    assert r["result"]["columns"]["成绩"]["detected_type"] == "numeric"
    # 姓名列固定 seed 抽样结果仅 2 个唯一值（王五/李四，张三未中签）<= int(12*0.2)=2 -> category
    col = r["result"]["columns"]["姓名"]
    assert col["detected_type"] == "category"
    assert "取值 top3" in col["note"]


def test_duplicate_columns_survive():
    r = _call(FIX / "dup_columns.csv")
    assert len(r["result"]["columns"]) == 3      # a, a.1, b


def test_text_col_with_suspicious_number(tmp_path):
    """text 列混入 "1,000" 千分位脏值：判 text 但 dirty_count=1 且 note 给示例（用户数据场景）。"""
    p = tmp_path / "note.csv"
    pd.DataFrame({"备注": ["促销", "1,000", "促销", "", "促销"]}).to_csv(
        p, index=False, encoding="utf-8-sig")
    r = _call(p)
    col = r["result"]["columns"]["备注"]
    assert col["detected_type"] == "text"
    assert col["dirty_count"] == 1
    assert "1,000" in col["note"]


def test_errors():
    assert data_type_check(str(SAMPLES / "nope.csv"))["status"] == "error"
    assert data_type_check(str(FIX / "empty.csv"))["status"] == "error"
    r = data_type_check(str(FIX / "header_only.csv"))     # 仅表头 -> 无数据行
    assert r["status"] == "error"


def test_summary_mentions_counts():
    r = _call(SAMPLES / "dirty.csv")
    assert isinstance(r["summary"], str)
    assert "共 20 行" in r["summary"] and "全缺失列" in r["summary"]


def test_json_safe_and_deterministic():
    r1 = _call(SAMPLES / "dirty.csv")
    json.dumps(r1, allow_nan=False, ensure_ascii=False)     # 无 NaN/Infinity
    r2 = data_type_check(str(SAMPLES / "dirty.csv"))
    assert json.dumps(r1, sort_keys=True, ensure_ascii=False) == json.dumps(
        r2, sort_keys=True, ensure_ascii=False)