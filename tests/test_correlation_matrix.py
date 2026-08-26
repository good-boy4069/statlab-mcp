"""tests/test_correlation_matrix.py —— 工具 4 测试（规范 10）。

独立性（红队裁决 13）：测试内**手写 pearson 公式**（Σ(x-x̄)(y-ȳ) / √(ΣΣ)）作独立对照
（不引用 numpy.corrcoef / scipy，避免同源互证）；r=±1 精确断言；
校正单调性（校正后 p ≥ 原始 p）断言 fdr_bh/bonferroni 生效。
"""
import json
import math
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools.data_exploration_correlation_matrix import correlation_matrix

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
FIX = ROOT / "tests" / "fixtures"


def _call(path, **kw) -> dict:
    r = correlation_matrix(str(path), **kw)
    assert r["status"] == "ok", r.get("message", r)
    return r


def _pearson_hand(xs: list, ys: list) -> float:
    """测试内独立实现 pearson 公式（对照用，不依赖 scipy/numpy 实现）。"""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=False))
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return num / den


# ---------------- 独立对照：手写公式 vs 工具 ----------------

def test_r_matches_hand_formula(tmp_path):
    """用确定性小数据，工具输出对照测试内手写 pearson 公式。"""
    xs = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    ys = [2, 4, 5, 4, 5, 8, 7, 10, 9, 11]
    p = tmp_path / "corr_hand.csv"
    pd.DataFrame({"x": xs, "y": ys}).to_csv(p, index=False, encoding="utf-8-sig")
    r = _call(p)
    got = r["result"]["correlation"]["x"]["y"]
    assert got == pytest.approx(_pearson_hand(xs, ys), abs=1e-12)


def test_perfect_linear_r_exact(tmp_path):
    xs = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    p = tmp_path / "corr_perfect.csv"
    pd.DataFrame({"x": xs, "p": [2 * v for v in xs], "n": [11 - v for v in xs]}).to_csv(
        p, index=False, encoding="utf-8-sig")
    r = _call(p)
    c = r["result"]["correlation"]
    assert c["x"]["p"] == pytest.approx(1.0)        # 完全正线性
    assert c["x"]["n"] == pytest.approx(-1.0)       # 完全负线性
    assert r["result"]["p_value"]["x"]["p"] < 0.001  # r=1 时 p 为极小浮点（如 1e-61）


# ---------------- 矩阵结构 ----------------

def test_matrix_structure_clean():
    r = _call(SAMPLES / "clean.csv")
    res = r["result"]
    assert res["n_pairs"] == 6                          # 4 列 -> 4*3/2
    assert res["excluded_columns"] == ["category", "date"]
    c = res["correlation"]
    assert c["id"]["id"] == 1.0 and c["score"]["id"] == c["id"]["score"]   # 对角 1.0 且对称
    assert res["p_value"]["id"]["id"] is None           # p 对角 null（使用者裁决）
    assert res["n_pairwise"]["id"]["id"] == 50
    assert "相关≠因果" in r["summary"]
    assert "fdr_bh" in r["summary"]


def test_pairwise_sample_size_with_nan(tmp_path):
    """成对样本量：缺失行不影响其他对。"""
    p = tmp_path / "pair.csv"
    pd.DataFrame({"a": [1.0, 2.0, None, 4.0, 5.0],
                  "b": [1.0, None, 3.0, 4.0, 5.0]}).to_csv(p, index=False, encoding="utf-8-sig")
    r = _call(p)
    npw = r["result"]["n_pairwise"]
    assert npw["a"]["b"] == 3          # 同时非 NaN 的行：1,4,5 行（0 基 0,3,4）
    assert npw["a"]["a"] == 4 and npw["b"]["b"] == 4


# ---------------- 多方法 / 校正 ----------------

