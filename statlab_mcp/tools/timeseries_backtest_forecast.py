"""backtest_forecast —— 时序组 · 滚动回测（工具 29，v1.2.0 新增）。

time_series_forecast 的可信度自评：滚动窗口回测输出 MAE/RMSE/MAPE，
让预测结论自带"历史表现"背书。前置处理与 forecast 完全同口径
（_prepare_series 五项统一前置），**逐窗独立重放以杜绝真值泄漏**
（验证窗不含任何由未来观测构造的插值点——design/06 防泄漏节）。

docstring = agent 使用说明书，与 statlab_mcp/docs/design/06_timeseries.md 同步维护。

参数:
    file_path (str): 本地数据文件（csv/tsv/xlsx/json），仅接受本地路径
    date_col (str): 日期列；value_col (str): 数值值列（语义与 time_series_forecast 一致）
    horizon (int): 每窗验证段长度，1 <= horizon <= 有效样本×50%（E1001）
    windows (int, 3): 回测窗口数，1..10（auto_arima 每窗一次拟合，防耗时爆炸；E1001）
    method (str, "auto_arima"): auto_arima / naive / seasonal_naive
        （两个 naive 基线为封闭公式，用于对照；seasonal_naive 的周期逐窗取
        _estimate_period，不可估或 > 训练段长时退化为 naive 并记 period_used_fallback）

门槛链（校验顺序红线 D9）:
    参数合法 → n>=30（低于报错 E1010）→ n >= horizon*(windows+1) 且
    train_min = n - windows*horizon >= max(15, 2*period_full_est)（E1010 带调参建议）
    → n<=100000（E1005 防大表卡顿）→ 逐窗计算。

指标: 每窗口逐点 pred/actual/abs_err + 汇总 MAE/RMSE/MAPE；
真实值含 |actual|<=1e-12 时该窗口 MAPE=null 并注明 zero_note（禁止除零假值）。
明细总量上限 10000 点，超出截断最旧窗并记 truncated=true（汇总永不截断）。

局限声明（固定附于 summary 末尾）：回测表现不代表未来；未做外部验证。

示例:
    backtest_forecast("samples/clean.csv", "date", "score", horizon=3)
    backtest_forecast("samples/clean.csv", "date", "score",
                      horizon=2, windows=2, method="naive")
inline 数据:
    本工具支持可选 inline_data 参数（v1.2.0 起）：与 file_path 二选一，
    支持 records 数组或 {"header": [...], "rows": [[...], ...]} 对象两种形态；
    规模上限/类型域/data_source 来源标注见 statlab_mcp/docs/SPEC.md 第 12 节。

"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from statlab_mcp.tools._common import (
    EC,
    DataLabError,
    _estimate_period,
    _prepare_series,
    err,
    ok,
    require_non_none,
    resolve_data,
)

_MIN_N = 30                       # 回测最低有效样本（高于 forecast 的 MIN_N=15）
_MAX_WINDOWS = 10
_DETAIL_CAP = 10_000              # 逐点明细总点数上限（超出截断最旧窗）
_EPS_ZERO = 1e-12                 # MAPE 分母零判据（R2-F11：显式 epsilon 而非 ==0）

_METHODS = ("auto_arima", "naive", "seasonal_naive")

# BLAS 单线程默认已前移至 statlab_mcp/__init__.py（红队 P2-12：此处设置晚于
# numpy 导入，OpenBLAS/MKL 已初始化，setdefault 不再生效）


def _mape(pred: np.ndarray, actual: np.ndarray) -> float | None:
    """单窗口 MAPE = mean(|a-f|/|a|)；含零真值该窗置 None（R2-F11 epsilon 判据）。"""
    denom = np.abs(actual)
    if bool(np.any(denom <= _EPS_ZERO)):
        return None
    return float(np.mean(np.abs(actual - pred) / denom))


def _fit_predict_one(method: str, y_train: pd.Series, horizon: int,
                     period_est: int | None) -> tuple[np.ndarray, dict[str, Any]]:
    """单窗拟合预测。返回 (pred 数组, 元信息)。方法间口径与 forecast 一致。"""
    info: dict[str, Any] = {}
    if method == "naive":
        return np.full(horizon, float(y_train.iloc[-1]), dtype=float), info
    # seasonal_naive：周期逐窗估计；period 不可估/≤1 已在外部退化 naive；
    # period > 窗内训练段长时同样退化（t-m 会越界，R2-F12）
    if method == "seasonal_naive":
        if period_est is not None and len(y_train) > period_est:
            last = y_train.iloc[-period_est:].to_numpy(dtype=float)
            reps = math.ceil(horizon / period_est)
            return np.tile(last, reps)[:horizon], {**info, "period_used": period_est}
        return np.full(horizon, float(y_train.iloc[-1]), dtype=float), \
            {**info, "period_used_fallback": True}
    # auto_arima：与 time_series_forecast 完全同参（P2 同口径承诺）
    from pmdarima import auto_arima  # 延迟导入（P1-1 固定清单成员）
    model = auto_arima(
        y_train.to_numpy(dtype=float),
        stepwise=True, suppress_warnings=True, error_action="ignore",
        max_order=8, random_state=42, trace=False)
    fcst = model.predict(n_periods=horizon)
    return np.asarray(fcst, dtype=float), info


def backtest_forecast(file_path: str | None = None, date_col: str | None = None,
                      value_col: str | None = None, horizon: int | None = None,
                      windows: int = 3, method: str = "auto_arima",
                      inline_data: list | dict | None = None) -> dict:
    """滚动回测主入口：expanding window、从序列尾部向前切 windows 个验证窗。"""
    try:
        # D17 连锁 optional 化的运行期强校验（SPEC §12.6）
        require_non_none(date_col=date_col, value_col=value_col, horizon=horizon)
        # ---- 参数合法化（D9 第一层：任何非法参数先于门槛报错）----
        if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon < 1:
            raise DataLabError("horizon 必须是 >=1 的整数", EC.PARAM)
        if isinstance(windows, bool) or not isinstance(windows, int):
            raise DataLabError("windows 必须是整数（默认 3，上限 10）", EC.PARAM)
        if windows < 1 or windows > _MAX_WINDOWS:
            raise DataLabError(
                f"windows 必须在 1 到 {_MAX_WINDOWS} 之间"
                f"（每窗一次 auto_arima 拟合，防耗时爆炸）", EC.PARAM)
        if method not in _METHODS:
            raise DataLabError(f"method 仅支持 {'/'.join(_METHODS)}", EC.PARAM)

        df, data_source = resolve_data(file_path, inline_data)
        y_full, meta = _prepare_series(df, date_col, value_col)
        n = int(y_full.size)

        # ---- 门槛链（D9 红线顺序；多层拒绝带可调建议）----
        if n < _MIN_N:
            raise DataLabError(
                f"有效样本过短（n={n}<{_MIN_N}），短序列回测无统计意义；"
                f"请积累更多数据后重试", EC.INSUFFICIENT)
        if n < horizon * (windows + 1):
            need = horizon * (windows + 1)
            raise DataLabError(
                f"样本不足以完成 {windows} 窗 × {horizon} 步回测"
                f"（需 n>={need}，实际 n={n}）；请减少 windows 或 horizon 后重试",
                EC.INSUFFICIENT)
        period_full = _estimate_period(y_full)
        train_min = n - windows * horizon
        min_required = max(15, 2 * period_full) if period_full else 15
        if train_min < min_required:
            raise DataLabError(
                f"第一窗训练段仅 {train_min} 点，不足稳定拟合"
                f"（本配置要求 ≥{min_required}"
                + (f"=2×周期{period_full}" if period_full else "") + "）；"
                "请减少 windows 或 horizon 后重试", EC.INSUFFICIENT)
        if n > 100_000:
            raise DataLabError(
                f"有效样本 {n} 行超过回测上限 100000（防大表反复拟合耗时）；"
                "请截取最近数据段后重试", EC.SCALE)

        # ---- 滚动切窗（尾部向前；每窗训练段=验证窗前全部历史，expanding）----
        window_records: list[dict[str, Any]] = []
        maes: list[float] = []
        rmses: list[float] = []
        mapes: list[float | None] = []
        any_zero_window = False
        truncated = False

        # 原始观测序列（红队 P1-1 防泄漏）：验证窗真值只从这里取。与
        # _prepare_series 的聚合口径一致（同刻求和、min_count=1），无效日期与
        # 缺值行不构成观测；y_full 为全量插值序列，其验证段缺口点是"由未来
        # 观测构造的插值"，直接取用违反 R2-F02 防泄漏钉死条款。
        _rd = pd.to_datetime(df[date_col], errors="coerce", utc=True)
        _rv = df[value_col].to_numpy(dtype=float)
        _mobs = _rd.notna() & ~np.isnan(_rv)
        raw_obs = pd.Series(_rv[_mobs], index=_rd[_mobs]) \
            .groupby(level=0).sum(min_count=1).sort_index()

        for i in range(windows):                     # i=0 为最早窗
            val_start = n - (windows - i) * horizon  # 验证段起点（含）
            train_end = val_start                    # 训练段 = [0, val_start)
            # 防泄漏（R2-F02）：逐窗只喂训练段历史重新做前置处理
            hist_df = df.iloc[:train_end].copy()
            try:
                y_hist, _meta_w = _prepare_series(hist_df, date_col, value_col)
            except DataLabError:
                window_records.append({"index": i, "error": "训练段前置处理失败"})
                continue
            p_full = _estimate_period(y_hist)
            use_period = p_full if (p_full is not None and p_full > 1) else None
            y_val = y_full.iloc[val_start:val_start + horizon]
            h_use = min(horizon, int(y_val.size))
            # 验证窗 actual 只认原始观测：无观测的时间点（asfreq 补齐/插值点）
            # 置 NaN 逐窗计数披露（n_actual_dropped），不进入任何指标
            m_obs = (raw_obs.index > y_hist.index[-1]) & (raw_obs.index <= y_val.index[-1])
            obs_win = raw_obs.loc[m_obs]
            actual = np.array([obs_win.get(t, np.nan) for t in y_val.index],
                              dtype=float)
            obs_valid = ~np.isnan(actual)
            n_dropped = int((~obs_valid).sum())
            try:
                pred, info = _fit_predict_one(method, y_hist, h_use, use_period)
            except Exception as exc:                 # 单窗失败不拖垮整体汇总
                window_records.append({"index": i, "train_end": str(y_hist.index[-1]),
                                       "error": f"{type(exc).__name__}"})
                continue
            if not obs_valid.any():
                window_records.append({
                    "index": i, "train_end": str(y_hist.index[-1]),
                    "error": "验证窗无原始观测真值（全部为补齐/插值点）"})
                continue
            actual_v = actual[obs_valid]
            pred_v = np.asarray(pred, dtype=float)[:h_use][obs_valid]
            abs_err = np.abs(actual_v - pred_v)
            mae = float(np.mean(abs_err))
            rmse = float(np.sqrt(np.mean((actual_v - pred_v) ** 2)))
            mape = _mape(pred_v, actual_v)
            maes.append(mae)
            rmses.append(rmse)
            mapes.append(mape)
            if mape is None:
                any_zero_window = True
            window_records.append({
                "index": i, "train_end": str(y_hist.index[-1]),
                "pred": [float(v) for v in pred_v],
                "actual": [float(v) for v in actual_v],
                "abs_err": [round(float(v), 6) for v in abs_err],
                **({"n_actual_dropped": n_dropped} if n_dropped else {}),
                "mae": mae, "rmse": rmse, "mape": mape,
                **({"period_used": info["period_used"]}
                   if "period_used" in info else {}),
                **({"period_used_fallback": True}
                   if info.get("period_used_fallback") else {}),
            })

        usable = [w for w in window_records if "error" not in w]
        if not usable:
            raise DataLabError("所有回测窗口均拟合失败（详见服务端日志）", EC.CALC)
        detail_count = sum(len(w.get("abs_err", [])) for w in usable)
        if detail_count > _DETAIL_CAP:
            # 截断最旧窗直至明细 <= 上限（汇总指标从不截断，R2-F10）；
            # 红队 P2-4：单窗明细自身超限（如 windows=1, horizon=12000）时原实现
            # "首个超限窗整窗保留"会突破上限——对保留窗再做窗内截断（保最新点）
            keep_from = len(window_records) - 1
            kept = 0
            for k in range(len(window_records) - 1, -1, -1):
                cnt = len(window_records[k].get("abs_err", []))
                if kept + cnt <= _DETAIL_CAP:
                    kept += cnt
                    keep_from = k
                else:
                    break
            window_records = window_records[keep_from:]
            total_kept = sum(len(w.get("abs_err", [])) for w in window_records)
            if total_kept > _DETAIL_CAP and window_records \
                    and "abs_err" in window_records[0]:
                room = _DETAIL_CAP - (total_kept - len(window_records[0]["abs_err"]))
                room = max(room, 0)
                w0 = window_records[0]
                for key in ("pred", "actual", "abs_err"):
                    w0[key] = w0[key][-room:] if room else []
            truncated = True

        summary_metrics = {
            "mae": float(np.mean(maes)),
            "rmse": float(np.sqrt(np.mean(np.square(rmses)))),
            "mape": (lambda ms: None if all(m is None for m in ms)
                     else float(np.mean([m for m in ms if m is not None])))(mapes),
        }
        zero_note = ("部分窗口存在零真值，其 MAPE=null 并已在汇总中剔除"
                     if any_zero_window else "")

        parts = [(f"{method} 回测 {len(usable)} 窗（windows={windows}, "
                  f"horizon={horizon}）：MAE={summary_metrics['mae']:.4f}，"
                  f"RMSE={summary_metrics['rmse']:.4f}")]
        parts.append(f"MAPE={summary_metrics['mape']:.4f}"
                     if summary_metrics["mape"] is not None else
                     "MAPE=null（真值含零）")
        if truncated:
            parts.append("明细已按 10000 点上限截断最旧窗")
        parts.append("局限声明：回测表现不代表未来；未做外部验证"
                     + (f"；{zero_note}" if zero_note else ""))

        result = {
            "method": method,
            "n_valid": n,
            "windows_requested": windows,
            "windows_actual": len(usable),
            "n_windows_failed": windows - len(usable),
            "horizon": horizon,
            "window_records": window_records,
            "metrics": summary_metrics,
            "period_full_est": period_full,
            "truncated": truncated,
            "prep_meta": {"freq": meta["freq"],
                          "interpolated": meta["interpolated"]},
        }
        _payload = ok(result, "；".join(parts))
        _payload["data_source"] = data_source
        return _payload
    except DataLabError as e:
        return err(e.code, str(e))
    except Exception:
        return err(EC.CALC, "计算失败，请检查数据内容与参数设置（详见服务端日志）")


def register(mcp) -> None:
    """注册到 MCPServer（mcp 2.x，工具名 = 函数名）。"""
    mcp.add_tool(backtest_forecast, description=__import__("sys").modules[__name__].__doc__)
