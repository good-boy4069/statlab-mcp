"""seasonal_decompose —— 时序组 · 季节分解（工具 18，简化实现）。

docstring = agent 使用说明书，与 statlab_mcp/docs/design/06_timeseries.md 同步维护。

参数:
    file_path (str): 本地数据文件（csv/tsv/xlsx/json）
    date_col / value_col (str): 日期列与数值列
    period (int|None, None): 周期；默认 FFT 主频自动估计（_common._estimate_period）
    model (str, "auto"): additive / multiplicative / auto
        auto: 全正值 -> multiplicative，否则 additive（注明选择依据）

口径:
    statsmodels.seasonal_decompose(extrapolate_trend="freq")；
    multiplicative 要求全正值（显式指定且含非正值 -> 中文报错）。
    输出分量统计 + 最后完整周期季节因子 + 4 子图（__image__ 顶层）。

示例:
    seasonal_decompose("samples/timeseries.csv", date_col="date", value_col="value")
inline 数据:
    本工具支持可选 inline_data 参数（v1.2.0 起）：与 file_path 二选一，
    支持 records 数组或 {"header": [...], "rows": [[...], ...]} 对象两种形态；
    规模上限/类型域/data_source 来源标注见 statlab_mcp/docs/SPEC.md 第 12 节。

"""

import numpy as np
from matplotlib import pyplot as plt

from statlab_mcp.tools._common import (
    CJK_FONT_OK,
    EC,
    DataLabError,
    _estimate_period,
    _prepare_series,
    err,
    ok,
    require_non_none,
    resolve_data,
    save_plot,
)

MIN_N = 15
_MODELS = {"additive", "multiplicative", "auto"}


def seasonal_decompose(file_path: str | None = None, date_col: str | None = None, value_col: str | None = None,
                       period: int | None = None, model: str = "auto",
                   inline_data: list | dict | None = None) -> dict:
    """时间序列分解：趋势 + 季节 + 残差（含周期自动估计与 4 子图）。"""
    try:
        # D17 连锁 optional 化的运行期强校验（SPEC §12.6）
        require_non_none(date_col=date_col, value_col=value_col)
        if model not in _MODELS:
            raise DataLabError("model 仅支持 additive/multiplicative/auto", EC.PARAM)
        if period is not None:
            if isinstance(period, bool) or not isinstance(period, (int, np.integer)):
                raise DataLabError("period 必须是整数", EC.PARAM)
            period = int(period)
        df, data_source = resolve_data(file_path, inline_data)
        y, meta = _prepare_series(df, date_col, value_col)
        n = int(y.size)
        if n < MIN_N:
            raise DataLabError(f"样本过短（n={n}<{MIN_N}），时序分析不可靠", EC.INSUFFICIENT)
        yv = y.dropna()

        # ---- 周期决定 ----
        if period is None:
            period = _estimate_period(yv)
            if period is None:
                raise DataLabError("无法估计周期，请显式指定 period", EC.INSUFFICIENT)
            period_note = f"周期由 FFT 自动估计 = {period}"
        else:
            if not (2 <= period <= n // 2):
                raise DataLabError(f"period 必须在 2 到 n/2 之间（n/2={n // 2}）", EC.PARAM)
            period_note = f"周期为指定值 {period}"

        # ---- 模型决定 ----
        all_positive = bool((yv > 0).all())
        model_note = None
        if model == "auto":
            model_used = "multiplicative" if all_positive else "additive"
            if not all_positive:
                model_note = "含非正值，已改用 additive"
        else:
            model_used = model
            if model_used == "multiplicative" and not all_positive:
                raise DataLabError("乘法分解要求全正值，请改用 additive", EC.STRUCTURE)

        # ---- 分解 ----
        from statsmodels.tsa.seasonal import seasonal_decompose as sm_decompose  # 延迟导入（P1-1）
        result_decomp = sm_decompose(yv, model=model_used, period=period,
                                     extrapolate_trend="freq")
        trend = result_decomp.trend
        season = result_decomp.seasonal
        resid = result_decomp.resid

        # 幅度取中段（首尾各去掉 period//2：规避趋势外推的边缘效应）
        mid = season.iloc[period // 2: -period // 2] if period // 2 > 0 else season
        amplitude = float(mid.max() - mid.min())
        components = {
            "trend": {"mean": float(trend.mean()) if trend.notna().any() else None,
                      "last": float(trend.dropna().iloc[-1]) if trend.notna().any() else None},
            "seasonal": {"mean": float(season.mean()), "last": float(season.iloc[-1]),
                         "amplitude": amplitude},
            "resid": {"mean": float(resid.mean()) if resid.notna().any() else None,
                      "std": float(resid.std(ddof=1)) if resid.notna().sum() > 1 else None,
                      "n_nan": int(resid.isna().sum())},
        }
        season_factors = [float(v) for v in season.iloc[-period:].tolist()]

        # ---- 图（4 子图）----
        t = yv.index
        fig, axes = plt.subplots(4, 1, figsize=(9, 8), sharex=True)
        axes[0].plot(t, yv.values, lw=0.8)
        axes[0].set_title("原值" if CJK_FONT_OK else "Observed")
        axes[1].plot(t, trend.values, lw=0.8, color="C1")
        axes[1].set_title("趋势" if CJK_FONT_OK else "Trend")
        axes[2].plot(t, season.values, lw=0.8, color="C2")
        axes[2].set_title("季节" if CJK_FONT_OK else "Seasonal")
        axes[3].plot(t, resid.values, lw=0.8, color="C3")
        axes[3].set_title("残差" if CJK_FONT_OK else "Residual")
        fig.tight_layout()
        img = save_plot(fig, "seasonal_decompose_all")

        summary = (f"{model_used} 分解（{period_note}）：趋势 "
                   f"{components['trend']['mean']:.2f}（末端 {components['trend']['last']:.2f}），"
                   f"季节幅度 {amplitude:.2f}，残差 σ={components['resid']['std']:.2f}")
        if model_note:
            summary += f"；{model_note}"
        if meta["interpolated"]:
            summary += f"；已插值 {meta['interpolated']} 个缺失点"
        if meta["dup_note"]:
            summary += f"；{meta['dup_note']}（合并 {meta['merged_duplicates']} 行）"
        elif meta["merged_duplicates"]:
            summary += f"；重复时间戳已按天求和聚合（合并 {meta['merged_duplicates']} 行）"
        if meta["utc_note"]:
            summary += f"；{meta['utc_note']}"
        summary += "；分解基于固定周期假设"

        result = {
            "period": period, "model": model_used, "n": n,
            "metadata": {k: v for k, v in meta.items() if k != "n_before_resample"},
            "components": components,
            "seasonal_factors": season_factors,
            "conclusion": (f"{model_used} 分解（周期 {period}）：季节波动幅度 {amplitude:.2f}，"
                           f"残差 std {components['resid']['std']:.2f}"),
        }
        res = ok(result, summary)
        res["data_source"] = data_source
        res["__image__"] = img
        return res
    except DataLabError as e:
        return err(e.code, str(e))
    except Exception:
        return err(EC.CALC, "计算失败，请检查数据内容与参数设置（详见服务端日志）")


def register(mcp) -> None:
    """注册到 MCPServer（mcp 2.x，工具名 = 函数名）。"""
    mcp.add_tool(seasonal_decompose, description=__import__("sys").modules[__name__].__doc__)

