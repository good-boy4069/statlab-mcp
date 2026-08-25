# -*- coding: utf-8 -*-
"""describe_statistics —— 数据探查组 · 描述性统计（工具 1，核心实现）。

docstring = agent 使用说明书，与 docs/design/01_data_exploration_batch1.md 同步维护。

参数:
    file_path (str): 本地数据文件（csv/tsv/xlsx/json），仅接受本地路径（拒绝 UNC）

返回:
    成功 {"status":"ok","result":{...},"summary":"一句话中文结论"}
    失败 {"status":"error","message":"中文原因"}（error 时无 result 字段）
    result 结构见设计文档「工具 1」JSON Schema：
    {n_rows, n_columns, numeric_columns, non_numeric_columns, fully_missing_columns,
     columns: {<列名>: {n, mean, median, std, min, q1, q3, max, skew, kurtosis, n_missing}}}

统计定义（SPEC 裁决，测试断言口径）:
    - 分位数 q1/q3 = linear 插值（=Excel QUARTILE.INC），Series.quantile 默认即 linear；
    - std 用 ddof=1（=Excel STDEV.S）；
    - skew = scipy.stats.skew(x, bias=False)（Fisher 样本偏度）；
    - kurtosis = scipy.stats.kurtosis(x, fisher=True, bias=False)（超额峰度，正态=0）。

边界语义（使用者已裁决）:
    - 全缺失列：n=0、n_missing=总行数、其余统计键全 null，不中断整表；
    - 常数列（std=0）：skew/kurtosis=null（方差为 0 无法定义）；
    - n<2：std/q1/q3=null；n<3：skew/kurtosis=null；
    - 非数值列忽略统计并列入 non_numeric_columns。

示例:
    describe_statistics("samples/clean.csv")
"""
from typing import Any, Dict

import numpy as np
import pandas as pd
from scipy import stats as sps

from statlab_mcp.tools._common import DataLabError, err, ok, read_table

MAX_NUMERIC_COLS = 200      # 防超大 JSON 输出（红队 B S3）


def _describe_numeric_col(s: pd.Series, n_rows: int) -> Dict[str, Any]:
    """单列描述统计：缺失按有效值计算，边界口径见模块 docstring。"""
    valid = s.dropna()
    n = int(valid.size)
    out: Dict[str, Any] = {
        "n": n, "mean": None, "median": None, "std": None,
        "min": None, "q1": None, "q3": None, "max": None,
        "skew": None, "kurtosis": None, "n_missing": n_rows - n,
    }
    if n == 0:
        return out
    out["mean"] = float(valid.mean())
    out["median"] = float(valid.median())
    out["min"] = float(valid.min())
    out["max"] = float(valid.max())
    if n >= 2:
        out["std"] = float(valid.std(ddof=1))
        out["q1"] = float(valid.quantile(0.25, interpolation="linear"))
        out["q3"] = float(valid.quantile(0.75, interpolation="linear"))
    if n >= 3 and out["std"] is not None and out["std"] > 0:
        x = valid.to_numpy(dtype=np.float64)
        out["skew"] = float(sps.skew(x, bias=False))
        out["kurtosis"] = float(sps.kurtosis(x, fisher=True, bias=False))
    return out


def _fmt(v: Any, nd: int = 2) -> str:
    return "无" if v is None else f"{v:.{nd}f}"


def describe_statistics(file_path: str) -> dict:
    """对数据文件的每一数值列输出描述统计（n/均值/中位数/标准差/分位数/偏度/峰度/缺失）。"""
    try:
        df = read_table(file_path)
        n_rows = int(len(df))
        n_columns = int(df.shape[1])
        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        if not numeric_cols:
            raise DataLabError("未找到数值列，无法计算描述统计")
        if len(numeric_cols) > MAX_NUMERIC_COLS:
            raise DataLabError(f"数值列超过 {MAX_NUMERIC_COLS} 个，输出过大，请先挑选列")

        columns = {}
        fully_missing = []
        constant_cols = []
        for col in numeric_cols:
            d = _describe_numeric_col(df[col], n_rows)
            columns[col] = d
            if d["n"] == 0:
                fully_missing.append(col)
            elif d["std"] == 0:
                constant_cols.append(col)
        non_numeric = [c for c in df.columns if c not in numeric_cols]
        non_numeric.sort()

        result = {
            "n_rows": n_rows,
            "n_columns": n_columns,
            "numeric_columns": numeric_cols,
            "non_numeric_columns": non_numeric,
            "fully_missing_columns": fully_missing,
            "columns": columns,
        }

        # summary 由代码模板拼数字生成（第一层禁止 LLM 文字）
        head = f"共 {n_rows} 行 {n_columns} 列；数值列 {len(numeric_cols)} 个（{', '.join(numeric_cols)}）"
        parts = [head]
        if fully_missing:
            parts.append(f"全缺失列 {len(fully_missing)} 个：{', '.join(fully_missing)}")
        if constant_cols:
            parts.append(f"常数列 {len(constant_cols)} 个：{', '.join(constant_cols)}（偏度/峰度无定义）")
        anchor = next((d for d in columns.values() if d["n"] > 0), None)
        if anchor is not None:
            cname = next(k for k, d in columns.items() if d is anchor)
            parts.append(
                f"例：{cname} 均值 {_fmt(anchor['mean'])}，中位数 {_fmt(anchor['median'])}，"
                f"标准差 {_fmt(anchor['std'])}，最大 {_fmt(anchor['max'])}，缺失 {anchor['n_missing']}"
            )
        if non_numeric:
            parts.append(f"非数值列 {len(non_numeric)} 个已忽略（{', '.join(non_numeric[:5])}）")
        summary = "；".join(parts) + "。"

        return ok(result, summary)
    except DataLabError as e:
        return err(str(e))
    except Exception as e:  # 计算层兜底：中文报错
        return err("计算失败，请检查数据内容与参数设置（详见服务端日志）")


def register(mcp) -> None:
    """注册到 MCPServer（mcp 2.x，工具名 = 函数名）。"""
    mcp.add_tool(describe_statistics, description=__import__("sys").modules[__name__].__doc__)

