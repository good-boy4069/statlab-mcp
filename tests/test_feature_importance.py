# -*- coding: utf-8 -*-
"""tests/test_feature_importance.py —— 工具 16 测试（规范 10）。

独立性：构造"只有 age 影响目标"的合成数据——语义结论（age 应是第一名）
可人工核验；随机森林为集成算法，无法逐数手算，以构造语义为准。
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools.modeling_feature_importance import feature_importance

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
SAMPLES = ROOT / "samples"


def _call(p, **kw) -> dict:
    r = feature_importance(str(p), **kw)
    assert r["status"] == "ok", r.get("message", r)
    return r


def _csv(tmp_path, **cols):
    p = tmp_path / "fi.csv"
    pd.DataFrame(cols).to_csv(p, index=False, encoding="utf-8-sig")
    return p


# ---------------- 构造语义：age 主导 ----------------

def test_age_dominant_permutation(tmp_path):
    rng = np.random.default_rng(41)
    n = 90
    age = rng.normal(40, 12, n)
    noise_feat = rng.normal(0, 1, n)
    y = 2.5 * age + rng.normal(0, 3, n)          # 只有 age 影响
    p = _csv(tmp_path, age=age, noise=noise_feat, y=y)
    r = _call(p, target="y", method="permutation", n_estimators=100)
    rs = r["result"]
    assert rs["importances"][0]["feature"] == "age"
    assert rs["importances"][0]["rank"] == 1
    assert rs["model_type"] == "regression"
    assert rs["importances"][0]["importance"] > rs["importances"][1]["importance"]
    assert "重要性≠因果" in r["summary"] and "重要性≠因果" in rs["conclusion"]


def test_impurity_method_runs(tmp_path):
    rng = np.random.default_rng(42)
    n = 80
    p = _csv(tmp_path, a=rng.normal(0, 1, n), b=rng.normal(0, 1, n),
             y=rng.normal(0, 1, n) + rng.normal(0, 1, n) * 2)
    r = _call(p, target="y", method="impurity", n_estimators=50)
    rs = r["result"]
    assert rs["method"] == "impurity"
    importances_sum = sum(v["importance"] for v in rs["importances"])
    assert importances_sum == pytest.approx(1.0, abs=1e-9)   # impurity 归一化恒等
    assert [v["rank"] for v in rs["importances"]] == [1, 2]


def test_classification_target(tmp_path):
    r = _call(FIX / "binary_noisy.csv", target="label", features=None, n_estimators=100) \
        if False else _call(FIX / "binary_noisy.csv", target="label", n_estimators=100)
    assert r["result"]["model_type"] == "classification"
    assert r["result"]["importances"][0]["feature"] == "score"      # score 主导标签


def test_categorical_feature_one_hot_mapping(tmp_path):
    rng = np.random.default_rng(43)
    n = 90
    cat = [f"G{i % 3}" for i in range(n)]
    p = _csv(tmp_path, cat=cat, x=rng.normal(0, 1, n),
             y=rng.normal(0, 1, n) + np.array([2.0 if c == "G0" else 0.0 for c in cat]))
    r = _call(p, target="y", n_estimators=100)
    assert r["result"]["dummy_mapping"] is not None
    assert r["result"]["dummy_mapping"]["cat_G0"] == "cat=G0"


# ---------------- 硬性门槛与参数 ----------------

def test_n_lt_50_rejected(tmp_path):
    p = _csv(tmp_path, a=np.arange(40.0), y=np.arange(40.0) * 2)
    r = feature_importance(str(p), target="y")
    assert r["status"] == "error" and "小于 50" in r["message"]


def test_param_validation(tmp_path):
    rng = np.random.default_rng(1)
    n = 60
    p = _csv(tmp_path, a=rng.normal(0, 1, n), y=rng.normal(0, 1, n))
    assert "method 仅支持" in feature_importance(
        str(p), target="y", method="gain")["message"]
    assert "n_estimators 必须" in feature_importance(
        str(p), target="y", n_estimators=5)["message"]
    assert "n_repeats 必须" in feature_importance(
        str(p), target="y", n_repeats=0)["message"]
    assert "缺少必需列" in feature_importance(str(p), target="nope")["message"]
    assert feature_importance(str(SAMPLES / "nope.csv"), target="y")["status"] == "error"


def test_dropped_rows_reported(tmp_path):
    xs = list(np.arange(60.0))
    xs[5] = None; xs[20] = None
    p = _csv(tmp_path, a=xs, y=list(np.arange(60.0)))
    rs = _call(p, target="y", n_estimators=50)["result"]
    assert rs["dropped_rows"] == 2 and rs["n"] == 58


def test_clean_income_runs(tmp_path):
    """clean.csv income 目标（回归）可跑；n=50 恰好过门槛。"""
    r = _call(SAMPLES / "clean.csv", target="income", n_estimators=100, n_repeats=5)
    assert r["result"]["model_type"] == "regression"
    assert len(r["result"]["importances"]) >= 4


def test_json_safe_and_deterministic(tmp_path):
    rng = np.random.default_rng(44)
    n = 70
    p = _csv(tmp_path, age=rng.normal(40, 10, n),
             x=rng.normal(0, 1, n), y=rng.normal(0, 1, n) + rng.normal(0, 1, n))
    r1 = _call(p, target="y", n_estimators=50)
    json.dumps(r1, allow_nan=False, ensure_ascii=False)
    r2 = feature_importance(str(p), target="y", n_estimators=50)
    v1 = {v["feature"]: v["importance"] for v in r1["result"]["importances"]}
    v2 = {v["feature"]: v["importance"] for v in r2["result"]["importances"]}
    assert r1["result"]["importances"] == r2["result"]["importances"] \
        or all(abs(v1[k] - v2[k]) < 1e-9 for k in v1)   # 数值容差兜底（并行回归下的 1ulp 噪声）