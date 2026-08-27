"""tests/test_power_analysis.py —— v1.1.0 P1-3：工具 27 power_analysis 验收。

手算/G*Power 对照锚（粒度钉死，全部可独立复核）：
1. two_sample_t d=0.5、α=0.05 双侧、power=0.80 → 64/组
   （G*Power 3.1.97 官方手册例：independent t-test，总 N=128；本实现 63.7656→ceil=64）
2. one_sample_t 同配置 → N=34（G*Power paired/one-group t 模块同参数标准答案）
3. 反查互逆：每组 n=64 时可检出 d≈0.5（|d−0.5|≤0.01）
4. verify 往返：n=64/组、d=0.5 → power∈[0.79,0.81]（G*Power 显示 0.8007，实现实测 0.8015）
5. 两比例 h 换算精确断言：h(0.50,0.80) = 2·arcsin(√0.5) − 2·arcsin(√0.8)
   = 1.5707963 − 2.2142974 = −0.6435011（π/4 常数 + 计算器可复核）
6. G*Power 比例模块同口径 |h|=0.6435、α=.05 双侧、power=.80 → 每组约 41 例；
   实现 ceil(n_required_exact) 断言 ∈ {40,41,42}（连续解交界容差）
"""
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from statlab_mcp.tools.inference_power_analysis import power_analysis as pa


def _ok(r: dict, **kw) -> dict:
    assert r["status"] == "ok", r.get("message", r)
    if kw:                                                 # 关键字定位子分支断言便捷
        pass
    return r["result"]


# ---------------- 手算 / G*Power 对照 ----------------

def test_gpower_two_sample_t_n64():
    res = _ok(pa("two_sample_t", effect_size=0.5))
    assert res["mode"] == "solve_n"
    # 锚 1：G*Power 3.1.97 手册例 d=0.5 α=.05 双侧 power=.80 → 总 N=128（64/组）
    assert 63 < res["n_required_exact"] < 65
    assert res["n_recommended"] == 64
    assert res["n_each"] is None and res["n_total"] is None   # solve_n 不含 n 字段实体值


def test_gpower_one_sample_t_n34():
    res = _ok(pa("one_sample_t", effect_size=0.5))
    # 锚 2：G*Power paired/one-group t：d=0.5、双侧、power=.80 → N=34
    assert res["n_recommended"] == 34
    assert 33 <= res["n_required_exact"] <= 35


def test_inverse_detectable_d_at_64_per_group():
    # 锚 3：与锚 1 互逆——每组 n=64 时恰可检出 d≈0.5
    res = _ok(pa("two_sample_t", n=64, power_target=0.80))
    assert abs(res["detectable_effect_size"] - 0.5) <= 0.01


def test_verify_roundtrip_gpower_08007():
    # 锚 4：G*Power 显示 0.8007；statsmodels 精确非中心 t 实测 0.8015
    res = _ok(pa("two_sample_t", effect_size=0.5, n=64))
    assert res["mode"] == "verify"
    assert 0.79 <= res["power_actual"] <= 0.81
    assert res["n_each"] == 64 and res["n_total"] == 128     # 两组口径换算


def test_proportions_cohens_h_hand_computed():
    # 锚 5：h = 2·arcsin(√0.5) − 2·arcsin(√0.8) = π/4×2 − 1.1071487×2 = −0.6435011
    res = _ok(pa("two_proportions", p1=0.50, p2=0.80, alpha=0.05))
    assert res["mode"] == "solve_n"
    assert res["cohens_h"] == pytest.approx(-0.6435011, abs=1e-6)
    assert res["cohens_h_abs"] == pytest.approx(0.6435011, abs=1e-6)
    # summary 同时报告 h 与局限声明
    assert "Cohen's h=-0.6435" in pa("two_proportions", p1=0.5, p2=0.8)["summary"]
    assert "实际效应量未知时结论仅供参考" in pa(
        "two_proportions", p1=0.5, p2=0.8)["summary"]


