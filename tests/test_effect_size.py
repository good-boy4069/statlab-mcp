"""tests/test_effect_size.py —— 工具 11 测试（规范 10）。

独立性：d/CI 手算硬编码（pooled 公式、正态近似 se 公式，Excel 可复核）；
cliff_delta 手数比较对计数。
"""
import json
import math
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools.inference_effect_size import effect_size

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


def _call(p, **kw) -> dict:
    r = effect_size(str(p), **kw)
    assert r["status"] == "ok", r.get("message", r)
    return r


def _csv(tmp_path, g_list, v_list, cg="g", cv="v"):
    p = tmp_path / "e.csv"
    pd.DataFrame({cg: g_list, cv: v_list}).to_csv(p, index=False, encoding="utf-8-sig")
    return p


# ---------------- cohens_d 手算对照 ----------------

def test_cohens_d_hand_calculated(tmp_path):
    """x=[1..5] y=[2,4,6,8,10]：pooled_sd=sqrt((4*2.5+4*10)/8)=2.5
    d=|3-6|/2.5=1.2；se=sqrt(1/5+1/5+1.44/20)=sqrt(0.472)=0.687024
    CI=1.2±1.96*0.687024=[−0.14657, 2.54657]"""
    p = _csv(tmp_path, ["A"] * 5 + ["B"] * 5, [1, 2, 3, 4, 5, 2, 4, 6, 8, 10])
    r = _call(p, group_col="g", value_col="v")
    rs = r["result"]
    assert rs["method"] == "cohens_d" and rs["paired"] is False
    assert rs["effect_size"] == pytest.approx(1.2)
    se = math.sqrt(0.472)
    assert rs["ci_lower"] == pytest.approx(1.2 - 1.959964 * se, abs=1e-6)
    assert rs["ci_upper"] == pytest.approx(1.2 + 1.959964 * se, abs=1e-6)
    assert rs["mean1"] == pytest.approx(3.0) and rs["mean2"] == pytest.approx(6.0)
    assert rs["interpretation"]["label"] == "大"


def test_hedges_g_correction(tmp_path):
    """g = d*(1-3/(4*10-9)) = 1.2*(1-3/31) = 1.0838709677"""
    p = _csv(tmp_path, ["A"] * 5 + ["B"] * 5, [1, 2, 3, 4, 5, 2, 4, 6, 8, 10])
    rs = _call(p, group_col="g", value_col="v", method="hedges_g")["result"]
    assert rs["effect_size"] == pytest.approx(1.2 * (1 - 3 / 31), abs=1e-9)


# ---------------- cliff_delta 手算对照 ----------------

def test_cliff_delta_hand_counted(tmp_path):
    """x=[1,2], y=[1,3]：四对 (1,1)=0 (1,3)=-1 (2,1)=+1 (2,3)=-1 -> sum=-1
    delta = -1/4 = -0.25"""
    p = _csv(tmp_path, ["A"] * 2 + ["B"] * 2, [1, 2, 1, 3])
    rs = _call(p, group_col="g", value_col="v", method="cliff_delta")["result"]
    assert rs["effect_size"] == pytest.approx(-0.25)
    assert rs["interpretation"]["label"] == "小"


def test_cliff_delta_constant_groups_defined(tmp_path):
    """外部评审 M4 盲区：两组全常量数据 cliff_delta 有明确定义
    （x=[1,1,1], y=[2,2,2] 全部 x<y -> delta=-1.0），不得误报"合并方差为 0"。"""
    p = _csv(tmp_path, ["A"] * 3 + ["B"] * 3, [1, 1, 1, 2, 2, 2])
    r = _call(p, group_col="g", value_col="v", method="cliff_delta")
    rs = r["result"]
    assert rs["effect_size"] == pytest.approx(-1.0)
    assert rs["interpretation"]["label"] == "大"            # |−1.0| ≥ 0.474
    # 对照组：cohens_d 对同数据应正确拒绝（pooled=0）
    p2 = _csv(tmp_path, ["A"] * 3 + ["B"] * 3, [1, 1, 1, 2, 2, 2])
    r2 = effect_size(str(p2), group_col="g", value_col="v")
    assert r2["status"] == "error" and "合并方差为 0" in r2["message"]


