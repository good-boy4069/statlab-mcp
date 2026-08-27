"""time_series_forecast —— 时序组 · 时间序列预测（工具 17，简化实现）。

docstring = agent 使用说明书，与 statlab_mcp/docs/design/06_timeseries.md 同步维护。

参数:
    file_path (str): 本地数据文件（csv/tsv/xlsx/json）
    date_col / value_col (str): 日期列与数值列
    horizon (int): 预测步数，1 <= horizon <= 样本量*50%（超限中文报错）

口径:
    auto_arima（pmdarima，stepwise=True, random_state=42, max_order=8）自动定阶；
    季节可估判定（FFT 主频 period 且 n>=2*period）-> SARIMA 否则 ARIMA 并注明；
    五项统一前置由 _common._prepare_series 完成（插值/聚合/时区等均入 metadata）；
    输出预测值 + 95% CI（predict(return_conf_int=True)）+ 历史/预测图（__image__ 顶层）；
    常数列退化为均值预测并注明。

示例:
    time_series_forecast("samples/timeseries.csv", date_col="date", value_col="value",
                         horizon=14)
inline 数据:
    本工具支持可选 inline_data 参数（v1.2.0 起）：与 file_path 二选一，
    支持 records 数组或 {"header": [...], "rows": [[...], ...]} 对象两种形态；
    规模上限/类型域/data_source 来源标注见 statlab_mcp/docs/SPEC.md 第 12 节。

"""

import numpy as np
import pandas as pd
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


def time_series_forecast(file_path: str | None = None, date_col: str | None = None, value_col: str | None = None,
                         horizon: int | None = None,
                   inline_data: list | dict | None = None) -> dict:
    """ARIMA/SARIMA 自动定阶预测：预测值 + 95% CI + 图。"""
    # D17 连锁 optional 化的运行期强校验（SPEC §12.6）
    require_non_none(date_col=date_col, value_col=value_col, horizon=horizon)
    try:
        if isinstance(horizon, bool) or not isinstance(horizon, (int, np.integer)) or horizon < 1:
            raise DataLabError("horizon 必须是 >=1 的整数", EC.PARAM)
        horizon = int(horizon)
        df, data_source = resolve_data(file_path, inline_data)
        y, meta = _prepare_series(df, date_col, value_col)
        n = int(y.size)
        if n < MIN_N:
            raise DataLabError(f"样本过短（n={n}<{MIN_N}），时序分析不可靠", EC.INSUFFICIENT)
        if horizon > n * 0.5:
            raise DataLabError(f"horizon={horizon} 超过样本量一半（{int(n * 0.5)}），"
                               f"请降低预测步数", EC.PARAM)
        if int(y.notna().sum()) == 0:
            raise DataLabError(f"列 {value_col} 无有效数据", EC.INSUFFICIENT)

        # ---- 季节可估判定 + 自动定阶 ----
        yv = y.dropna()
        period = _estimate_period(yv)
        seasonal = period is not None and n >= 2 * period
        if yv.nunique() == 1:                     # 常数列：退化为均值预测
            mean_v = float(yv.iloc[0])
            forecast = [{"step": i + 1, "value": mean_v,
                         "ci_lower": mean_v, "ci_upper": mean_v}
                        for i in range(horizon)]
            model_info = {"order": [0, 0, 0], "seasonal_order": None,
                          "seasonal": False, "aic": None}
            method = "CONSTANT"
        else:
            from pmdarima import auto_arima  # 延迟导入（P1-1：冷启动不加载 pmdarima）
            model = auto_arima(
                yv, seasonal=seasonal, m=int(period) if seasonal else 1,
                stepwise=True, suppress_warnings=True, error_action="ignore",
                max_order=8, random_state=42, trace=False)
            fc, ci = model.predict(n_periods=horizon, return_conf_int=True)
            forecast = [{"step": i + 1, "value": float(fc.iloc[i]),
                         "ci_lower": float(ci[i][0]), "ci_upper": float(ci[i][1])}
                        for i in range(horizon)]
            so = model.seasonal_order
            # pmdarima 的 seasonal_order 恒为 4 元组，非季节时为 (0,0,0,0)；
            # 必须按 P/D/Q 非全零判定，否则非季节数据被恒标 SARIMA（外部评审 M2）
            is_seasonal = bool(so is not None and any(int(v) != 0 for v in so[:3]))
            model_info = {
                "order": [int(v) for v in model.order],
                "seasonal_order": ([int(v) for v in so] if is_seasonal else None),
                "seasonal": is_seasonal,
                "aic": float(model.aic()) if model.aic() is not None else None,
            }
            method = "SARIMA" if is_seasonal else "ARIMA"

        # ---- 图（历史 + 预测 + CI 带）----
        fig, ax = plt.subplots(figsize=(9, 4.2))
        ax.plot(y.index, y.values, lw=0.9, label="历史" if CJK_FONT_OK else "History")
        fc_idx = pd.date_range(start=y.index[-1], periods=horizon + 1,
                               freq=meta["freq"])[1:]
        ax.plot(fc_idx, [f["value"] for f in forecast], "r--", lw=1.2,
                label="预测" if CJK_FONT_OK else "Forecast")
        ax.fill_between(fc_idx, [f["ci_lower"] for f in forecast],
                        [f["ci_upper"] for f in forecast], color="red", alpha=0.15,
                        label="95% CI")
        ax.set_title(f"{method} 预测（horizon={horizon}）" if CJK_FONT_OK
                     else f"{method} forecast (h={horizon})")
        ax.legend()
        fig.tight_layout()
        img = save_plot(fig, "forecast_time_series_forecast_all")

        last_date = str(y.index[-1].date())
        last_val = float(y.dropna().iloc[-1])
        f0 = forecast[0]
        meta_out = {k: v for k, v in meta.items() if k != "n_before_resample"}
        steps_note = ("；常数列预测退化为均值" if method == "CONSTANT"
                      else f"；{method}，AIC={model_info['aic']:.1f}"
                      if model_info["aic"] is not None else "")
        summary = (f"{method}（order={model_info['order']}"
                   + (f", seasonal_order={model_info['seasonal_order']}"
                      if model_info["seasonal_order"] else "")
                   + f"）：预测 {horizon} 步，第 1 步 {f0['value']:.2f}"
                   + f"（95% CI [{f0['ci_lower']:.2f}, {f0['ci_upper']:.2f}]）"
                   + steps_note)
        if meta["interpolated"]:
            summary += f"；已插值 {meta['interpolated']} 个缺失点"
        if meta["dup_note"]:
            summary += f"；{meta['dup_note']}（合并 {meta['merged_duplicates']} 行）"
        elif meta["merged_duplicates"]:
            summary += f"；重复时间戳已按天求和聚合（合并 {meta['merged_duplicates']} 行）"
        if meta["utc_note"]:
            summary += f"；{meta['utc_note']}"
        if meta["tail_nan"]:
            summary += f"；两端缺失 {meta['tail_nan']} 个未插值"
        summary += "；相关≠因果"

        result = {
            "n": n, "horizon": horizon, "freq": meta["freq"],
            "model": model_info, "method": method,
            "metadata": meta_out,
            "forecast": forecast,
            "last_observed": {"date": last_date, "value": last_val},
            "conclusion": (f"未来 {horizon} 步预测完成；第 1 步预测 {f0['value']:.2f}"
                           f"（95% CI [{f0['ci_lower']:.2f}, {f0['ci_upper']:.2f}]）"),
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
    mcp.add_tool(time_series_forecast, description=__import__("sys").modules[__name__].__doc__)

