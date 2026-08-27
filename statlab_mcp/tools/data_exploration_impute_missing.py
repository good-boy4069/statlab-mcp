r"""impute_missing —— 数据探查组 · 缺失值插补（工具 28，v1.2.0 新增）。

与 missing_report 互补的确定性整治工具：只做规则插补（mean/median/ffill/bfill/constant），
不做任何"智能推断"；绝不修改输入文件，插补结果写入 reports/imputed/ 新 CSV 并以
__output__ 返回绝对路径（SPEC 第 11 节文件输出协议）。

docstring = agent 使用说明书，与 statlab_mcp/docs/design/01_data_exploration_batch1.md 同步维护。

参数:
    file_path (str): 本地数据文件（csv/tsv/xlsx/json），仅接受本地路径
    columns (list[str]|None): 待插补的数值列清单；缺省 = 全部含缺失的数值列
        （显式传入时逐列校验：不存在 → E1008；非数值列含 object 伪数值列 → E1009）
    strategy (str, "mean"): mean / median / ffill / bfill / constant；
        mean/median 仅基于有限观测计算（±Inf 不算缺失也不计入均值——排除数进 result）
    value (float|None): 仅 strategy="constant" 时必填的填充值（有限数，
        拒绝 NaN/Inf/bool）；其它策略携带本参数 → E1001

边界（钉死）:
    - 无任何可插补对象 → E1012 中文报错，三种情形 message 独立：
      全表无缺失 / 指定列均无缺失 / 缺失仅位于非数值列；
    - 列全缺失且策略为 mean/median/ffill/bfill 时无来源可用 → 该列跳过原样保留，
      在 result.skipped_columns 与 summary 如实注明（不报错）；constant 对全缺失列生效；
    - 输出文件 = reports/imputed/YYYYmmdd/impute_missing_<干名>_<策略>_YYYYmmdd_HHMMSS_fff.csv
      （utf-8-sig；Excel 公式注入转义与控制字符清洗见 SPEC 第 11 节第 5 条）。

返回: 成功 result 含 {columns_processed:[{column,strategy,filled,value_or_direction,
    excluded_nonfinite,residual_missing}], skipped_columns:[...], output_dir} +
    顶层 __output__ = 插补文件绝对路径。
局限声明（固定附于 summary 末尾）：插补值为确定性规则估计，会低估方差、可能引入偏差，
后续分析请注明使用了插补数据。

示例:
    impute_missing("samples/dirty.csv")                     # 默认全部数值缺失列、均值
    impute_missing("samples/dirty.csv", columns=["score"], strategy="median")
    impute_missing("samples/dirty.csv", columns=["note"], strategy="constant", value=0)
inline 数据:
    本工具支持可选 inline_data 参数（v1.2.0 起）：与 file_path 二选一，
    支持 records 数组或 {"header": [...], "rows": [[...], ...]} 对象两种形态；
    规模上限/类型域/data_source 来源标注见 statlab_mcp/docs/SPEC.md 第 12 节。

"""
from __future__ import annotations

import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from statlab_mcp.tools._common import (
    EC,
    IMPUTED_DIR,
    DataLabError,
    _cleanup_old_dirs,
    _safe_name,
    err,
    ok,
    resolve_data,
)

_STRATEGIES = ("mean", "median", "ffill", "bfill", "constant")
_DIR_SIGN = {"ffill": "前向（上一有效值）", "bfill": "后向（下一有效值）"}
_LIMITATION = ("局限声明：插补值为确定性规则估计，会低估方差、可能引入偏差，"
               "后续分析请注明使用了插补数据")

_CTRL_CHARS = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
_FORMULA_PREFIX = re.compile(r"^[=+\-@]")


def _escape_csv_cell(v: Any) -> Any:
    """CSV 写出防 Excel 公式注入 + 控制字符清洗（SPEC 第 11 节第 5 条）。"""
    if isinstance(v, str):
        v = v.lstrip("\t\r")     # 红队 P2-8：前导 Tab/CR 同样构成公式注入前缀
        v = _CTRL_CHARS.sub("", v)
        if _FORMULA_PREFIX.match(v):
            v = "'" + v
    return v


