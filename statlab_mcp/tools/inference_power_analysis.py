"""power_analysis —— 统计推断组 · 功效分析/样本量计算（工具 27，v1.1.0 新增）。

回答两类问题：「要检出效应量，需要多少样本」与「给定样本量能检出多大效应 / 实际功效多少」。
纯封闭公式计算（statsmodels.stats.power 精确非中心 t / 正态近似），零 LLM、确定性输出。

docstring = agent 使用说明书，与 statlab_mcp/docs/design/10_power_analysis.md 同步维护。

参数:
    scenario (str): one_sample_t（单样本/配对 t，n=总样本）/ two_sample_t（独立两样本
        t，n=每组样本量）/ two_proportions（两独立比例，n=每组样本量）
    effect_size (float|None): Cohen's d（仅 t 系场景）；与 n 至少提供一个；必须 >0 的有限数
    n (int|None): 样本量；与 effect_size 至少提供一个；必须是 >=2 的整数
    p1 (float|None), p2 (float|None): 两个总体比例 ∈(0,1)，仅 two_proportions 场景且须成对；
        工具内部换算 Cohen's h = 2·arcsin√p₁ − 2·arcsin√p₂ 并随 result/summary 报告
    alpha (float, 0.05): 显著性水平 ∈(0,1)
    power_target (float, 0.80): 目标功效（求 n 时使用）∈(0,1)
    alternative (str, "two_sided"): two_sided / less / greater

模式决策表（任务书钉死）:
    只给效应侧 → mode="solve_n"（求 n_required_exact 与 n_recommended=向上取整）
    只给 n    → mode="detect_effect"（可检出标准化效应）
    都给      → mode="verify"（返回实际 power 验算结果）
    都不给    → E1001 中文报错

返回: 成功 {"status":"ok","result":{...},"summary":"..."}；
    result 含 scenario/n_each/n_total 及各模式专属字段；两比例场景另报 cohens_h。
局限声明（固定附在 summary 末尾）：功效计算依赖效应量假设，实际效应量未知时结论仅供参考。

示例:
    power_analysis("two_sample_t", effect_size=0.5)                 # 经典配置 → 64/组
    power_analysis("one_sample_t", n=34)                            # 反查可检出的 d
    power_analysis("two_proportions", p1=0.50, p2=0.80, n=100)      # verify 实际功效
"""
import math
import warnings
from typing import Any

from statlab_mcp.tools._common import EC, DataLabError, err, ok

_SCENARIOS = ("one_sample_t", "two_sample_t", "two_proportions")
_ALTERNATIVES = {"two_sided": "two-sided", "less": "smaller", "greater": "larger"}
_TailNote = {"two_sided": "双侧", "less": "单侧（检出较低方向）",
             "greater": "单侧（检出较高方向）"}


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _cohens_h(p1: float, p2: float) -> float:
    """Cohen's h（Arcsine 变换差，Cohen 1988 §6.2.1）：2·arcsin√p₁ − 2·arcsin√p₂。"""
    return 2.0 * math.asin(math.sqrt(p1)) - 2.0 * math.asin(math.sqrt(p2))


