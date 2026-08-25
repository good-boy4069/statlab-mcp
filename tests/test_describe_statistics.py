"""tests/test_describe_statistics.py —— 工具 1 测试（规范 10）。

独立性（红队裁决 13，三级策略）：
- mean/median/std 对照标准库 statistics（独立于 pandas/numpy 实现）；
- q1/q3 用手算推导的期望值硬编码（最强对照，附推导注释）；
- 全列统一 json.dumps(allow_nan=False) 强断言（红队裁决 2）。
"""
import json
import statistics
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools.data_exploration_describe_statistics import describe_statistics

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
FIX = ROOT / "tests" / "fixtures"


def _call(path: Path) -> dict:
    r = describe_statistics(str(path))
    assert r["status"] == "ok", r.get("message", r)
    return r


# ---------------- 独立第三方对照 ----------------

def test_mean_median_std_vs_statistics():
    """score 列的 mean/median/std 对照标准库 statistics（ddof=1）。"""
    df = pd.read_csv(SAMPLES / "clean.csv", encoding="utf-8-sig")
    x = df["score"].dropna()
    r = _call(SAMPLES / "clean.csv")
    col = r["result"]["columns"]["score"]
    assert col["n"] == len(x) == 50
    assert col["mean"] == pytest.approx(statistics.mean(x))
    assert col["median"] == pytest.approx(statistics.median(x))
    assert col["std"] == pytest.approx(statistics.stdev(x))     # 标准库 stdev 即 ddof=1


def test_q1_q3_hand_calculated():
    """q1/q3 linear 插值手算硬编码：数据 [2,4,4,4,5,5,7,9]。
    推导：(n-1)*p 位置线性插值。
      q1: (8-1)*0.25=1.75 -> x[1]+0.75*(x[2]-x[1]) = 4+0.75*0 = 4.0
      q3: (8-1)*0.75=5.25 -> x[5]+0.25*(x[6]-x[5]) = 5+0.25*2 = 5.5
    Excel 复核：=QUARTILE.INC(A1:A8,1)=4，=QUARTILE.INC(A1:A8,3)=5.5
    """
    df = pd.DataFrame({"v": [2, 4, 4, 4, 5, 5, 7, 9]})
    p = FIX / "_q_hand.csv"
    df.to_csv(p, index=False, encoding="utf-8-sig")
    try:
        r = _call(p)
        col = r["result"]["columns"]["v"]
        assert col["q1"] == pytest.approx(4.0)
        assert col["q3"] == pytest.approx(5.5)
        assert col["min"] == pytest.approx(2.0) and col["max"] == pytest.approx(9.0)
        assert col["mean"] == pytest.approx(statistics.mean([2, 4, 4, 4, 5, 5, 7, 9]))
        assert col["std"] == pytest.approx(statistics.stdev([2, 4, 4, 4, 5, 5, 7, 9]))
    finally:
        p.unlink(missing_ok=True)


# ---------------- 原生类型与 JSON 强断言 ----------------

def test_all_stats_native_types_and_json_safe():
    """规范 7.2：全部统计量为 Python 原生类型；无一 NaN/Infinity 字面量。"""
    r = _call(SAMPLES / "clean.csv")
    json.dumps(r, allow_nan=False)                     # 强断言
    for col in r["result"]["columns"].values():
        for k, v in col.items():
            assert isinstance(v, (int, float, str, bool, type(None))), (k, type(v))
    assert all(type(d["n"]) is int and type(d["n_missing"]) is int
               for d in r["result"]["columns"].values())
    assert all(type(d["mean"]) is float for d in r["result"]["columns"].values())


# ---------------- dirty.csv 边界 ----------------

def test_dirty_full_missing_column_semantics():
    """全缺失列：n=0、n_missing=总行数、其余键全 None；不中断整表（使用者裁决）。"""
    r = _call(SAMPLES / "dirty.csv")
    res = r["result"]
    assert "empty_col" in res["fully_missing_columns"]
    d = res["columns"]["empty_col"]
    assert d["n"] == 0 and d["n_missing"] == 20
    for k in ["mean", "median", "std", "min", "q1", "q3", "max", "skew", "kurtosis"]:
        assert d[k] is None, k
    # 其他列不受影响
    assert res["columns"]["value"]["n"] == 19     # row0 空单元格
    assert res["columns"]["value"]["n_missing"] == 1
    assert res["columns"]["extreme"]["max"] == 1e9     # 极端值照常统计


def test_dirty_non_numeric_listed():
    r = _call(SAMPLES / "dirty.csv")
    nn = r["result"]["non_numeric_columns"]
    assert "name" in nn and "bad_date" in nn


# ---------------- 边界行为表 ----------------

def test_no_numeric_column_errors(tmp_path):
    p = tmp_path / "text_only.csv"
    pd.DataFrame({"备注": ["甲", "乙", "丙"]}).to_csv(p, index=False, encoding="utf-8-sig")
    r = describe_statistics(str(p))
    assert r["status"] == "error"
    assert "未找到数值列" in r["message"]
    assert "result" not in r


def test_constant_column_skew_kurt_none():
    r = _call(FIX / "constant_col.csv")
    d = r["result"]["columns"]["x"]
    assert d["std"] == 0.0
    assert d["skew"] is None and d["kurtosis"] is None
    assert d["mean"] == 1.0


def test_single_row_min_stats_none():
    r = _call(FIX / "single_row.csv")
    d = r["result"]["columns"]["x"]
    assert d["n"] == 1 and d["mean"] == 1.0 and d["min"] == 1.0 and d["max"] == 1.0
    for k in ["std", "q1", "q3", "skew", "kurtosis"]:
        assert d[k] is None, k


def test_duplicate_columns_survive():
    """重复列名：pandas 自动改名（a -> a, a.1），工具不崩溃。"""
    r = _call(FIX / "dup_columns.csv")
    assert len(r["result"]["columns"]) == 3      # a, a.1, b


def test_chinese_columns_ok():
    r = _call(FIX / "chinese_columns.csv")
    assert "成绩" in r["result"]["columns"]
    assert "姓名" in r["result"]["non_numeric_columns"]


def test_empty_file_error():
    r = describe_statistics(str(FIX / "empty.csv"))
    assert r["status"] == "error" and "空或无可读数据" in r["message"]


def test_not_exist_error():
    r = describe_statistics(str(SAMPLES / "nope.csv"))
    assert r["status"] == "error" and "文件不存在" in r["message"]


def test_summary_is_generated_text():
    r = _call(SAMPLES / "clean.csv")
    assert isinstance(r["summary"], str) and len(r["summary"]) > 10
    assert "数值列" in r["summary"] and "共 50 行" in r["summary"]


# ---------------- 可复现性 ----------------

def test_deterministic_identical_output():
    """同一输入两次运行结果必须一致（规范 4）。"""
    r1 = describe_statistics(str(SAMPLES / "clean.csv"))
    r2 = describe_statistics(str(SAMPLES / "clean.csv"))
    assert json.dumps(r1, sort_keys=True, ensure_ascii=False) == json.dumps(
        r2, sort_keys=True, ensure_ascii=False)