def impute_missing(file_path: str | None = None,
                   inline_data: list | dict | None = None, columns: list[str] | None = None,
                   strategy: str = "mean",
                   value: float | None = None) -> dict:
    """确定性缺失值插补主入口。"""
    try:
        # ---- 参数校验 ----
        if not isinstance(strategy, str) or strategy not in _STRATEGIES:
            raise DataLabError(f"strategy 仅支持 {'/'.join(_STRATEGIES)}", EC.PARAM)
        if strategy == "constant":
            if not isinstance(value, (int, float)) or isinstance(value, bool) \
                    or not math.isfinite(value):
                raise DataLabError(
                    "strategy=constant 时必须提供有限数的 value（拒绝 NaN/Inf/bool）",
                    EC.PARAM)
        elif value is not None:
            raise DataLabError(
                "value 仅在 strategy=constant 时使用，请移除该参数或改用 constant",
                EC.PARAM)

        df, data_source = resolve_data(file_path, inline_data)

        # ---- 目标列解析 ----
        explicit = columns is not None
        if explicit and (
                not isinstance(columns, list) or len(columns) == 0 or
                not all(isinstance(c, str) for c in columns)):
            raise DataLabError(
                "columns 必须为非空的字符串数组（如 [\"score\",\"income\"]）", EC.PARAM)
        if explicit:
            for c in columns:
                if c not in df.columns:
                    raise DataLabError(f"缺少必需列: {c}；实际列: {list(df.columns)}",
                                       EC.COLUMN_MISSING)
                if not pd.api.types.is_numeric_dtype(df[c]):
                    raise DataLabError(
                        f"列 {c} 不是数值列（本工具仅对数值列插补，object 伪数值列亦不支持）",
                        EC.COLUMN_TYPE)
            targets = list(dict.fromkeys(columns))
        else:
            targets = sorted(c for c in df.columns
                             if pd.api.types.is_numeric_dtype(df[c])
                             and df[c].isna().any())

        total_missing_all = int(df.isna().sum().sum())
        if not targets:
            if explicit:
                raise DataLabError("指定的列均无缺失值，无需插补（数据可直接用于分析）",
                                   EC.NO_OBJECT)
            if total_missing_all == 0:
                raise DataLabError("数据无任何缺失值，无需插补（数据可直接用于分析）",
                                   EC.NO_OBJECT)
            raise DataLabError(
                "存在缺失但仅位于非数值列，本工具不对非数值列插补；"
                "如需处理请先用 missing_report 定位或转换为数值类型", EC.NO_OBJECT)

        # ---- 逐列插补（独立副本，绝不触碰输入文件）----
        out_df = df.copy()
        per_column: list[dict[str, Any]] = []
        skipped_columns: list[dict[str, str]] = []
        total_filled = 0
        for col in targets:
            s = out_df[col]
            isna_mask = s.isna()
            before_isna = int(isna_mask.sum())
            finite_vals = s.dropna().to_numpy(dtype=float)
            excluded_nonfinite = int((~np.isfinite(finite_vals)).sum())
            finite_vals = finite_vals[np.isfinite(finite_vals)]
            entry: dict[str, Any] = {
                "column": col, "strategy": strategy, "filled": 0,
                "value_or_direction": None,
                "excluded_nonfinite": excluded_nonfinite,
                "residual_missing": before_isna}

            def _skip(reason: str, *, _col: str = col,
                      _entry: dict[str, Any] = entry) -> None:
                """记跳过列（该列原样保留），显式绑定循环变量（B023）。"""
                skipped_columns.append({"column": _col, "reason": reason})
                per_column.append(_entry)

            has_source = finite_vals.size > 0 or strategy == "constant"
            if not has_source:
                _skip("无可插补来源（列全缺失或全部为非有限值）")
                continue

            if strategy in ("mean", "median"):
                fill_v = float(np.mean(finite_vals)) if strategy == "mean" \
                    else float(np.median(finite_vals))
                out_df.loc[isna_mask, col] = fill_v
                entry["value_or_direction"] = fill_v
            elif strategy in ("ffill", "bfill"):
                out_df[col] = out_df[col].ffill() if strategy == "ffill" \
                    else out_df[col].bfill()
                entry["value_or_direction"] = _DIR_SIGN[strategy]
            else:                                        # constant
                out_df.loc[isna_mask, col] = float(value)
                entry["value_or_direction"] = float(value)

            actual_filled = before_isna - int(out_df[col].isna().sum())
            if actual_filled == 0 and before_isna > 0:
                # 红队 P2-6：ffill/bfill 的缺失全在序列头/尾（无前值/后值可填充）
                # 时归 skipped 并如实注明——原实现落入"数据无任何缺失值"E1012，
                # 与事实相悖误导 agent 判定数据健康
                pos, neighbor = (("头部", "前") if strategy == "ffill"
                                 else ("尾部", "后"))
                _skip(f"缺失均位于序列{pos}，无{neighbor}值可填充（策略={strategy}）")
                continue
            entry["filled"] = actual_filled
            entry["residual_missing"] = int(out_df[col].isna().sum())
            total_filled += actual_filled
            per_column.append(entry)

        if total_filled == 0 and not skipped_columns:
            # 显式列表 filled=0（列健康但被点名）/ 全表健康的显式与默认场景统一归 E1012
            if explicit:
                raise DataLabError("指定的列均无缺失值，无需插补（数据可直接用于分析）",
                                   EC.NO_OBJECT)
            raise DataLabError("数据无任何缺失值，无需插补（数据可直接用于分析）",
                               EC.NO_OBJECT)

        # ---- 写出文件（SPEC 第 11 节）----
        now = datetime.now()
        ts = now.strftime("%Y%m%d_%H%M%S_%f")[:-3]
        day_dir = IMPUTED_DIR / now.strftime("%Y%m%d")
        day_dir.mkdir(parents=True, exist_ok=True)
        _cleanup_old_dirs(IMPUTED_DIR)
        stem = _safe_name(Path(file_path).stem) if file_path else "inline"
        out_path = day_dir / f"impute_missing_{stem}_{strategy}_{ts}.csv"
        escaped = out_df.map(_escape_csv_cell)
        escaped.to_csv(out_path, index=False, encoding="utf-8-sig")

        active = [e for e in per_column if e["filled"] > 0]
        parts = [(f"已生成插补文件：{len(per_column)} 个目标列共补齐 "
                  f"{total_filled} 处缺失（策略={strategy}）")]
        detail = "、".join(
            f"{e['column']} 补 {e['filled']}"
            + (f"（值={e['value_or_direction']:.6g})"
               if isinstance(e["value_or_direction"], float)
               else (f"（{e['value_or_direction']}）"
                     if e["value_or_direction"] else ""))
            for e in active)
        if detail:
            parts.append(detail)
        if skipped_columns:
            parts.append("; ".join(f"{s['column']} 跳过（{s['reason']}）"
                                   for s in skipped_columns))
        parts.append(_LIMITATION)

        result = {"rows_before": int(df.shape[0]),
                  "columns_processed": per_column,
                  "skipped_columns": [s["column"] for s in skipped_columns],
                  "total_filled": total_filled,
                  "output_dir": str(day_dir)}
        payload = ok(result, "；".join(parts))
        payload["data_source"] = data_source
        payload["__output__"] = str(out_path)          # SPEC §11：顶层平级路径字段
        return payload
    except DataLabError as e:
        return err(e.code, str(e))
    except Exception:
        return err(EC.CALC, "计算失败，请检查数据内容与参数设置（详见服务端日志）")


def register(mcp) -> None:
    """注册到 MCPServer（mcp 2.x，工具名 = 函数名）。"""
    mcp.add_tool(impute_missing, description=__import__("sys").modules[__name__].__doc__)