def power_analysis(scenario: str, effect_size: float | None = None,
                   n: int | None = None, p1: float | None = None,
                   p2: float | None = None, alpha: float = 0.05,
                   power_target: float = 0.80,
                   alternative: str = "two_sided") -> dict:
    """功效分析主入口：solve_n / detect_effect / verify 三模式。"""
    try:
        # ---- 参数校验（全部 E1001 家族；NaN/Inf 一律拒绝）----
        if scenario not in _SCENARIOS:
            raise DataLabError(f"scenario 仅支持 {'/'.join(_SCENARIOS)}", EC.PARAM)
        if not _is_number(alpha) or not math.isfinite(alpha) or not (0 < alpha < 1):
            raise DataLabError("alpha 必须为 (0,1) 内的有限数", EC.PARAM)
        if not _is_number(power_target) or not math.isfinite(power_target) \
                or not (0 < power_target < 1):
            raise DataLabError("power_target 必须为 (0,1) 内的有限数", EC.PARAM)
        if alternative not in _ALTERNATIVES:
            raise DataLabError(
                f"alternative 仅支持 {'/'.join(sorted(_ALTERNATIVES))}", EC.PARAM)
        if n is not None and (isinstance(n, bool) or not isinstance(n, int) or n < 2):
            raise DataLabError("n 必须是 >=2 的整数", EC.PARAM)

        props_pair_given = p1 is not None and p2 is not None
        if scenario == "two_proportions":
            if effect_size is not None:
                raise DataLabError(
                    "two_proportions 场景以 p1/p2 为效应输入，不接受 effect_size", EC.PARAM)
            if props_pair_given != (p1 is not None or p2 is not None):
                raise DataLabError(
                    "two_proportions 场景必须成对提供 p1 与 p2", EC.PARAM)
            for name, v in (("p1", p1), ("p2", p2)):
                if v is not None and (not _is_number(v) or not math.isfinite(v)
                                      or not (0 < v < 1)):
                    raise DataLabError(f"{name} 必须为 (0,1) 之间的有限数", EC.PARAM)
        else:
            if p1 is not None or p2 is not None:
                raise DataLabError(
                    "p1/p2 仅适用于 two_proportions 场景；t 检验系列请提供 effect_size",
                    EC.PARAM)
            if effect_size is not None and (
                    not _is_number(effect_size) or not math.isfinite(effect_size)
                    or effect_size <= 0):
                raise DataLabError(
                    "effect_size 必须为 >0 的有限数（拒绝 NaN/Inf/0/负数）", EC.PARAM)

        # ---- 模式决策表 ----
        es_ready = (p1 is not None and p2 is not None) if scenario == "two_proportions" \
            else effect_size is not None
        if es_ready and n is not None:
            mode = "verify"
        elif es_ready:
            mode = "solve_n"
        elif n is not None:
            mode = "detect_effect"
        else:
            raise DataLabError(
                "缺少必需参数：请至少提供「效应量（effect_size 或成对的 p1/p2）」或"
                "「n」其一；两者同给则输出实际功效验算", EC.PARAM)

        # ---- 引擎（延迟导入，P1-1 清单内库）----
        from statsmodels.stats.power import NormalIndPower, TTestIndPower, TTestPower

        h: float | None = None
        d_eff: float | None = None
        if scenario == "one_sample_t":
            engine, ind_like = TTestPower(), False
        elif scenario == "two_sample_t":
            engine, ind_like = TTestIndPower(), True
        else:
            engine, ind_like = NormalIndPower(), True
            if props_pair_given:
                h = _cohens_h(float(p1), float(p2))
                d_eff = abs(h)

        if scenario != "two_proportions" and es_ready:
            d_eff = abs(float(effect_size))

        sm_alt = _ALTERNATIVES[alternative]

        def _solve(*, es: float | None, nobs: int | None, tgt: float | None,
                   root: bool) -> float:
            """统一调用 statsmodels。

            - ind_like 场景用 nobs1/ratio=1 的两组口径；
            - 单侧求根做「方向归一」：statsmodels 对符号×方向不匹配的求根会静默
              返回垃圾解并伴随 Failed to converge 警告（上游已知缺陷）。本工具将
              less/greater 的求根统一镜像为 (带符号 es, alternative='larger')，
              数值上完全等价；verify 只算 power 不走求根，各方向均直接可用；
            - 求根过程中出现未收敛警告或非有限值 → 抛 RuntimeError → 兜底 E9999
              如实报错（防幻觉：宁可报错也不输出可疑数字）。
            """
            use_alt, use_es = sm_alt, es
            if root and sm_alt in ("smaller", "larger"):
                # 方向归一：less(检出较低 d) ≡ (effect=-d, 'larger')；
                # greater(检出较高 d) ≡ (effect=+d, 'larger')
                use_alt = "larger"
                if es is not None:
                    use_es = -es if sm_alt == "smaller" else es
            try:
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    if ind_like:
                        val = engine.solve_power(
                            effect_size=use_es, nobs1=nobs, alpha=alpha, power=tgt,
                            ratio=1.0, alternative=use_alt)
                    else:
                        val = engine.solve_power(
                            effect_size=use_es, nobs=nobs, alpha=alpha, power=tgt,
                            alternative=use_alt)
                diverged = any("Failed to converge" in str(w.message)
                               for w in caught)
            except Exception as exc:                     # 上游抛错 → 统一兜底文案
                raise RuntimeError(f"solve_power 失败: {exc}") from exc
            fv = float(val)
            if diverged or not math.isfinite(fv):
                raise RuntimeError(
                    f"solve_power 未收敛（direction={sm_alt}, root={root}），"
                    "已拒绝该可疑结果")
            return fv

        base: dict[str, Any] = {
            "mode": mode,
            "scenario": scenario,
            "alternative": alternative,
            "alpha": float(alpha),
            "n_each": int(n) if (ind_like and n is not None) else None,
            "n_total": (int(n) if not ind_like else 2 * int(n)) if n is not None else None,
        }

        tail_note: str
        eff_disp: str
        if mode == "solve_n":
            exact = _solve(es=d_eff, nobs=None, tgt=float(power_target), root=True)
            if not math.isfinite(exact) or exact <= 0:
                raise DataLabError("该参数组合下无法求解有效样本量，请调整后重试", EC.CALC)
            base.update({"power_target": float(power_target),
                         "n_required_exact": exact,
                         "n_recommended": math.ceil(exact)})
            eff_disp = f"|h|={d_eff:.4f}" if scenario == "two_proportions" \
                else f"d={d_eff:.4f}"
            tail_note = (f"{_TailNote[alternative]} α={alpha:g}，目标功效 "
                         f"{power_target:g}，所需样本量 ≈ {math.ceil(exact)}"
                         f"{'（每组）' if ind_like else ''}（效应量 {eff_disp}）")
        elif mode == "detect_effect":
            detected = abs(_solve(es=None, nobs=int(n), tgt=float(power_target), root=True))
            if not math.isfinite(detected) or detected <= 0:
                raise DataLabError("该参数组合下无法求解可检出效应量，请调整后重试", EC.CALC)
            base.update({"power_target": float(power_target)})
            label = "detectable_cohens_h_abs" if scenario == "two_proportions" \
                else "detectable_effect_size"
            base[label] = detected
            tail_note = (f"{_TailNote[alternative]} α={alpha:g}，样本量 {int(n)}"
                         f"{'（每组）' if ind_like else ''}、目标功效 {power_target:g}"
                         f"时可检出的最小标准化效应 ≈ {detected:.3f}")
        else:                                            # verify
            actual = min(max(_solve(es=d_eff, nobs=int(n), tgt=None, root=False), 0.0), 1.0)
            if not math.isfinite(actual):
                raise DataLabError("该参数组合下无法验算功效，请检查输入", EC.CALC)
            base.update({"power_actual": actual})
            eff_disp = f"|h|={d_eff:.4f}" if scenario == "two_proportions" \
                else f"d={d_eff:.4f}"
            tail_note = (f"{_TailNote[alternative]} α={alpha:g}，n={int(n)}，"
                         f"{eff_disp} 下的实际功效 ≈ {actual:.4f}")

        summary_parts = [f"{scenario} 功效分析（{mode}）", tail_note]
        if scenario == "two_proportions" and h is not None:
            base.update({"p1": float(p1), "p2": float(p2), "cohens_h": h,
                         "cohens_h_abs": abs(h)})
            summary_parts.append(f"Cohen's h={h:+.4f}（p1={p1:g}, p2={p2:g}）")
        summary_parts.append("局限声明：功效计算依赖效应量假设，"
                             "实际效应量未知时结论仅供参考")
        return ok(base, "；".join(summary_parts))
    except DataLabError as e:
        return err(e.code, str(e))
    except Exception:
        return err(EC.CALC, "计算失败，请检查数据内容与参数设置（详见服务端日志）")


def register(mcp) -> None:
    """注册到 MCPServer（mcp 2.x，工具名 = 函数名）。"""
    mcp.add_tool(power_analysis, description=__import__("sys").modules[__name__].__doc__)
