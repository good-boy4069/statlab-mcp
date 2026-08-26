"""tests/test_nonparametric_test.py —— 工具 26 测试（规范 10）。

独立性：全部期望值**手算硬编码**（不引用 scipy 结果做对照，禁循环论证）：
- Wilcoxon：[-1,-2,-2,0,0] 差值 → 剔除 0 差后 n=3，|diff|=[1,2,2] 秩=[1,2.5,2.5]，
  负秩和 W=6、正秩和 0 → scipy 返回较小秩和 W=0；n=3 无 ties 精确分布
  双侧 P(W<=0)=P(W+>=6)=0.125×2=0.25；r = 1−4×0/(3×4)=1，方向 mean(diff)<0 → −1
- Mann-Whitney：[1,2,3] vs [4,5,6,7]：全部 x<y → U=0；exact 双侧 p=2×(1/C(7,3))=2/35≈0.05714
  （scipy method="auto" 对 n1*n2 小且无 ties 用精确分布）；r = 2×0/(3×4)−1 = −1
- Kruskal-Wallis：三组 1..3/4..6/7..9：秩和 R=[6,15,24]，ΣR²/n=36/3+225/3+576/3=279，
  H = 12/(9·10)×279 − 3×10 = 37.2−30 = 7.2；ε² = H/(N−1) = 7.2/8 = 0.9
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools.inference_nonparametric_test import nonparametric_test

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


def _call(p, **kw) -> dict:
    r = nonparametric_test(str(p), **kw)
    assert r["status"] == "ok", r.get("message", r)
    return r


def _csv(tmp_path, df: pd.DataFrame, name="np.csv"):
    p = tmp_path / name
    df.to_csv(p, index=False, encoding="utf-8-sig")
    return p


# ---------------- Wilcoxon 手算对照 ----------------

def test_wilcoxon_hand_calculated(tmp_path):
    """diff=[-1,-2,-2,0,0]：W=0, p=0.25（精确分布）, r=-1（column 全体低于 sample2_col）。"""
    p = _csv(tmp_path, pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": [2, 4, 5, 4, 5]}))
    rs = _call(p, test="wilcoxon", column="a", sample2_col="b")["result"]
    assert rs["method"] == "wilcoxon"
    assert rs["statistic"] == pytest.approx(0.0)
    assert rs["p_value"] == pytest.approx(0.25, abs=1e-9)
    assert rs["effsize"] == pytest.approx(-1.0, abs=1e-9)      # 方向：a 低于 b
    assert rs["n_pairs_used"] == 3                             # 剔除 2 个 0 差
    assert rs["n_dropped_zero_diff"] == 2
    assert "不能拒绝" in rs["conclusion"]                      # p=0.25 >= 0.05


def test_wilcoxon_reverse_direction_positive(tmp_path):
    """反方向数据：a 全体高于 b → effsize 为正。"""
    p = _csv(tmp_path, pd.DataFrame({"a": [5, 6, 7, 8, 9], "b": [1, 2, 3, 4, 5]}))
    rs = _call(p, test="wilcoxon", column="a", sample2_col="b")["result"]
    assert rs["effsize"] == pytest.approx(1.0, abs=1e-9)
    assert rs["statistic"] == pytest.approx(0.0)


def test_wilcoxon_alternatives_p_complement(tmp_path):
    """单侧与双侧关系：精确分布下 pt = 2×min(pl, pg)（scipy 对不利方向给平凡尾 p=1，
    故取两侧较小者；本项目数据实测 pl=0.125, pg=1.0, pt=0.25）。"""
    p = _csv(tmp_path, pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": [2, 4, 5, 4, 5]}))
    pt = _call(p, test="wilcoxon", column="a", sample2_col="b")["result"]["p_value"]
    pl = _call(p, test="wilcoxon", column="a", sample2_col="b",
               alternative="less")["result"]["p_value"]
    pg = _call(p, test="wilcoxon", column="a", sample2_col="b",
               alternative="greater")["result"]["p_value"]
    assert pt == pytest.approx(min(2 * pl, 2 * pg), abs=1e-9)


# ---------------- Mann-Whitney 手算对照 ----------------

def test_mann_whitney_hand_calculated(tmp_path):
    """x=[1,2,3] vs y=[4,5,6,7]：U=0, p=2/35, r=-1（group1 全体低于 group2）。"""
    p = _csv(tmp_path, pd.DataFrame({"g": ["A"] * 3 + ["B"] * 4,
                                     "v": [1, 2, 3, 4, 5, 6, 7]}))
    rs = _call(p, test="mann_whitney", group_col="g", value_col="v")["result"]
    assert rs["statistic"] == pytest.approx(0.0)
    assert rs["p_value"] == pytest.approx(2.0 / 35.0, abs=1e-10)
    assert rs["effsize"] == pytest.approx(-1.0, abs=1e-9)
    assert rs["n1"] == 3 and rs["n2"] == 4


def test_mann_whitney_zero_effect_no_difference(tmp_path):
    """两组同分布（交错）：U≈n1·n2/2 → r≈0，p 大。"""
    p = _csv(tmp_path, pd.DataFrame({"g": ["A", "B"] * 8,
                                     "v": [float(i) for i in range(16)]}))
    rs = _call(p, test="mann_whitney", group_col="g", value_col="v")["result"]
    assert rs["effsize"] == pytest.approx(0.0, abs=0.2)
    assert rs["p_value"] > 0.05


# ---------------- Kruskal-Wallis 手算对照 ----------------

def test_kruskal_hand_calculated(tmp_path):
    """三组 1..3 / 4..6 / 7..9：H=7.2, ε²=0.9。"""
    p = _csv(tmp_path, pd.DataFrame({"g": ["A"] * 3 + ["B"] * 3 + ["C"] * 3,
                                     "v": [1, 2, 3, 4, 5, 6, 7, 8, 9]}))
    rs = _call(p, test="kruskal_wallis", group_col="g", value_col="v")["result"]
    assert rs["statistic"] == pytest.approx(7.2, abs=1e-9)
    assert rs["effsize"] == pytest.approx(7.2 / 8.0, abs=1e-9)
    assert rs["p_value"] < 0.05
    assert rs["n_groups"] == 3 and rs["n"] == 9
    assert "拒绝 H0" in rs["conclusion"]


def test_kruskal_no_difference_high_p(tmp_path):
    """三组同分布：H≈0，p 大，不能拒绝。"""
    rng = np.random.default_rng(42)
    vals = rng.normal(0, 1, 30).tolist()
    p = _csv(tmp_path, pd.DataFrame({"g": ["A"] * 10 + ["B"] * 10 + ["C"] * 10,
                                     "v": vals}))
    rs = _call(p, test="kruskal_wallis", group_col="g", value_col="v")["result"]
    assert rs["p_value"] > 0.05


# ---------------- 边界与错误 ----------------

def test_errors(tmp_path):
    p2 = _csv(tmp_path, pd.DataFrame({"g": ["A"] * 3 + ["B"] * 3,
                                      "v": [1, 2, 3, 4, 5, 6]}))
    assert "test 仅支持" in nonparametric_test(str(p2), test="anova_test")["message"]
    assert "alternative 仅支持" in nonparametric_test(str(p2), test="mann_whitney",
                                                      group_col="g", value_col="v",
                                                      alternative="one_side")["message"]
    assert "alpha 必须在" in nonparametric_test(str(p2), test="mann_whitney",
                                                group_col="g", value_col="v",
                                                alpha=1.5)["message"]
    assert "alpha 必须在" in nonparametric_test(str(p2), test="mann_whitney",
                                                group_col="g", value_col="v",
                                                alpha=float("nan"))["message"]
    import math
    assert "alpha 必须在" in nonparametric_test(str(p2), test="mann_whitney",
                                                group_col="g", value_col="v",
                                                alpha=math.inf)["message"]
    # wilcoxon 缺列
    assert "缺少列" in nonparametric_test(str(p2), test="wilcoxon",
                                          column="v", sample2_col=None)["message"]
    # mw 组数不足
    p3 = _csv(tmp_path, pd.DataFrame({"g": ["A"] * 5, "v": [1, 2, 3, 4, 5]}))
    r = nonparametric_test(str(p3), test="mann_whitney", group_col="g", value_col="v")
    assert r["status"] == "error" and ("2 组" in r["message"] or "恰好" in r["message"])
    # wilcoxon 常量差（全 0 差）
    p4 = _csv(tmp_path, pd.DataFrame({"a": [1.0] * 6, "b": [1.0] * 6}))
    r4 = nonparametric_test(str(p4), test="wilcoxon", column="a", sample2_col="b")
    assert r4["status"] == "error" and "无变异" in r4["message"]
    # mw 组内样本不足
    p5 = _csv(tmp_path, pd.DataFrame({"g": ["A"] * 1 + ["B"] * 3,
                                      "v": [1.0, 2, 3, 4]}))
    r5 = nonparametric_test(str(p5), test="mann_whitney", group_col="g", value_col="v")
    assert r5["status"] == "error" and "样本量不足" in r5["message"]
    # kruskal 组数 > 20
    big = [f"g{i:02d}" for i in range(21)]
    vals = [float(i) for i in range(42)]
    p6 = _csv(tmp_path, pd.DataFrame({"g": [big[i % 21] for i in range(42)],
                                      "v": vals}))
    r6 = nonparametric_test(str(p6), test="kruskal_wallis", group_col="g", value_col="v")
    assert r6["status"] == "error" and "超过 20" in r6["message"]
    assert nonparametric_test(str(SAMPLES / "nope.csv"), test="mann_whitney",
                              group_col="g", value_col="v")["status"] == "error"


def test_chinese_columns(tmp_path):
    p = _csv(tmp_path, pd.DataFrame({"疗法": ["甲"] * 3 + ["乙"] * 3,
                                     "分数": [1, 2, 3, 4, 5, 6]}))
    rs = _call(p, test="mann_whitney", group_col="疗法", value_col="分数")["result"]
    assert rs["method"] == "mann_whitney"


def test_clean_csv_mw_ok():
    """clean.csv 的 A/B 两组真实跑通（语义核验）。"""
    df = pd.read_csv(SAMPLES / "clean.csv", encoding="utf-8-sig")
    sub = df[df["category"].isin(["A", "B"])]
    pytest.importorskip("tempfile")
    import os
    import tempfile

    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    try:
        sub.to_csv(path, index=False, encoding="utf-8-sig")
        r = _call(path, test="mann_whitney", group_col="category", value_col="score")
        assert 0 <= abs(r["result"]["effsize"]) <= 1
        assert 0 <= r["result"]["p_value"] <= 1
    finally:
        os.unlink(path)


# ---------------- 确定性与 JSON 安全 ----------------

def test_deterministic_and_json_safe(tmp_path):
    p = _csv(tmp_path, pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": [2, 4, 5, 4, 5]}))
    r1 = _call(p, test="wilcoxon", column="a", sample2_col="b")
    json.dumps(r1, allow_nan=False, ensure_ascii=False)
    r2 = nonparametric_test(str(p), test="wilcoxon", column="a", sample2_col="b")
    assert json.dumps(r1, sort_keys=True, ensure_ascii=False) == json.dumps(
        r2, sort_keys=True, ensure_ascii=False)


def test_kruskal_json_safe(tmp_path):
    rng = np.random.default_rng(7)
    p = _csv(tmp_path, pd.DataFrame({"g": ["A"] * 8 + ["B"] * 8,
                                     "v": rng.normal(0, 1, 16).tolist()}))
    r = _call(p, test="kruskal_wallis", group_col="g", value_col="v")
    json.dumps(r, allow_nan=False, ensure_ascii=False)
