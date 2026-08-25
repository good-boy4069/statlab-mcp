"""tests/test_logistic_regression.py —— 工具 13 测试（规范 10）。

独立性：可分离数据（score>50 完美分类）AUC=1.0 为数学事实；复现性断言固定 seed；
balanced 复制数量按公式手算对照（w=n/(2*n_class)）。
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools.modeling_logistic_regression import logistic_regression

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"


def _call(p, **kw) -> dict:
    r = logistic_regression(str(p), **kw)
    assert r["status"] == "ok", r.get("message", r)
    return r


# ---------------- 收敛与结构 ----------------

def test_noisy_structure():
    r = _call(FIX / "binary_noisy.csv", target="label", features=["score", "age"])
    rs = r["result"]
    assert rs["roc_auc"] > 0.85                        # 语义基准（score 主导标签）
    assert rs["auc_ci_lower"] <= rs["roc_auc"] <= rs["auc_ci_upper"]
    assert 0.7 < rs["accuracy"] < 1.0
    cm = rs["confusion_matrix"]
    assert {"tp", "fp", "fn", "tn"} <= set(cm) and cm["tp"] + cm["tn"] > cm["fp"] + cm["fn"]
    assert rs["label_mapping"] == {"0": 0, "1": 1}
    assert rs["convergence_warning"] is None
    assert "仅对照" in rs["accuracy_note"]
    assert "相关≠因果" in r["summary"]


def test_separable_triggers_warning():
    """完美可分（score>50 -> label=1）：AUC=1.0 且必须注明系数不稳定（规格场景）。"""
    r = _call(FIX / "binary_separable.csv", target="label", features=["score"])
    rs = r["result"]
    assert rs["roc_auc"] == 1.0
    assert rs["accuracy"] == 1.0
    assert rs["convergence_warning"] is not None
    assert "完美可分" in rs["convergence_warning"]


def test_odds_ratios_positive_and_sig():
    r = _call(FIX / "binary_noisy.csv", target="label", features=["score"])
    where = {o["name"]: o for o in r["result"]["odds_ratios"]}
    assert where["score"]["or"] > 1.0                  # score 越高越易 label=1
    assert where["score"]["significant"] is True
    assert where["const"]["or"] > 0


# ---------------- balanced 复制（手算对照） ----------------

def test_balanced_copying(tmp_path):
    """构造 60:10 不平衡训练数据 -> balanced 复制少数类。
    w = n_total/(2*n_minor)；训练(70%)：n_total'=49, n_minor'=7 -> w=49/14=3.5 -> round=4 -> 复制 3 份。"""
    rng = np.random.default_rng(3)
    n0, n1 = 60, 10
    x = np.concatenate([rng.normal(0, 1, n0), rng.normal(3, 1, n1)])
    y = np.array([0] * n0 + [1] * n1)
    p = tmp_path / "imb.csv"
    pd.DataFrame({"x": x, "label": y}).to_csv(p, index=False, encoding="utf-8-sig")
    r0 = _call(p, target="label", features=["x"], class_weight="balanced")
    rs = r0["result"]
    # 分层 70/30：训练 49 行（0 类 42、1 类 7）-> w=49/14=3.5 -> 复制 round(3.5)-1=2 份 ? 手算核对
    n1_tr = rs["class_distribution"]["train"]["1"]["n"]
    n0_tr = rs["class_distribution"]["train"]["0"]["n"]
    w = (n0_tr + n1_tr) / (2 * min(n0_tr, n1_tr))
    expected_copies = max(0, round(w) - 1) * min(n0_tr, n1_tr)
    assert rs["copied_rows"] == expected_copies
    assert rs["n_train_after_weight"] == n0_tr + n1_tr + expected_copies
    assert "复制" in rs["class_weight_note"]
    # none 时无复制
    r1 = _call(p, target="label", features=["x"], class_weight="none")
    assert r1["result"]["copied_rows"] == 0


# ---------------- 错误与边界 ----------------

def test_errors(tmp_path):
    assert "仅支持二分类" in logistic_regression(
        str(ROOT / "samples" / "clean.csv"), target="category",
        features=["age"])["message"]
    p1 = tmp_path / "one.csv"
    pd.DataFrame({"x": [1.0, 2, 3], "label": [1, 1, 1]}).to_csv(
        p1, index=False, encoding="utf-8-sig")
    assert "只有 1 个类别" in logistic_regression(
        str(p1), target="label", features=["x"])["message"]
    assert "test_size 必须在" in logistic_regression(
        str(FIX / "binary_noisy.csv"), target="label", features=["score"],
        test_size=0.0)["message"]
    assert "class_weight 仅支持" in logistic_regression(
        str(FIX / "binary_noisy.csv"), target="label", features=["score"],
        class_weight="sqrt")["message"]
    assert "不是数值列" in logistic_regression(
        str(ROOT / "samples" / "clean.csv"), target="category",
        features=["category"])["message"]
    assert "features 至少需要" in logistic_regression(
        str(FIX / "binary_noisy.csv"), target="label", features=[])["message"]
    assert logistic_regression(str(ROOT / "samples" / "nope.csv"), target="label",
                               features=["x"])["status"] == "error"


# ---------------- 可复现与 JSON ----------------

def test_deterministic_and_json_safe():
    r1 = _call(FIX / "binary_noisy.csv", target="label", features=["score"])
    json.dumps(r1, allow_nan=False, ensure_ascii=False)
    r2 = logistic_regression(str(FIX / "binary_noisy.csv"), target="label",
                             features=["score"])
    assert json.dumps(r1, sort_keys=True, ensure_ascii=False) == json.dumps(
        r2, sort_keys=True, ensure_ascii=False)
