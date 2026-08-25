# -*- coding: utf-8 -*-
"""tests/test_confidence_interval.py —— 工具 10 测试（规范 10）。

独立性：mean_t 用 t 分布临界值手算硬编码（Excel =T.INV.2T 可复算）；
bootstrap_median 断言可复现性 + 区间必含样本中位数 + 种子/次数字段。
"""
import json
import math
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools.inference_confidence_interval import confidence_interval

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
FIX = ROOT / "tests" / "fixtures"


def _call(path, **kw) -> dict:
    r = confidence_interval(str(path), **kw)
    assert r["status"] == "ok", r.get("message", r)
    return r


def _hand_csv(tmp_path, **cols):
    p = tmp_path / "h.csv"
    pd.DataFrame(cols).to_csv(p, index=False, encoding="utf-8-sig")
    return p


# ---------------- mean_t 手算对照 ----------------

def test_mean_t_hand_calculated_95(tmp_path):
    """[1..5] 95%：mean=3, sd=1.5811, t(0.975,4)=2.7764451, se=0.7071068
    margin=1.9632432 -> CI=[1.036757, 4.963243]（Excel T.INV.2T(0.05,4) 可复核）"""
    p = _hand_csv(tmp_path, x=[1, 2, 3, 4, 5])
    r = _call(p, column="x")
    rs = r["result"]
    assert rs["method"] == "mean_t" and rs["n"] == 5
    assert rs["point_estimate"] == pytest.approx(3.0)
    assert rs["std_error"] == pytest.approx(math.sqrt(2.5) / math.sqrt(5))
    se = math.sqrt(2.5) / math.sqrt(5)
    t_crit = 2.7764451051977987                       # scipy t.ppf(0.975, 4) 精确值
    assert rs["margin"] == pytest.approx(t_crit * se)
    assert rs["ci_lower"] == pytest.approx(3 - t_crit * se, abs=1e-9)
    assert rs["ci_upper"] == pytest.approx(3 + t_crit * se, abs=1e-9)
    assert ("95%" in r["summary"]) and ("t 分布" in r["summary"])


def test_mean_t_confidence_90(tmp_path):
    """confidence=0.90 -> t(0.95,4)=2.1318468；区间更窄（使用者可复算 T.INV.2T(0.10,4)）。"""
    p = _hand_csv(tmp_path, x=[1, 2, 3, 4, 5])
    r = _call(p, column="x", confidence=0.90)
    rs = r["result"]
    se = math.sqrt(2.5) / math.sqrt(5)
    t_crit = 2.1318467863266507
    assert rs["ci_lower"] == pytest.approx(3 - t_crit * se, abs=1e-9)
    assert rs["ci_upper"] == pytest.approx(3 + t_crit * se, abs=1e-9)
    assert rs["ci_upper"] - rs["ci_lower"] < 2 * 1.9632432   # 90% 区间比 95% 窄


# ---------------- bootstrap_median ----------------

def test_bootstrap_median_reproducible_and_contains_median(tmp_path):
    p = _hand_csv(tmp_path, x=list(range(1, 12)))      # 1..11，中位数=6
    r1 = _call(p, column="x", method="bootstrap_median")
    r2 = confidence_interval(str(p), column="x", method="bootstrap_median")
    rs = r1["result"]
    assert rs["method"] == "bootstrap_median"
    assert rs["n_bootstrap"] == 1000 and rs["seed"] == 42
    assert rs["point_estimate"] == 6.0 and rs["estimate_type"] == "median"
    assert rs["ci_lower"] <= 6.0 <= rs["ci_upper"]     # 区间必包含样本中位数
    assert rs["ci_lower"] >= 1.0 and rs["ci_upper"] <= 11.0
    # 局部固定 seed：同一进程两次调用结果逐字段一致（比全局 seed 更强）
    assert r1["result"] == r2["result"]


# ---------------- 边界 ----------------

def test_constant_column_degrades_to_point():
    r = _call(FIX / "constant_col.csv", column="x")
    rs = r["result"]
    assert rs["ci_lower"] == pytest.approx(1.0) and rs["ci_upper"] == pytest.approx(1.0)
    assert rs["margin"] == pytest.approx(0.0)
    assert "常数列" in r["summary"]


def test_errors():
    assert "至少需要 3 个有效值" in confidence_interval(
        str(FIX / "single_row.csv"), column="x")["message"]
    assert "confidence 必须在" in confidence_interval(
        str(SAMPLES / "clean.csv"), column="score", confidence=1.0)["message"]
    assert "confidence 必须在" in confidence_interval(
        str(SAMPLES / "clean.csv"), column="score", confidence=0.0)["message"]
    assert "method 仅支持" in confidence_interval(
        str(SAMPLES / "clean.csv"), column="score", method="bayes")["message"]
    assert "缺少必需列" in confidence_interval(
        str(SAMPLES / "clean.csv"), column="nope")["message"]
    assert "不是数值列" in confidence_interval(
        str(SAMPLES / "clean.csv"), column="category")["message"]
    assert confidence_interval(str(SAMPLES / "nope.csv"), column="x")["status"] == "error"


def test_clean_income_ok_and_json_safe():
    r = _call(SAMPLES / "clean.csv", column="income")
    json.dumps(r, allow_nan=False, ensure_ascii=False)
    assert r["result"]["n"] == 50
    assert r["result"]["ci_lower"] < r["result"]["ci_upper"]


def test_chinese_columns_ok():
    r = _call(FIX / "chinese_columns.csv", column="成绩")
    assert r["status"] == "ok"


def test_deterministic_mean_t():
    r1 = _call(SAMPLES / "clean.csv", column="income")
    r2 = confidence_interval(str(SAMPLES / "clean.csv"), column="income")
    assert json.dumps(r1, sort_keys=True, ensure_ascii=False) == json.dumps(
        r2, sort_keys=True, ensure_ascii=False)