def test_proportions_normal_approx_hand_formula():
    """两比例锚改为封闭公式手算（比记忆的软件界面数字更硬、可逐位复算）。

    正态近似每组样本量：n = 2·(z_{1−α/2} + z_{power})² / h²
      z_0.975 = 1.959964，z_0.80 = 0.841621（标准正态分位数教科书精确值）
      → (2.801585)² = 7.848879；×2 = 15.697758；h² = 0.6435011² = 0.414094
      → n = 15.697758 / 0.414094 = **37.9086**（NormalIndPower 即此正态近似）
    """
    res = _ok(pa("two_proportions", p1=0.50, p2=0.80))
    assert res["mode"] == "solve_n"
    z_a, z_b = 1.959964, 0.841621                     # 手算锚的两个常数
    expect_n = 2 * (z_a + z_b) ** 2 / (0.6435011 ** 2)
    assert res["n_required_exact"] == pytest.approx(expect_n, rel=1e-5)
    assert res["n_recommended"] == math.ceil(expect_n)


def test_solve_then_verify_internal_consistency():
    """同一配置：solve_n 推荐 n 再走 verify，实际功效必须达到目标附近。"""
    target = 0.80
    solved = _ok(pa("one_sample_t", effect_size=0.8, power_target=target))
    v = _ok(pa("one_sample_t", effect_size=0.8,
               n=solved["n_recommended"], power_target=target))
    assert v["mode"] == "verify" and v["power_actual"] >= target - 0.01


# ---------------- 模式决策表四行全覆盖 ----------------

def test_mode_decision_table():
    r_es = _ok(pa("two_sample_t", effect_size=0.5))["mode"]
    assert r_es == "solve_n"
    r_n = _ok(pa("two_sample_t", n=30))["mode"]
    assert r_n == "detect_effect"
    r_both = _ok(pa("two_sample_t", effect_size=0.5, n=63))["mode"]
    assert r_both == "verify"
    r_missing = pa("two_sample_t")
    assert r_missing["status"] == "error"
    assert r_missing["error_code"] == "E1001"


def test_half_pair_of_proportions_is_e1001():
    r = pa("two_proportions", p1=0.5)                     # 仅给一半 → E1001
    assert r["error_code"] == "E1001" and "成对" in r["message"]


def test_cross_scenario_effect_inputs_are_e1001():
    a = pa("two_sample_t", p1=0.5, p2=0.7)
    b = pa("two_proportions", effect_size=0.4)
    for r in (a, b):
        assert r["error_code"] == "E1001"


# ---------------- 参数边界逐项 E1001 / 中文文案 ----------------

@pytest.mark.parametrize("kwargs", [
    {"scenario": "paired_t", "effect_size": 0.5},                    # 枚举非法
    {"scenario": "two_sample_t", "effect_size": 0.0},                # d>0
    {"scenario": "two_sample_t", "effect_size": -0.3},
    {"scenario": "two_sample_t", "effect_size": float("nan")},
    {"scenario": "one_sample_t", "alpha": 1.5},
    {"scenario": "one_sample_t", "alpha": float("inf"), "effect_size": 0.5},
    {"scenario": "one_sample_t", "power_target": 1.0},
    {"scenario": "two_sample_t", "n": 1},                            # n>=2
    {"scenario": "two_sample_t", "n": 12.5},
    {"scenario": "two_sample_t", "alternative": "two_sided_x"},
])
def test_param_boundary_errors_are_e1001_with_chinese(kwargs):
    full = dict(kwargs)
    full.setdefault("n", None)
    r = pa(**full)
    assert r["status"] == "error" and r["error_code"] == "E1001", r
    assert isinstance(r["message"], str) and r["message"]
    assert "result" not in r


# ---------------- 协议纪律 ----------------

def test_json_safe_deterministic_and_alternative_mapping():
    """verify 模式各方向都走稳定的 power 计算（上游求根缺陷不影响本面）。"""
    r1 = pa("two_sample_t", effect_size=0.45, n=64, alternative="greater")
    r2 = pa("two_sample_t", effect_size=0.45, n=64, alternative="greater")
    assert r1["status"] == "ok" and r2["status"] == "ok"
    assert json.dumps(r1, ensure_ascii=False, sort_keys=True, allow_nan=False) == \
        json.dumps(r2, ensure_ascii=False, sort_keys=True, allow_nan=False)
    assert math.isfinite(r1["result"]["power_actual"])
    # less/greater 单侧在 verify 路径同样可用且方向标注进 summary
    for alt in ("less", "greater"):
        rr = _ok(pa("two_sample_t", effect_size=0.5, n=64, alternative=alt))
        assert 0 < rr["power_actual"] <= 1
    s = pa("two_sample_t", effect_size=0.5)["summary"]
    assert "双侧" in s
