"""plot_forecast —— 可视化组 · 时序折线图（工具 24，核心实现）。

原值折线 + 7 日移动平均线；**仅作图不预测**（预测见工具 17）。
五项统一前置由 _common._prepare_series 承载（插值/聚合/时区均报告）。
inline 数据:
    本工具支持可选 inline_data 参数（v1.2.0 起）：与 file_path 二选一，
    支持 records 数组或 {"header": [...], "rows": [[...], ...]} 对象两种形态；
    规模上限/类型域/data_source 来源标注见 statlab_mcp/docs/SPEC.md 第 12 节。

"""

from matplotlib import pyplot as plt

from statlab_mcp.tools._common import (
    CJK_FONT_OK,
    EC,
    DataLabError,
    _prepare_series,
    err,
    ok,
    require_non_none,
    resolve_data,
    save_plot,
)

MIN_N = 5
MA_WINDOW = 7


def plot_forecast(file_path: str | None = None, date_col: str | None = None, value_col: str | None = None,
                   inline_data: list | dict | None = None) -> dict:
    """时序折线图 + 7 日均线（仅作图，不预测）。"""
    try:
        # D17 连锁 optional 化的运行期强校验（SPEC §12.6）
        require_non_none(date_col=date_col, value_col=value_col)
        df, data_source = resolve_data(file_path, inline_data)
        y, meta = _prepare_series(df, date_col, value_col)
        n = int(y.size)
        if n < MIN_N:
            raise DataLabError(f"样本过短（n={n}<{MIN_N}），无法作图", EC.INSUFFICIENT)
        ma = y.rolling(MA_WINDOW, min_periods=3).mean()

        fig, ax = plt.subplots(figsize=(9, 4.0))
        ax.plot(y.index, y.values, lw=0.9, color="#4C72B0",
                label="原值" if CJK_FONT_OK else "Series")
        ax.plot(ma.index, ma.values, lw=1.4, color="red",
                label=f"{MA_WINDOW} 日均线" if CJK_FONT_OK else f"MA{MA_WINDOW}")
        ax.set_title(f"{value_col} 时间序列（n={n}）" if CJK_FONT_OK
                     else f"{value_col} time series (n={n})")
        ax.legend()
        fig.tight_layout()
        img = save_plot(fig, "plot_forecast_all")

        result = {
            "n": n, "series_min": float(y.min()), "series_max": float(y.max()),
            "series_last": float(y.iloc[-1]),
            "metadata": {k: v for k, v in meta.items() if k != "n_before_resample"},
        }
        summary = (f"时序图已保存：{value_col}（n={n}，范围 "
                   f"[{result['series_min']:.2f}, {result['series_max']:.2f}]，"
                   f"末端 {result['series_last']:.2f}，含 {MA_WINDOW} 日均线）")
        if meta["interpolated"]:
            summary += f"；已插值 {meta['interpolated']} 个缺失点"
        if meta["dup_note"]:
            summary += f"；{meta['dup_note']}（合并 {meta['merged_duplicates']} 行）"
        elif meta["merged_duplicates"]:
            summary += f"；重复时间戳已按天求和聚合（合并 {meta['merged_duplicates']} 行）"
        if meta["utc_note"]:
            summary += f"；{meta['utc_note']}"
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
    mcp.add_tool(plot_forecast, description=__import__("sys").modules[__name__].__doc__)


