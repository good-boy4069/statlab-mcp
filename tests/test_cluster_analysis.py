# -*- coding: utf-8 -*-
"""tests/test_cluster_analysis.py —— 工具 14 测试（规范 10）。

独立性：反标准化质心 = 原空间簇均值（KMeans 数学性质，手算每组均值核对）；
k=2 真两团数据的轮廓系数应高于 k=3（结构与轮廓系数的语义一致）。
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools.modeling_cluster_analysis import cluster_analysis

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


def _call(p, k) -> dict:
    r = cluster_analysis(str(p), k)
    assert r["status"] == "ok", r.get("message", r)
    return r


# ---------------- 质心 = 簇均值（手算核对） ----------------

def test_centroid_equals_cluster_mean(tmp_path):
    """人造两团团（age 20~30 与 60~70 各 15 人，score 两侧）：k=2
    反标准化质心应落在各团均值 ±1.5 内（样本抽样误差 ~σ/√15，容差 1.5）。"""
    rng = np.random.default_rng(21)
    a1 = rng.normal(25, 2, 15)
    a2 = rng.normal(65, 2, 15)
    s1 = rng.normal(60, 5, 15)
    s2 = rng.normal(40, 5, 15)
    p = tmp_path / "km.csv"
    pd.DataFrame({"age": np.concatenate([a1, a2]),
                  "score": np.concatenate([s1, s2])}).to_csv(
        p, index=False, encoding="utf-8-sig")
    r = _call(p, k=2)
    rs = r["result"]
    assert rs["k"] == 2 and rs["n_samples"] == 30
    cents = sorted(rs["clusters"], key=lambda x: x["centroid_original_units"]["age"])
    assert cents[0]["centroid_original_units"]["age"] == pytest.approx(25.0, abs=1.5)
    assert cents[1]["centroid_original_units"]["age"] == pytest.approx(65.0, abs=1.5)
    assert cents[0]["n_members"] == 15 and cents[1]["n_members"] == 15
    assert rs["silhouette"] > 0.5                       # 两团真结构
    r3 = _call(p, k=3)
    assert r3["result"]["silhouette"] < rs["silhouette"]   # 结构真有两团（兼容标准化后）


def test_k_compare_real_structure(tmp_path):
    """1D 两团（±4）：k=2 比 k=3 轮廓更高（真结构）；k=2 时 k_minus_1=null。"""
    rng = np.random.default_rng(23)
    x = np.concatenate([rng.normal(-4, 1, 20), rng.normal(4, 1, 20)])
    p = tmp_path / "km2.csv"
    pd.DataFrame({"x": x}).to_csv(p, index=False, encoding="utf-8-sig")
    r2 = _call(p, k=2)
    r3 = _call(p, k=3)
    assert r2["result"]["silhouette"] > r3["result"]["silhouette"]
    assert r2["result"]["silhouette_compare"]["k_minus_1"] is None
    assert r2["result"]["silhouette_compare"]["k_plus_1"]["k"] == 3


# ---------------- 边界与错误 ----------------

def test_k_validation(tmp_path):
    p = tmp_path / "k.csv"
    pd.DataFrame({"a": np.arange(10.0), "b": np.arange(10.0) * 2}).to_csv(
        p, index=False, encoding="utf-8-sig")
    assert "k 必须在 2 到 N-1" in cluster_analysis(str(p), 1)["message"]
    assert "k 必须在 2 到 N-1" in cluster_analysis(str(p), 10)["message"]
    assert "k 必须是整数" in cluster_analysis(str(p), 3.5)["message"]
    assert "k 必须是整数" in cluster_analysis(str(p), True)["message"]


def test_no_numeric_cols(tmp_path):
    p = tmp_path / "txt.csv"
    pd.DataFrame({"c": ["甲", "乙", "丙", "丁"]}).to_csv(p, index=False, encoding="utf-8-sig")
    r = cluster_analysis(str(p), 2)
    assert r["status"] == "error" and "未找到数值列" in r["message"]


def test_clean_k3_structure():
    r = _call(SAMPLES / "clean.csv", k=3)
    rs = r["result"]
    assert rs["excluded_columns"] == ["category", "date"]
    assert sum(c["n_members"] for c in rs["clusters"]) == 50
    assert all("score" in c["centroid_original_units"] for c in rs["clusters"])
    assert rs["standardized"] is True
    assert -1 <= rs["silhouette"] <= 1
    assert rs["silhouette_compare"]["k_minus_1"]["k"] == 2
    assert rs["silhouette_compare"]["k_plus_1"]["k"] == 4


def test_chinese_columns(tmp_path):
    rng = np.random.default_rng(5)
    p = tmp_path / "cn.csv"
    pd.DataFrame({"年龄": rng.normal(40, 10, 30), "分数": rng.normal(70, 10, 30)}).to_csv(
        p, index=False, encoding="utf-8-sig")
    r = _call(p, k=2)
    assert "年龄" in r["result"]["clusters"][0]["centroid_original_units"]


def test_json_safe_and_deterministic():
    r1 = _call(SAMPLES / "clean.csv", k=3)
    json.dumps(r1, allow_nan=False, ensure_ascii=False)
    r2 = cluster_analysis(str(SAMPLES / "clean.csv"), 3)
    assert json.dumps(r1, sort_keys=True, ensure_ascii=False) == json.dumps(
        r2, sort_keys=True, ensure_ascii=False)