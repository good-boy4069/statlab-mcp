"""tests/test_outlier_detect.py —— 工具 5 测试（规范 10）。

独立性：IQR 边界手算硬编码（Excel 可复核：=QUARTILE.INC）；
图断言：__image__ 顶层字段为绝对路径、PNG 后缀、文件真实存在。
"""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools.data_exploration_outlier_detect import outlier_detect

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
FIX = ROOT / "tests" / "fixtures"


def _call(path, **kw) -> dict:
    r = outlier_detect(str(path), **kw)
    assert r["status"] == "ok", r.get("message", r)
    return r


# ---------------- 手算独立对照 ----------------

def test_hand_calculated_iqr_bounds(tmp_path):
    """数据 [1,2,3,4,5,100]：Q1=2、Q3=5、IQR=3 → bounds [-2.5, 9.5] → 100 是唯一异常。
    推导：(n-1)*0.25=1.25 -> x[1]+0.25*(x[2]-x[1]) = 2.25? 注意 linear 插值:
    (6-1)*0.25=1.25 -> 排序 x=[1,2,3,4,5,100] -> x[1]=2, x[2]=3 -> 2+0.25*1=2.25
    (6-1)*0.75=3.75 -> x[3]=4 +0.75*(x[4]-x[3])=4+0.75*1=4.75
    IQR=2.5 -> lower=2.25-3.75=-1.5, upper=4.75+3.75=8.5
    Excel 复核：QUARTILE.INC(...,1)=2.25、QUARTILE.INC(...,3)=4.75
    """
    p = tmp_path / "out_hand.csv"
    pd.DataFrame({"v": [1, 2, 3, 4, 5, 100]}).to_csv(p, index=False, encoding="utf-8-sig")
    r = _call(p)
    d = r["result"]["columns"]["v"]
    assert d["lower_bound"] == pytest.approx(-1.5)
    assert d["upper_bound"] == pytest.approx(8.5)
    assert d["n_outliers"] == 1
    assert d["outlier_indices"] == [5]           # 0 基行号
    assert d["outlier_values"] == [100.0]


# ---------------- dirty.csv：1e9 极端值 ----------------

def test_dirty_extreme_detected():
    r = _call(SAMPLES / "dirty.csv")
    d = r["result"]["columns"]["extreme"]
    assert d["n_outliers"] == 1
    assert d["outlier_values"] == [1000000000.0]     # 1e9
    assert d["outlier_indices"] == [5]               # 生成脚本 loc[5]
    assert d["upper_bound"] < 1e9
    assert r["result"]["columns"]["value"]["n_outliers"] == 0
    assert r["result"]["n_outliers_total"] == 1


def test_dirty_skipped_columns():
    r = _call(SAMPLES / "dirty.csv")
    assert set(r["result"]["skipped_columns"]) == {"name", "bad_date"}
    assert "empty_col" in r["result"]["columns"]     # 全缺失数值列 n=0 -> bounds null


# ---------------- 图协议（附录 D） ----------------

def test_image_field_top_level_and_exists():
    r = _call(SAMPLES / "dirty.csv")
    assert "status" in r and "__image__" in r        # 顶层字段，与 result 平级
    assert "result" not in r["__image__"]            # 不会误放
    p = Path(r["__image__"])
    assert p.is_absolute() and p.suffix == ".png"
    assert p.name.startswith("outlier_detect_all_")
    assert p.exists() and p.stat().st_size > 0
    assert "reports" in p.parts and "plots" in p.parts


def test_no_outliers_still_plots():
    r = _call(FIX / "tiny_numeric.csv")                    # [1,2,3,4] 系：bounds 内无异常
    assert r["result"]["n_outliers_total"] == 0
    assert "未发现异常值" in r["summary"]
    assert Path(r["__image__"]).exists()


def test_clean_income_one_tail_outlier():
    """clean.csv 正态抽样尾部应有 ~1 个 IQR 异常（seed 固定；实测 income 13827.72>上界）。"""
    r = _call(SAMPLES / "clean.csv")
    d = r["result"]["columns"]["income"]
    assert d["n_outliers"] >= 1
    assert d["outlier_values"][0] > d["upper_bound"]


# ---------------- 边界 ----------------

def test_small_n_bounds_null():
    r = _call(FIX / "single_row.csv")
    d = r["result"]["columns"]["x"]
    assert d["n_outliers"] == 0
    assert d["lower_bound"] is None and d["upper_bound"] is None


def test_constant_column_no_outliers():
    r = _call(FIX / "constant_col.csv")
    d = r["result"]["columns"]["x"]                  # 全 1.0：bounds 相等，无异常
    assert d["n_outliers"] == 0
    assert d["lower_bound"] == pytest.approx(1.0)


def test_method_validation_cn():
    r = outlier_detect(str(SAMPLES / "clean.csv"), method="zscore")
    assert r["status"] == "error" and "method 仅支持 iqr" in r["message"]


def test_no_numeric_column_errors(tmp_path):
    p = tmp_path / "txt.csv"
    pd.DataFrame({"c": ["甲", "乙", "丙"]}).to_csv(p, index=False, encoding="utf-8-sig")
    r = outlier_detect(str(p))
    assert r["status"] == "error" and "至少需要 1 个数值列" in r["message"]


def test_basic_errors_and_chinese_cols():
    assert outlier_detect(str(SAMPLES / "nope.csv"))["status"] == "error"
    r = _call(FIX / "chinese_columns.csv")           # 中文列名正常
    assert "成绩" in r["result"]["columns"]


def test_json_safe_and_result_deterministic():
    """两次运行 result 部分一致（__image__ 带时间戳命名，只比较 result）。"""
    r1 = _call(SAMPLES / "dirty.csv")
    json.dumps(r1, allow_nan=False, ensure_ascii=False)   # 无 NaN/Infinity
    r2 = outlier_detect(str(SAMPLES / "dirty.csv"))
    assert json.dumps(r1["result"], sort_keys=True, ensure_ascii=False) == json.dumps(
        r2["result"], sort_keys=True, ensure_ascii=False)
