# -*- coding: utf-8 -*-
"""tests/test_normality_test.py —— 工具 9 测试（规范 10）。

独立性：skew 用测试内手写 Fisher 修正公式对照（Excel SKEW 同式，可人工复核）；
正态判定用教科书结论数据（正态抽样 p 大 / 指数抽样 p 小且右偏）。
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools.inference_normality_test import normality_test

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
FIX = ROOT / "tests" / "fixtures"


def _call(path, **kw) -> dict:
    r = normality_test(str(path), **kw)
    assert r["status"] == "ok", r.get("message", r)
    return r


def _skew_fisher_hand(xs: list) -> float:
    """测试内手写 Fisher 修正偏度：n/((n-1)(n-2)) * Σ((x-x̄)/s)³（Excel SKEW 同式）。"""
    n = len(xs)
    m = sum(xs) / n
    s = (sum((v - m) ** 2 for v in xs) / (n - 1)) ** 0.5
    return n / ((n - 1) * (n - 2)) * sum(((v - m) / s) ** 3 for v in xs)


# ---------------- 基础与独立对照 ----------------

def test_clean_score_normal():
    r = _call(SAMPLES / "clean.csv", column="score")
    rs = r["result"]
    assert rs["method_used"] == "shapiro" and rs["n"] == 50
    assert rs["normal"] is True                       # 正态抽样 seed 固定
    assert rs["p_value"] > 0.05 and rs["threshold_alpha"] == 0.05
    # 口径一致性：skew 对照手写 Fisher 公式（独立实现）
    x = pd.read_csv(SAMPLES / "clean.csv", encoding="utf-8-sig")["score"].dropna().tolist()
    assert rs["skew"] == pytest.approx(_skew_fisher_hand(x), abs=1e-9)


def test_skew_matches_describe():
    """与 describe_statistics 同一口径（互验一致性）。"""
    from statlab_mcp.tools.data_exploration_describe_statistics import describe_statistics
    d = describe_statistics(str(SAMPLES / "clean.csv"))["result"]["columns"]["score"]
    r = _call(SAMPLES / "clean.csv", column="score")
    assert r["result"]["skew"] == pytest.approx(d["skew"], abs=1e-12)
    assert r["result"]["kurtosis"] == pytest.approx(d["kurtosis"], abs=1e-12)


# ---------------- 偏态数据 ----------------

def test_exponential_skewed_not_normal(tmp_path):
    rng = np.random.default_rng(7)
    p = tmp_path / "exp.csv"
    pd.DataFrame({"x": rng.exponential(scale=2.0, size=200)}).to_csv(
        p, index=False, encoding="utf-8-sig")
    r = _call(p, column="x")
    rs = r["result"]
    assert rs["normal"] is False and rs["p_value"] < 0.05
    assert rs["skew"] > 1.0                        # 指数分布明显右偏（理论 skew=2）


def test_symmetric_data_normal_judged(tmp_path):
    rng = np.random.default_rng(11)
    p = tmp_path / "sym.csv"
    pd.DataFrame({"x": rng.normal(50, 8, 100)}).to_csv(p, index=False, encoding="utf-8-sig")
    assert _call(p, column="x")["result"]["normal"] is True


# ---------------- 方法选择与边界 ----------------

def test_auto_switches_to_dagostino(tmp_path):
    rng = np.random.default_rng(42)
    p = tmp_path / "big.csv"
    pd.DataFrame({"x": rng.normal(0, 1, 6000)}).to_csv(p, index=False, encoding="utf-8-sig")
    r = _call(p, column="x")
    assert r["result"]["method_used"] == "dagostino"
    assert r["result"]["normal"] is True


def test_explicit_shapiro_large_n_errors(tmp_path):
    rng = np.random.default_rng(42)
    p = tmp_path / "big.csv"
    pd.DataFrame({"x": rng.normal(0, 1, 6000)}).to_csv(p, index=False, encoding="utf-8-sig")
    r = normality_test(str(p), column="x", method="shapiro")
    assert r["status"] == "error" and "超出 Shapiro 适用范围" in r["message"]


def test_dagostino_small_n_errors(tmp_path):
    p = tmp_path / "tiny.csv"
    pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, 5.0]}).to_csv(p, index=False, encoding="utf-8-sig")
    r = normality_test(str(p), column="x", method="dagostino")
    assert r["status"] == "error" and "样本量 >=8" in r["message"]


def test_huge_n_errors(tmp_path):
    rng = np.random.default_rng(1)
    p = tmp_path / "huge.csv"
    pd.DataFrame({"x": rng.normal(0, 1, 100001)}).to_csv(p, index=False, encoding="utf-8-sig")
    r = normality_test(str(p), column="x")
    assert r["status"] == "error" and "随机抽样" in r["message"]


def test_small_n_errors():
    r = normality_test(str(FIX / "single_row.csv"), column="x")
    assert r["status"] == "error" and "至少需要 3 个有效值" in r["message"]


def test_constant_col_errors():
    r = normality_test(str(FIX / "constant_col.csv"), column="x")
    assert r["status"] == "error" and "常数列" in r["message"]


def test_bad_inputs():
    assert "method 仅支持" in normality_test(str(SAMPLES / "clean.csv"),
                                             column="score", method="kolmogorov")["message"]
    assert "缺少必需列" in normality_test(str(SAMPLES / "clean.csv"), column="nope")["message"]
    assert "不是数值列" in normality_test(str(SAMPLES / "clean.csv"), column="category")["message"]
    assert normality_test(str(SAMPLES / "nope.csv"), column="x")["status"] == "error"


def test_chinese_columns_and_json_safe():
    r = _call(FIX / "chinese_columns.csv", column="成绩")
    json.dumps(r, allow_nan=False, ensure_ascii=False)


def test_deterministic():
    r1 = _call(SAMPLES / "clean.csv", column="score")
    r2 = normality_test(str(SAMPLES / "clean.csv"), column="score")
    assert json.dumps(r1, sort_keys=True, ensure_ascii=False) == json.dumps(
        r2, sort_keys=True, ensure_ascii=False)