def test_methods_and_p_adjust_variants():
    for method in ("pearson", "spearman", "kendalltau"):
        r1 = _call(SAMPLES / "clean.csv", method=method)
        assert r1["result"]["method"] == method
    for pa in ("none", "bonferroni", "fdr_bh"):
        r2 = _call(SAMPLES / "clean.csv", p_adjust=pa)
        assert r2["status"] == "ok"


def test_correction_monotonicity(tmp_path):
    """校正生效：fdr_bh/bonferroni 的 p 不小于原始 p（单调性），且 ≤1.0。"""
    rng = __import__("numpy").random.default_rng(7)
    n = 30
    frame = {"a" + str(i): rng.normal(0, 1, n) + (rng.normal(0, 1, n) * 0.05 if i < 4 else 0)
             for i in range(8)}       # 8 列 -> 28 对，前几对有弱相关
    p = tmp_path / "corr.csv"
    pd.DataFrame(frame).to_csv(p, index=False, encoding="utf-8-sig")
    raw = _call(p, p_adjust="none")["result"]["p_value"]
    for pa in ("fdr_bh", "bonferroni"):
        adj = _call(p, p_adjust=pa)["result"]["p_value"]
        checked = 0
        cols = list(frame)
        for i in range(8):
            for j in range(i + 1, 8):
                a, b = cols[i], cols[j]
                rv, av = raw[a][b], adj[a][b]
                if rv is None:
                    continue
                assert av >= rv - 1e-12 and av <= 1.0   # 校正不减小、不越界
                checked += 1
        assert checked > 0


# ---------------- 边界与错误 ----------------

def test_constant_column_pair_null():
    r = _call(FIX / "constant_col.csv")
    c = r["result"]["correlation"]["x"]["y"]
    assert c is None                                     # 常量列协方差无定义
    assert r["result"]["p_value"]["x"]["y"] is None
    assert r["result"]["n_pairwise"]["x"]["y"] == 12     # 样本量仍如实记录


def test_too_few_numeric_columns_errors(tmp_path):
    p = tmp_path / "one.csv"
    pd.DataFrame({"a": [1.0, 2.0, 3.0]}).to_csv(p, index=False, encoding="utf-8-sig")
    r = correlation_matrix(str(p))
    assert r["status"] == "error" and "至少需要 2 个数值列" in r["message"]


def test_too_many_columns_errors(tmp_path):
    p = tmp_path / "many.csv"
    pd.DataFrame({f"c{i}": [1.0] * 5 for i in range(21)}).to_csv(
        p, index=False, encoding="utf-8-sig")
    r = correlation_matrix(str(p))
    assert r["status"] == "error" and "超过 20 个" in r["message"]


def test_bad_params_cn():
    assert "method 仅支持" in correlation_matrix(
        str(SAMPLES / "clean.csv"), method="polynomial")["message"]
    assert "p_adjust 仅支持" in correlation_matrix(
        str(SAMPLES / "clean.csv"), p_adjust="holm")["message"]


def test_errors_basic(tmp_path):
    assert correlation_matrix(str(SAMPLES / "nope.csv"))["status"] == "error"
    p = tmp_path / "cn.csv"
    pd.DataFrame({"姓名": ["张三", "李四"], "甲": [1.0, 2.0], "乙": [3.0, 4.0]}).to_csv(
        p, index=False, encoding="utf-8-sig")
    r = correlation_matrix(str(p))                       # 中文列名 + 2 数值列
    assert r["status"] == "ok"
    assert "甲" in r["result"]["correlation"] and "姓名" in r["result"]["excluded_columns"]


def test_json_safe_and_deterministic():
    r1 = _call(SAMPLES / "dirty.csv")
    json.dumps(r1, allow_nan=False, ensure_ascii=False)
    r2 = correlation_matrix(str(SAMPLES / "dirty.csv"))
    assert json.dumps(r1, sort_keys=True, ensure_ascii=False) == json.dumps(
        r2, sort_keys=True, ensure_ascii=False)
