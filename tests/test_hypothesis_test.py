"""tests/test_hypothesis_test.py —— 工具 6 测试（规范 10）。

独立性：t/df/均值差/CI/效应量全部用**手算公式硬编码期望值**（不引用 scipy 结果，
Excel 可复核：T.DIST.2T / T.INV.2T / STDEV.S）；r=0 对称数据 p=1.0 精确断言。
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools.inference_hypothesis_test import hypothesis_test

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
FIX = ROOT / "tests" / "fixtures"


def _two_group_csv(tmp_path, x=(1, 2, 3, 4, 5), y=(2, 4, 6, 8, 10)):
    p = tmp_path / "two.csv"
    pd.DataFrame({"g": ["A"] * len(x) + ["B"] * len(y), "v": list(x) + list(y)}).to_csv(
        p, index=False, encoding="utf-8-sig")
    return p


def _hand_csv(tmp_path, **cols):
    p = tmp_path / "h.csv"
    pd.DataFrame(cols).to_csv(p, index=False, encoding="utf-8-sig")
    return p


# ---------------- one_sample 手算对照 ----------------

def test_one_sample_hand_calculated(tmp_path):
    """[1,2,3,4,5] mu0=4：mean=3, sd=1.5811(STDEV.S), t=(3-4)/(sd/√5)=-1.4142,
    df=4, mean_diff=-1, se=0.7071, d=0.6325；
    CI: 3±T.INV.2T(0.05,4)*se, T.INV.2T=2.776445 -> [1.03693, 4.96307]"""
    p = _hand_csv(tmp_path, x=[1, 2, 3, 4, 5])
    r = hypothesis_test(str(p), column="x", test="one_sample", mu0=4.0)
    assert r["status"] == "ok", r.get("message")
    rs = r["result"]
    assert rs["method"] == "one_sample_t"
    assert rs["statistic"] == pytest.approx(-math.sqrt(2))          # -1.41421356
    assert rs["df"] == pytest.approx(4.0)
    assert rs["mean"] == pytest.approx(3.0)
    assert rs["mean_diff"] == pytest.approx(-1.0)
    assert rs["effect_size"] == pytest.approx(1.0 / math.sqrt(2.5))
    assert rs["ci_lower"] == pytest.approx(-2.96324316, abs=1e-5)  # mean_diff=-1 ± 2.7764451*0.7071068
    assert rs["ci_upper"] == pytest.approx(0.96324316, abs=1e-5)   # （文档口径：与 mean_diff 同口径）
    assert 0.22 < rs["p_value"] < 0.24                            # 手算 Excel T.DIST.2T≈0.2302
    assert "不能拒绝 H0" in rs["conclusion"]


def test_one_sample_mu0_equal_mean_p_exact(tmp_path):
    """对称数据均值=假设值 -> t=0、p=1.0（精确断言，无需库对照）。"""
    p = _hand_csv(tmp_path, x=[1, 2, 3, 4, 5])
    r = hypothesis_test(str(p), column="x", test="one_sample", mu0=3.0)
    rs = r["result"]
    assert rs["statistic"] == pytest.approx(0.0, abs=1e-12)
    assert rs["p_value"] == 1.0


# ---------------- independent（Welch）手算对照 ----------------

def test_welch_hand_calculated(tmp_path):
    """x=[1..5], y=[2,4,6,8,10]：s1²=2.5, s2²=10, a=0.5, b=2
    t=(3-6)/√2.5=-1.8973666；df=(2.5)²/(0.25/4+4/4)=6.25/1.0625=5.8823529
    pooled=√(6.25)=2.5 -> d=|−3|/2.5=1.2"""
    p = _two_group_csv(tmp_path)
    r = hypothesis_test(str(p), column="v", test="independent", group_col="g")
    assert r["status"] == "ok", r.get("message")
    rs = r["result"]
    assert rs["method"] == "welch_t"
    assert rs["statistic"] == pytest.approx(-1.897366596, abs=1e-9)
    assert rs["df"] == pytest.approx(6.25 / 1.0625, abs=1e-9)
    assert rs["mean1"] == pytest.approx(3.0) and rs["mean2"] == pytest.approx(6.0)
    assert rs["mean_diff"] == pytest.approx(-3.0)
    assert rs["effect_size"] == pytest.approx(1.2)
    assert rs["n1"] == 5 and rs["n2"] == 5 and rs["n"] == 10
    assert rs["p_value"] > 0.05                       # 手算 Excel T.DIST.2T≈0.1075


# ---------------- paired 手算对照 ----------------

def test_paired_hand_calculated(tmp_path):
    """x=[1..5], y=[2,4,5,4,5] -> diff=[-1,-2,-2,0,0]：mean=-1, sd=1(ddof=1)
    t=-1/(1/√5)=-2.23606798；df=4；d=1.0"""
    p = _hand_csv(tmp_path, x=[1, 2, 3, 4, 5], y=[2, 4, 5, 4, 5])
    r = hypothesis_test(str(p), column="x", test="paired", sample2_col="y")
    assert r["status"] == "ok", r.get("message")
    rs = r["result"]
    assert rs["method"] == "paired_t"
    assert rs["statistic"] == pytest.approx(-math.sqrt(5), abs=1e-12)
    assert rs["df"] == pytest.approx(4.0)
    assert rs["mean_diff"] == pytest.approx(-1.0)
    assert rs["effect_size"] == pytest.approx(1.0)


# ---------------- alternative 关系 ----------------

def test_alternative_p_relationship(tmp_path):
    p = _hand_csv(tmp_path, x=[1, 2, 3, 4, 5])
    r2 = hypothesis_test(str(p), column="x", test="one_sample", mu0=4.0)["result"]
    rl = hypothesis_test(str(p), column="x", test="one_sample", mu0=4.0,
                         alternative="less")["result"]
    rg = hypothesis_test(str(p), column="x", test="one_sample", mu0=4.0,
                         alternative="greater")["result"]
    assert r2["p_value"] == pytest.approx(2 * min(rl["p_value"], rg["p_value"]))
    assert rl["p_value"] + rg["p_value"] == pytest.approx(1.0)   # 单侧互补


# ---------------- 错误路径 ----------------

def test_errors(tmp_path):
    assert "test 仅支持" in hypothesis_test(str(SAMPLES / "clean.csv"), column="score",
                                            test="anova")["message"]
    assert "alternative 仅支持" in hypothesis_test(str(SAMPLES / "clean.csv"), column="score",
                                                    alternative="one_side")["message"]
    assert "alpha 必须在" in hypothesis_test(str(SAMPLES / "clean.csv"), column="score",
                                              alpha=1.5)["message"]
    assert "缺少必需列" in hypothesis_test(str(SAMPLES / "clean.csv"), column="nope")["message"]
    assert "不是数值列" in hypothesis_test(str(SAMPLES / "clean.csv"), column="category")["message"]
    assert "group_col" in hypothesis_test(str(SAMPLES / "clean.csv"), column="score",
                                          test="independent")["message"]
    assert "sample2_col" in hypothesis_test(str(SAMPLES / "clean.csv"), column="score",
                                            test="paired")["message"]
    # 3 组 -> 引导 anova_test
    assert "anova_test" in hypothesis_test(str(SAMPLES / "clean.csv"), column="score",
                                           test="independent", group_col="category")["message"]
    # 配对所有差值相同 -> 拒绝（tmp_path，避免污染仓库 fixtures）
    p = tmp_path / "same.csv"
    pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [5.0, 6.0, 7.0]}).to_csv(
        p, index=False, encoding="utf-8-sig")
    r = hypothesis_test(str(p), column="a", test="paired", sample2_col="b")
    assert r["status"] == "error" and "无变异" in r["message"]
    assert hypothesis_test(str(SAMPLES / "nope.csv"), column="x")["status"] == "error"


def test_single_value_errors(tmp_path):
    p = _hand_csv(tmp_path, x=[1.0])
    r = hypothesis_test(str(p), column="x")
    assert r["status"] == "error" and "至少需要 2 个有效值" in r["message"]


# ---------------- 样本数据与边界 ----------------

def test_clean_score_mu70_ok():
    r = hypothesis_test(str(SAMPLES / "clean.csv"), column="score", test="one_sample", mu0=70.0)
    assert r["status"] == "ok"
    assert r["result"]["n"] == 50
    assert 0.5 < r["result"]["p_value"] < 0.7        # 回归基准（seed 固定）
    assert r["result"]["normality_shapiro"]["data"]["normal"] is True


def test_shapiro_skipped_when_large_n(tmp_path):
    rng = np.random.default_rng(42)
    p = tmp_path / "big.csv"
    pd.DataFrame({"x": rng.normal(0, 1, 6000)}).to_csv(p, index=False, encoding="utf-8-sig")
    r = hypothesis_test(str(p), column="x")
    d = r["result"]["normality_shapiro"]["data"]
    assert d["statistic"] is None and "自动跳过" in d["note"]


def test_skewed_data_warns(tmp_path):
    rng = np.random.default_rng(7)
    p = tmp_path / "skew.csv"
    pd.DataFrame({"x": rng.exponential(scale=2.0, size=80)}).to_csv(
        p, index=False, encoding="utf-8-sig")
    r = hypothesis_test(str(p), column="x", mu0=2.0)
    assert r["result"]["normality_warning"] is not None      # 非正态警示
    assert "Wilcoxon" in r["result"]["normality_warning"]


def test_chinese_columns_and_json_safe():
    r = hypothesis_test(str(FIX / "chinese_columns.csv"), column="成绩")
    assert r["status"] == "ok"
    json.dumps(r, allow_nan=False, ensure_ascii=False)


def test_deterministic():
    r1 = hypothesis_test(str(SAMPLES / "clean.csv"), column="score", mu0=70.0)
    r2 = hypothesis_test(str(SAMPLES / "clean.csv"), column="score", mu0=70.0)
    assert json.dumps(r1, sort_keys=True, ensure_ascii=False) == json.dumps(
        r2, sort_keys=True, ensure_ascii=False)