def test_cliff_delta_negative_large_label(tmp_path):
    """外部评审 M5 盲区：负向大效应 |delta|=0.75 档位必须按 |v| 判定为"大"
    （x=[1,2], y=[2,3]：gt=0, lt=3 -> delta=-0.75）。"""
    p = _csv(tmp_path, ["A"] * 2 + ["B"] * 2, [1, 2, 2, 3])
    rs = _call(p, group_col="g", value_col="v", method="cliff_delta")["result"]
    assert rs["effect_size"] == pytest.approx(-0.75)
    assert rs["interpretation"]["label"] == "大"


# ---------------- paired（简化语义） ----------------

def test_paired_diff_effect(tmp_path):
    """x=[1..5] y=[2,4,5,4,5]：diff=[-1,-2,-2,0,0] mean=-1 sd=1 -> d=1.0"""
    p = tmp_path / "e2.csv"
    pd.DataFrame({"m": ["前"] * 5 + ["后"] * 5,
                  "v": [1, 2, 3, 4, 5, 2, 4, 5, 4, 5]}).to_csv(p, index=False,
                                                              encoding="utf-8-sig")
    rs = _call(p, group_col="m", value_col="v", paired=True)["result"]
    assert rs["paired"] is True
    assert rs["effect_size"] == pytest.approx(1.0)


# ---------------- 错误与边界 ----------------

def test_errors(tmp_path):
    p1 = _csv(tmp_path, ["A"] * 5, [1, 2, 3, 4, 5])
    assert "只支持恰好 2 组" in effect_size(str(p1), group_col="g", value_col="v")["message"]
    p2 = _csv(tmp_path, ["A"] * 5 + ["B"] * 1, [0, 1, 2, 3, 4, 5.0])
    assert "样本量不足 2" in effect_size(str(p2), group_col="g", value_col="v")["message"]
    assert "method 仅支持" in effect_size(str(SAMPLES / "clean.csv"), group_col="category",
                                           value_col="score", method="eta2")["message"]
    assert "缺少必需列" in effect_size(str(SAMPLES / "clean.csv"), group_col="category",
                                        value_col="nope")["message"]
    assert "不是数值列" in effect_size(str(SAMPLES / "clean.csv"), group_col="category",
                                        value_col="category")["message"]
    # paired 不等数
    p3 = _csv(tmp_path, ["A"] * 4 + ["B"] * 6, list(range(10)))
    r = effect_size(str(p3), group_col="g", value_col="v", paired=True)
    assert r["status"] == "error" and "样本数相等" in r["message"]
    # paired + cliff_delta（用 2 组数据）
    p4 = _csv(tmp_path, ["A"] * 5 + ["B"] * 5, [1, 2, 3, 4, 5, 2, 4, 6, 8, 10])
    r2 = effect_size(str(p4), group_col="g", value_col="v",
                     method="cliff_delta", paired=True)
    assert r2["status"] == "error" and "不支持配对" in r2["message"]
    assert effect_size(str(SAMPLES / "nope.csv"), group_col="g", value_col="v")["status"] == "error"


def test_clean_two_groups_ok(tmp_path):
    """clean.csv 取 A/B 两组（人工子集）可跑。"""
    df = pd.read_csv(SAMPLES / "clean.csv", encoding="utf-8-sig")
    sub = df[df["category"].isin(["A", "B"])].copy()
    p = tmp_path / "ab.csv"
    sub.to_csv(p, index=False, encoding="utf-8-sig")
    r = _call(p, group_col="category", value_col="score")
    assert 0 < r["result"]["effect_size"] < 1


def test_json_safe_and_deterministic(tmp_path):
    p = _csv(tmp_path, ["A"] * 5 + ["B"] * 5, [1, 2, 3, 4, 5, 2, 4, 6, 8, 10])
    r1 = _call(p, group_col="g", value_col="v")
    json.dumps(r1, allow_nan=False, ensure_ascii=False)
    r2 = effect_size(str(p), group_col="g", value_col="v")
    assert json.dumps(r1, sort_keys=True, ensure_ascii=False) == json.dumps(
        r2, sort_keys=True, ensure_ascii=False)
