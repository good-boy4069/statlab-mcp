"""tests/test_linear_regression.py —— 工具 12 测试（规范 10）。

独立性：精确线性 y=2x+1 硬编码（Excel SLOPE/INTERCEPT 可复核）；R² 与
correlation_matrix 的 r² 交叉验证（数学恒等 R²=r²，单特征时）。
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools.modeling_linear_regression import linear_regression

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


def _call(p, **kw) -> dict:
    r = linear_regression(str(p), **kw)
    assert r["status"] == "ok", r.get("message", r)
    return r


def _csv(tmp_path, **cols):
    p = tmp_path / "lr.csv"
    pd.DataFrame(cols).to_csv(p, index=False, encoding="utf-8-sig")
    return p


# ---------------- 精确线性硬编码 ----------------

def test_perfect_line_exact_coefficients(tmp_path):
    """y=2x+1（x=1..10）：β=[1,2] 精确、R²=1.0。Excel SLOPE=2/INTERCEPT=1 可复核。"""
    p = _csv(tmp_path, x=list(range(1, 11)), y=[2 * v + 1 for v in range(1, 11)])
    r = _call(p, target="y", features=["x"])
    rs = r["result"]
    b = {c["name"]: c["beta"] for c in rs["coefficients"]}
    assert b["const"] == pytest.approx(1.0)
    assert b["x"] == pytest.approx(2.0, abs=1e-9)
    assert rs["r_squared"] == pytest.approx(1.0, abs=1e-9)
    assert rs["dropped_rows"] == 0
    assert rs["durbin_watson"] is not None


# ---------------- R² 与相关系数交叉验证 ----------------

def test_r2_equals_correlation_squared():
    """income~age 单特征：R² = r²（数学恒等；r 来自 correlation_matrix 独立实测）。"""
    from statlab_mcp.tools.data_exploration_correlation_matrix import (
        correlation_matrix,
    )
    cm = correlation_matrix(str(SAMPLES / "clean.csv"))["result"]
    r_val = cm["correlation"]["age"]["income"]
    lr = _call(SAMPLES / "clean.csv", target="income", features=["age"])["result"]
    assert lr["r_squared"] == pytest.approx(r_val ** 2, abs=1e-6)
    assert 0.05 < lr["r_squared"] < 0.15                # 回归基准（seed 固定）


# ---------------- one-hot 与缺失 ----------------

def test_categorical_one_hot_mapping(tmp_path):
    """类别特征 one-hot：映射表正确；模型可拟合。"""
    rng = np.random.default_rng(9)
    n = 60
    p = _csv(tmp_path, x=rng.normal(0, 1, n),
             c=[f"G{i % 3}" for i in range(n)],
             y=rng.normal(0, 1, n) + np.array([i % 3 for i in range(n)]))
    r = _call(p, target="y", features=["x", "c"])
    rs = r["result"]
    assert rs["dummy_mapping"]["c_G0"] == "c=G0"
    assert rs["dummy_mapping"]["c_G2"] == "c=G2"
    assert rs["n"] == 60
    assert any(c["name"] == "c_G0" for c in rs["coefficients"])


def test_listwise_dropna_reported(tmp_path):
    xs = list(range(1, 21))
    xs[3] = None
    xs[9] = None
    xs[15] = None    # 3 个缺失
    p = _csv(tmp_path, x=xs, y=list(range(20)))
    rs = _call(p, target="y", features=["x"])["result"]
    assert rs["dropped_rows"] == 3
    assert rs["n"] == 17
    assert "已剔除缺失 3 行" in linear_regression(str(p), target="y",
                                                   features=["x"])["summary"]


def test_zero_variance_col_dropped(tmp_path):
    p = _csv(tmp_path, x=[1.0] * 10, z=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
             y=list(range(10)))
    rs = _call(p, target="y", features=["x", "z"])["result"]
    assert rs["drop_zero_var"] == ["x"]        # 常数列自动剔除并报告
    assert rs["n_features"] == 1


# ---------------- 图与结构 ----------------

def test_image_top_level_and_exists():
    r = _call(SAMPLES / "clean.csv", target="income", features=["age"])
    img = r["__image__"]
    p = Path(img)
    assert p.is_absolute() and p.suffix == ".png"
    assert p.name.startswith("residuals_linear_regression_all_")
    assert p.exists() and p.stat().st_size > 0


def test_vif_flag_when_collinear(tmp_path):
    """x2=2*x1 完全共线 -> VIF 极大（或无穷），应命中 vif_flags 或可计算性处理。"""
    p = _csv(tmp_path, x1=list(range(1, 16)), x2=[2 * v for v in range(1, 16)],
             y=[float(v) + v % 3 for v in range(1, 16)])
    r = _call(p, target="y", features=["x1", "x2"])
    rs = r["result"]
    assert rs["vif_flags"] or any(c["vif"] is not None and c["vif"] > 10
                                  for c in rs["coefficients"])
    assert rs["r_squared"] > 0.9          # 共线但不影响拟合优度


# ---------------- 错误与边界 ----------------

def test_errors(tmp_path):
    p = _csv(tmp_path, x=list(range(1, 6)), y=[2 * v for v in range(1, 6)])
    assert "至少需要 1 个特征" in linear_regression(str(p), target="y",
                                                     features=[])["message"]
    assert "含重复项" in linear_regression(str(p), target="y",
                                            features=["x", "x"])["message"]
    assert "缺少必需列" in linear_regression(str(p), target="nope",
                                              features=["x"])["message"]
    p_cat = _csv(tmp_path, x=[1.0, 2.0, 3.0, 4.0, 5.0], y=[2.0, 4.0, 6.0, 8.0, 10.0],
                 cat=["a", "b", "a", "b", "a"])
    assert "不是数值列" in linear_regression(str(p_cat), target="cat",
                                              features=["x"])["message"]
    r = linear_regression(str(p_cat), target="y", features=["x", "cat"])
    assert r["status"] == "error" and "样本量不足" in r["message"]   # n=5 <= 3+2
    assert "alpha 必须在" in linear_regression(str(p), target="y",
                                                features=["x"], alpha=1.0)["message"]
    assert linear_regression(str(SAMPLES / "nope.csv"), target="y",
                             features=["x"])["status"] == "error"


def test_add_constant_false_runs(tmp_path):
    p = _csv(tmp_path, x=list(range(1, 11)), y=[2 * v + 1 for v in range(1, 11)])
    r = _call(p, target="y", features=["x"], add_constant=False)
    assert r["result"]["add_constant"] is False
    assert "参考意义受限" in r["summary"]


def test_chinese_columns(tmp_path):
    p = _csv(tmp_path, 年龄=list(range(20, 30)), 收入=[v * 100 for v in range(20, 30)])
    r = _call(p, target="收入", features=["年龄"])
    assert "年龄" in [c["name"] for c in r["result"]["coefficients"]]


def test_json_safe_and_deterministic():
    r1 = _call(SAMPLES / "clean.csv", target="income", features=["age", "score"])
    json.dumps(r1, allow_nan=False, ensure_ascii=False)
    r2 = linear_regression(str(SAMPLES / "clean.csv"), target="income",
                           features=["age", "score"])
    assert json.dumps(r1["result"], sort_keys=True, ensure_ascii=False) == json.dumps(
        r2["result"], sort_keys=True, ensure_ascii=False)
