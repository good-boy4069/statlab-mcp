# -*- coding: utf-8 -*-
"""tests/test_chi_square_test.py —— 工具 8 测试（规范 10）。

独立性：2x2 卡方手算硬编码（Σ(O-E)^2/E，Excel CHISQ.TEST 可复核）；
Cramér's V 手算公式对照。
"""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools.inference_chi_square_test import chi_square_test

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


def _call(p, **kw) -> dict:
    r = chi_square_test(str(p), **kw)
    assert r["status"] == "ok", r.get("message", r)
    return r


def _csv(tmp_path, a_list, b_list, ca="a", cb="b"):
    p = tmp_path / "c.csv"
    pd.DataFrame({ca: a_list, cb: b_list}).to_csv(p, index=False, encoding="utf-8-sig")
    return p


# ---------------- 手算对照：无关联 2x2 ----------------

def test_independent_2x2_hand_calculated(tmp_path):
    """[[10,15],[12,13]]：n=50；E=[[11,14],[11,14]]
    chi2=(1^2/11)+(1^2/14)+(1^2/11)+(1^2/14)=0.0909+0.0714+0.0909+0.0714=0.3247
    df=1；Cramér's V=sqrt(0.3247/(50*1))=0.0806"""
    p = _csv(tmp_path, ["X"] * 25 + ["Y"] * 25,
             ["1"] * 10 + ["2"] * 15 + ["1"] * 12 + ["2"] * 13)
    r = _call(p, col_a="a", col_b="b")
    rs = r["result"]
    assert rs["test_used"] == "chi_square"
    assert rs["statistic"] == pytest.approx(0.3247, abs=1e-3)
    assert rs["df"] == 1
    assert rs["p_value"] > 0.05
    assert rs["cramers_v"] == pytest.approx(0.0806, abs=1e-3)
    assert "不能拒绝 H0" in rs["conclusion"]
    assert "关联≠因果" in r["summary"]


def test_associated_2x2_significant(tmp_path):
    """[[20,5],[6,19]]：关联明显，p<0.05。"""
    p = _csv(tmp_path, ["X"] * 25 + ["Y"] * 25,
             ["1"] * 20 + ["2"] * 5 + ["1"] * 6 + ["2"] * 19)
    rs = _call(p, col_a="a", col_b="b")["result"]
    assert rs["test_used"] == "chi_square"
    assert rs["p_value"] < 0.05
    assert "拒绝 H0" in rs["conclusion"]


# ---------------- Fisher 切换 ----------------

def test_fisher_switch_2x2(tmp_path):
    """[[1,15],[4,20]]：n=40；期望最小值=5*19/40=2.375<5 且占 100%>20% -> Fisher。
    OR 与 p 以 scipy 输出为准；df=null。"""
    p = _csv(tmp_path, ["X"] * 16 + ["Y"] * 24,
             ["1"] * 16 + ["2"] * 0 + ["1"] * 4 + ["2"] * 20)
    # 修正构造：X 组 16 个（1 个"1"、15 个"2"），Y 组 24 个（4 个"1"、20 个"2"）
    p2 = tmp_path / "c2.csv"
    pd.DataFrame({"a": ["X"] * 16 + ["Y"] * 24,
                  "b": ["1"] + ["2"] * 15 + ["1"] * 4 + ["2"] * 20}).to_csv(
        p2, index=False, encoding="utf-8-sig")
    r = _call(p2, col_a="a", col_b="b")
    rs = r["result"]
    assert rs["test_used"] == "fisher_exact"
    assert rs["df"] is None
    assert rs["p_value"] > 0.05                    # 期望频数低 -> Fisher p 保守
    assert "Fisher" in r["summary"]          # summary 在顶层（result 无 summary）


def test_fisher_rejected_for_larger_table(tmp_path):
    """非 2x2 且期望过低 -> 中文报错引导合并类别。"""
    p = _csv(tmp_path, ["X"] * 7 + ["Y"] * 33 + ["Z"] * 6,
             ["1"] * 40 + ["2"] * 6)
    r = chi_square_test(str(p), col_a="a", col_b="b")
    assert r["status"] == "error" and "合并类别" in r["message"]


# ---------------- 数值列分箱 ----------------

def test_numeric_col_auto_binned(tmp_path):
    """数值列分箱：箱内样本充足（n=400 -> 每格期望 ~25）时正常走卡方并注明分箱。
    注：样本过小时（如 60 行分 8 箱 -> 期望≈4<5）会按规格触发"期望过低"规则，属正确行为。"""
    import numpy as np
    vals = np.arange(400, dtype=float)
    p = _csv(tmp_path, vals.tolist(), ["红"] * 200 + ["蓝"] * 200)
    r = _call(p, col_a="a", col_b="b")
    rs = r["result"]
    assert rs["test_used"] == "chi_square"
    assert rs["binning_note"] is not None and "分箱" in rs["binning_note"]
    rows = len(rs["contingency_table"])
    assert 2 <= rows <= 8                          # 等宽分箱 ≤8 箱


# ---------------- 错误与边界 ----------------

def test_errors(tmp_path):
    p = _csv(tmp_path, ["A"] * 5, ["B"] * 5)
    assert "缺少必需列" in chi_square_test(str(p), col_a="nope", col_b="b")["message"]
    p1 = _csv(tmp_path, ["A"] * 10, ["B"] * 10)
    assert "只有 1 个类别" in chi_square_test(str(p1), col_a="a", col_b="b")["message"]
    many = [f"c{i}" for i in range(51)]
    p2 = _csv(tmp_path, many + ["X"] * 10, (["B", "C", "D"] * 21)[:61])
    r = chi_square_test(str(p2), col_a="a", col_b="b")
    assert r["status"] == "error" and "超过 50 个" in r["message"]
    assert chi_square_test(str(SAMPLES / "nope.csv"), col_a="a", col_b="b")["status"] == "error"


def test_clean_category_pair_ok(tmp_path):
    """均衡 2x2（每格期望 25>=5）正常走卡方；clean.csv 的 3x3 稀疏表按规格报错属正确行为。"""
    p = _csv(tmp_path, ["X"] * 50 + ["Y"] * 50,
             (["1"] * 25 + ["2"] * 25) * 2)
    r = _call(p, col_a="a", col_b="b")
    assert r["result"]["test_used"] == "chi_square"
    assert r["result"]["n"] == 100


def test_json_safe_and_deterministic(tmp_path):
    p = _csv(tmp_path, ["X"] * 50 + ["Y"] * 50,
             (["1"] * 25 + ["2"] * 25) * 2)
    r1 = _call(p, col_a="a", col_b="b")
    json.dumps(r1, allow_nan=False, ensure_ascii=False)
    r2 = chi_square_test(str(p), col_a="a", col_b="b")
    assert json.dumps(r1, sort_keys=True, ensure_ascii=False) == json.dumps(
        r2, sort_keys=True, ensure_ascii=False)