"""tests/test_anova_test.py —— 工具 7 测试（规范 10）。

独立性：F 值用方差分析公式手算硬编码（MSTr/MSE，Excel 数据分析工具可复核）；
Tukey 事后差值手算对照。
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools.inference_anova_test import anova_test

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


def _call(p, **kw) -> dict:
    r = anova_test(str(p), **kw)
    assert r["status"] == "ok", r.get("message", r)
    return r


def _csv(tmp_path, group_col, value_col, g_list, v_list):
    p = tmp_path / "a.csv"
    pd.DataFrame({group_col: g_list, value_col: v_list}).to_csv(
        p, index=False, encoding="utf-8-sig")
    return p


# ---------------- F 值手算对照 ----------------

def test_f_hand_calculated(tmp_path):
    """组 [1,2,3],[2,3,4],[5,6,7]：
    组均值 2/3/6，总均值 11/3；
    SSB=3*(2-11/3)^2+3*(3-11/3)^2+3*(6-11/3)^2 = 26
    SSW=各组内平方和 2+2+2=6
    F=(SSB/(k-1))/(SSW/(N-k))=(26/2)/(6/6)=13；df=(2,6)
    Excel 复核：单因素方差分析输出 F=13"""
    p = _csv(tmp_path, "g", "v", ["A"] * 3 + ["B"] * 3 + ["C"] * 3,
             [1, 2, 3, 2, 3, 4, 5, 6, 7])
    r = _call(p, group_col="g", value_col="v")
    rs = r["result"]
    assert rs["method"] == "anova"
    assert rs["statistic"] == pytest.approx(13.0)
    assert (rs["df_between"], rs["df_within"]) == (2, 6)
    assert rs["levene"]["equal_variance"] is True
    assert rs["p_value"] < 0.05
    assert "拒绝 H0" in rs["conclusion"]


def test_tukey_pair_diffs_hand(tmp_path):
    """Tukey 事后差值 = 组均值差：A-C = 2-6 = -4；B-C = 3-6 = -3。"""
    p = _csv(tmp_path, "g", "v", ["A"] * 3 + ["B"] * 3 + ["C"] * 3,
             [1, 2, 3, 2, 3, 4, 5, 6, 7])
    rs = _call(p, group_col="g", value_col="v")["result"]
    pairs = {x["pair"]: x for x in rs["posthoc"]["pairs"]}
    assert pairs["A-C"]["diff"] == pytest.approx(-4.0)
    assert pairs["B-C"]["diff"] == pytest.approx(-3.0)
    assert pairs["A-C"]["significant"] is True
    assert rs["posthoc"]["method"] == "tukey_hsd"
    assert "按族校正" in rs["posthoc"]["correction"]


# ---------------- 方差不齐 -> Welch + Games-Howell ----------------

def test_unequal_variance_welch_gh(tmp_path):
    rng = np.random.default_rng(5)
    vals = np.concatenate([rng.normal(0, 1, 20), rng.normal(0.5, 1, 20),
                           rng.normal(3, 6, 20)])
    p = _csv(tmp_path, "g", "v", ["A"] * 20 + ["B"] * 20 + ["C"] * 20, vals)
    rs = _call(p, group_col="g", value_col="v")["result"]
    assert rs["method"] == "welch_anova"
    assert rs["levene"]["equal_variance"] is False
    assert rs["posthoc"]["method"] == "games_howell"
    assert rs["posthoc"]["pairs"][0]["p_value"] is None    # 诚实省略（设计文档）
    assert "Games-Howell" in rs["posthoc"]["correction"]
    assert rs["df_within"] > 0


# ---------------- 错误与边界 ----------------

def test_errors(tmp_path):
    p1 = _csv(tmp_path, "g", "v", ["A"] * 3, [1, 2, 3])
    assert "分组至少需要 2 组" in anova_test(str(p1), group_col="g", value_col="v")["message"]
    p2 = _csv(tmp_path, "g", "v", ["A", "A", "B"], [1.0, 2.0, 3.0])
    assert "样本量不足 2" in anova_test(str(p2), group_col="g", value_col="v")["message"]
    assert "缺少必需列" in anova_test(str(SAMPLES / "clean.csv"),
                                      group_col="category", value_col="nope")["message"]
    assert "不是数值列" in anova_test(str(SAMPLES / "clean.csv"),
                                      group_col="category", value_col="category")["message"]
    assert "alpha 必须在" in anova_test(str(SAMPLES / "clean.csv"),
                                        group_col="category", value_col="score",
                                        alpha=2.0)["message"]
    # 组数 >20
    g = [f"G{i}" for i in range(21) for _ in range(3)]
    v = [float(i) for i in range(63)]
    p3 = _csv(tmp_path, "g", "v", g, v)
    assert "组数超过 20" in anova_test(str(p3), group_col="g", value_col="v")["message"]
    assert anova_test(str(SAMPLES / "nope.csv"), group_col="g", value_col="v")["status"] == "error"


def test_clean_regression():
    """seed 固定回归基准：F≈6.04、p≈0.0046、显著对 B-C 与 A-C。"""
    rs = _call(SAMPLES / "clean.csv", group_col="category", value_col="score")["result"]
    assert rs["statistic"] == pytest.approx(6.0403, abs=1e-3)
    assert 0.004 < rs["p_value"] < 0.006
    sig = {x["pair"] for x in rs["posthoc"]["pairs"] if x["significant"]}
    assert "B-C" in sig and "A-C" in sig


def test_chinese_group_names(tmp_path):
    p = _csv(tmp_path, "分组", "成绩", ["甲"] * 3 + ["乙"] * 3 + ["丙"] * 3,
             [1, 2, 3, 4, 5, 6, 7, 8, 9])
    r = _call(p, group_col="分组", value_col="成绩")
    assert "甲" in r["result"]["groups"] and "甲-丙" in [x["pair"] for x in r["result"]["posthoc"]["pairs"]]


def test_json_safe_and_deterministic():
    r1 = _call(SAMPLES / "clean.csv", group_col="category", value_col="score")
    json.dumps(r1, allow_nan=False, ensure_ascii=False)
    r2 = anova_test(str(SAMPLES / "clean.csv"), group_col="category", value_col="score")
    assert json.dumps(r1, sort_keys=True, ensure_ascii=False) == json.dumps(
        r2, sort_keys=True, ensure_ascii=False)
