"""trend_analysis —— 时序组 · 趋势分析（工具 19，简化实现）。

docstring = agent 使用说明书，与 statlab_mcp/docs/design/06_timeseries.md 同步维护。

参数:
    file_path (str): 本地数据文件（csv/tsv/xlsx/json）
    date_col / value_col (str): 日期列与数值列
    method (str, "mann_kendall"): mann_kendall / theil_sen

口径:
    Mann-Kendall：scipy.stats.kendalltau(y, 时间序号) 的 tau 与 p（MK 检验的
    tau 统计量 + 正态近似双侧 p，scipy 官方实现，输出注明该口径）；
    Theil-Sen 斜率：点对斜率中位数（n<=2000 全枚举；n>2000 固定 seed 抽样
    50000 对并注明）；两种方法都输出 tau/p/slope，method 决定 slope 的计算主口径
    （theil_sen 时 slope 为点对中位数；mann_kendall 时 slope 同样用 Theil-Sen 斜率，
    tau 为主统计量）。
    含季节成分时输出"趋势结论需谨慎"警示（设计文档：不校正）。

示例:
    trend_analysis("samples/timeseries.csv", date_col="date", value_col="value")
inline 数据:
    本工具支持可选 inline_data 参数（v1.2.0 起）：与 file_path 二选一，
    支持 records 数组或 {"header": [...], "rows": [[...], ...]} 对象两种形态；
    规模上限/类型域/data_source 来源标注见 statlab_mcp/docs/SPEC.md 第 12 节。

"""
import math

import numpy as np
from scipy import stats as sps

from statlab_mcp.tools._common import (
    EC,
    DataLabError,
    _prepare_series,
    err,
    ok,
    require_non_none,
    resolve_data,
)

_MIN_N = 8
_MAX_PAIRS = 50000
_FULL_ENUM_LIMIT = 2000
_METHODS = {"mann_kendall", "theil_sen"}


def _fmt_p(p: float) -> str:
    """p 值格式化：p<0.001 统一显示 '<0.001'（防幻觉口径），其余保留 4 位小数。"""
    return "<0.001" if p < 0.001 else f"{p:.4f}"


def _theil_sen_slope(yv: np.ndarray) -> float:
    """点对斜率中位数（O(n²) 向量化）。"""
    n = int(yv.size)
    if n <= 2:
        return 0.0
    if n <= _FULL_ENUM_LIMIT:
        slopes = []
        for j in range(1, n):
            slopes.append((yv[j:] - yv[:-j]) / j)
        return float(np.median(np.concatenate(slopes)))
    # 大样本：固定 seed 抽样 50000 对（确定性）
    rng = np.random.default_rng(42)
    idx = rng.integers(0, n, size=(_MAX_PAIRS, 2))
    i1, i2 = np.minimum(idx[:, 0], idx[:, 1]), np.maximum(idx[:, 0], idx[:, 1])
    mask = i1 != i2
    d = i2[mask] - i1[mask]
    slopes = (yv[i2[mask]] - yv[i1[mask]]) / d
    return float(np.median(slopes))


def trend_analysis(file_path: str | None = None, date_col: str | None = None, value_col: str | None = None,
                   method: str = "mann_kendall",
                   inline_data: list | dict | None = None) -> dict:
    """Mann-Kendall / Theil-Sen 趋势检验：tau、p、斜率与单调性结论。"""
    # D17 连锁 optional 化的运行期强校验（SPEC §12.6）
    require_non_none(date_col=date_col, value_col=value_col)
    try:
        if method not in _METHODS:
            raise DataLabError("method 仅支持 mann_kendall/theil_sen", EC.PARAM)
        df, data_source = resolve_data(file_path, inline_data)
        y, meta = _prepare_series(df, date_col, value_col)
        # _prepare_series 的插值只填中间缺失，头部 NaN 保留（interpolate 无法回填）；
        # 必须 dropna 后检验，否则 kendalltau 遇 NaN 返回 (nan,nan) 被改写为无趋势（外部评审 S2）
        head_nan = 0
        if not bool(y.notna().all()):
            head_nan = int(y.notna().to_numpy().argmax())   # 第一个有效值的位置 = 开头缺失数
            y = y.dropna()
        n = int(y.size)
        if n < _MIN_N:
            raise DataLabError(f"有效样本不足（n={n}<{_MIN_N}），趋势检验不可靠", EC.INSUFFICIENT)
        yv = y.to_numpy(dtype=float)

        tau, p = sps.kendalltau(yv, np.arange(n))       # MK：tau + 正态近似双侧 p
        tau = 0.0 if math.isnan(tau) else float(tau)   # 全等序列 scipy 返回 nan -> 语义 tau=0
        p = 1.0 if math.isnan(p) else float(p)
        slope = _theil_sen_slope(yv)
        if slope > 0:
            direction = "上升"
        elif slope < 0:
            direction = "下降"
        else:
            direction = "无"
        monotonic = bool(p < 0.05)

        sampled = "；大样本点对斜率已抽样 50000 对（seed=42）" if n > _FULL_ENUM_LIMIT else ""
        season_note = "；含季节成分时趋势结论需谨慎（未做季节校正）"
        nan_note = f"；开头 {head_nan} 个缺失未参与计算" if head_nan else ""
        dup_txt = (f"；{meta['dup_note']}（合并 {meta['merged_duplicates']} 行）"
                   if meta["dup_note"] else "")
        if monotonic and direction != "无":
            concl = (f"p={_fmt_p(p)} <0.05：存在显著{'上升' if direction == '上升' else '下降'}"
                     f"的单调趋势；斜率（Theil-Sen）={slope:.4f}/单位时间")
        elif monotonic:
            # 斜率恰为 0 而检验显著：MK 与 Theil-Sen 统计量不一致，方向无法判定（外部评审 L7）
            concl = (f"p={_fmt_p(p)} <0.05：检验显著，但 Theil-Sen 斜率中位数恰为 0，"
                     f"趋势方向无法判定（建议换 theil_sen 方法复核）")
        else:
            concl = (f"p={_fmt_p(p)} ≥0.05：无显著单调趋势；"
                     f"斜率（Theil-Sen）={slope:.4f}/单位时间")
        summary = (f"Mann-Kendall：tau={tau:.3f}（p={_fmt_p(p)}），"
                   f"{'显著' + direction + '趋势' if monotonic and direction != '无' else '无显著单调趋势'}；"
                   f"Theil-Sen 斜率 {slope:.3f}/单位时间"
                   f"{sampled}{nan_note}{dup_txt}{season_note}")

        result = {
            "method": method, "n": n,
            "head_dropped": head_nan,
            "tau": tau, "p_value": p,
            "slope": slope,
            "slope_note": "Theil-Sen 点对斜率中位数" + ("（抽样）" if sampled else ""),
            "trend_direction": direction,
            "monotonic": monotonic,
            "metadata": {k: v for k, v in meta.items() if k != "n_before_resample"},
            "conclusion": concl,
        }
        _payload = ok(result, summary)
        _payload["data_source"] = data_source
        return _payload
    except DataLabError as e:
        return err(e.code, str(e))
    except Exception:
        return err(EC.CALC, "计算失败，请检查数据内容与参数设置（详见服务端日志）")


def register(mcp) -> None:
    """注册到 MCPServer（mcp 2.x，工具名 = 函数名）。"""
    mcp.add_tool(trend_analysis, description=__import__("sys").modules[__name__].__doc__)

