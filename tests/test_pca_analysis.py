"""tests/test_pca_analysis.py —— 工具 15 测试（规范 10）。

独立性：方差解释率用测试内独立实现核对——协方差矩阵 numpy.linalg.eigh
特征分解（不引用 sklearn PCA）；构造 u 主导结构（PC1 载荷符号相反、比例大）。
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools.modeling_pca_analysis import pca_analysis

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


def _call(p, nc) -> dict:
    r = pca_analysis(str(p), nc)
    assert r["status"] == "ok", r.get("message", r)
    return r


def _pca_hand(X: np.ndarray) -> np.ndarray:
    """测试内独立 PCA（镜像工具口径：StandardScaler 标准化后）：
    标准化 -> 协方差 -> eigh（不依赖 sklearn）。"""
    Xs = (X - X.mean(axis=0)) / X.std(axis=0, ddof=1)
    cov = Xs.T @ Xs / (X.shape[0] - 1)
    w, _ = np.linalg.eigh(cov)             # 升序
    return w[::-1] / w.sum()               # 降序方差解释率


# ---------------- 独立核对：eigh vs sklearn ----------------

def test_explained_ratio_matches_eigh(tmp_path):
    rng = np.random.default_rng(31)
    n = 80
    u = rng.normal(0, 3, n)
    X = np.column_stack([u + rng.normal(0, 0.5, n),       # 强相关对
                         u * 2 + rng.normal(0, 0.5, n),
                         rng.normal(0, 1, n)])            # 独立噪声
    p = tmp_path / "pca.csv"
    pd.DataFrame(X, columns=["v1", "v2", "v3"]).to_csv(p, index=False, encoding="utf-8-sig")
    rs = _call(p, 3)["result"]
    hand = _pca_hand(X)
    assert rs["explained_variance_ratio"][0] == pytest.approx(hand[0], abs=1e-6)
    assert rs["explained_variance_ratio"][-1] == pytest.approx(hand[-1], abs=1e-6)
    assert sum(rs["explained_variance_ratio"]) == pytest.approx(1.0)   # 数学恒等
    assert rs["cumulative_ratio"][-1] == pytest.approx(1.0)
    # PC1 载荷 v2>v1（v2 变异更大）且同号——u 主导
    pc1 = {ld["feature"]: ld["loading"] for ld in rs["loadings"] if ld["component"] == 1}
    assert pc1["v1"] > 1.0 and pc1["v2"] > 2.0 and abs(pc1["v3"]) < abs(pc1["v1"])


def test_clean_k2_structure_and_image():
    r = _call(SAMPLES / "clean.csv", 2)
    rs = r["result"]
    assert rs["n_features"] == 4 and rs["n_samples"] == 50
    assert rs["excluded_columns"] == ["category", "date"]
    assert len(rs["explained_variance_ratio"]) == 2
    assert rs["cumulative_ratio"][0] < rs["cumulative_ratio"][1] <= 1.0
    assert len(rs["loadings"]) == 2 * 4
    img = Path(r["__image__"])
    assert img.is_absolute() and img.suffix == ".png" and img.exists()


def test_single_feature_degenerate(tmp_path):
    p = tmp_path / "one.csv"
    pd.DataFrame({"v": np.arange(20.0)}).to_csv(p, index=False, encoding="utf-8-sig")
    rs = _call(p, 1)["result"]
    assert rs["explained_variance_ratio"] == [1.0]
    assert "无降维意义" in r"{}".format("") or "无降维意义" in pca_analysis(
        str(p), 1)["summary"]


def test_errors(tmp_path):
    p = tmp_path / "pca.csv"
    pd.DataFrame({"a": np.arange(10.0), "b": np.arange(10.0) * 2}).to_csv(
        p, index=False, encoding="utf-8-sig")
    assert "n_components 必须在" in pca_analysis(str(p), 0)["message"]
    assert "n_components 必须在" in pca_analysis(str(p), 3)["message"]   # 3 > min(10,2)
    assert "n_components 必须是整数" in pca_analysis(str(p), 1.5)["message"]
    assert "n_components 必须是整数" in pca_analysis(str(p), True)["message"]
    p2 = tmp_path / "txt.csv"
    pd.DataFrame({"c": ["甲", "乙"]}).to_csv(p2, index=False, encoding="utf-8-sig")
    assert "未找到数值列" in pca_analysis(str(p2), 1)["message"]
    assert pca_analysis(str(SAMPLES / "nope.csv"), 2)["status"] == "error"


def test_chinese_columns(tmp_path):
    p = tmp_path / "cn.csv"
    pd.DataFrame({"收入": np.arange(30.0), "年龄": np.arange(30.0) + 20}).to_csv(
        p, index=False, encoding="utf-8-sig")
    rs = _call(p, 1)["result"]
    assert rs["loadings"][0]["feature"] == "收入"


def test_json_safe_and_deterministic():
    r1 = _call(SAMPLES / "clean.csv", 2)
    json.dumps(r1, allow_nan=False, ensure_ascii=False)
    r2 = pca_analysis(str(SAMPLES / "clean.csv"), 2)
    assert json.dumps(r1["result"], sort_keys=True, ensure_ascii=False) == json.dumps(
        r2["result"], sort_keys=True, ensure_ascii=False)
