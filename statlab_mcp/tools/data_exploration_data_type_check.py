"""data_type_check —— 数据探查组 · 列类型识别（工具 2，核心实现）。

docstring = agent 使用说明书，与 statlab_mcp/docs/design/01_data_exploration_batch1.md 同步维护。

参数:
    file_path (str): 本地数据文件（csv/tsv/xlsx/json），仅接受本地路径（拒绝 UNC）

返回:
    成功 {"status":"ok","result":{...},"summary":"一句话中文结论"}
    失败 {"status":"error","message":"中文原因"}
    result: {n_rows, n_columns,
             columns: {<列名>: {detected_type, n_valid, n_missing, dirty_count, note}},
             issue_summary: {mixed_columns, fully_missing_columns, invalid_date_columns}}

判定树（确定性代码；实现期修订 vs 设计文档：数值先于日期，防 "123" 被 to_datetime
误认成日期；mixed 定义 = 数值或日期转换成功数在 (0, 95%) 区间，全部失败则按
category/text 处理）:
    1. 全缺失列 → missing（不参与任何转换）
    2. pandas 数值 dtype → numeric；值全为整数 → integer
    3. object 列先试 to_numeric(errors="coerce")：成功 ≥95% → numeric
       （有失配时 dirty_count=失败数，note 给脏值示例；全成功且全整数 → integer）
    4. 未过数值，再试 to_datetime(errors="coerce")：成功 ≥95% → date
       （失配 = 非法日期，如 2024-02-30，记 dirty_count 并在 note 列示例）
    5. 部分可转（成功数在 (0, 95%)）→ mixed（两种转换都失败的值 = 脏值）
    6. 完全不可转：唯一值 ≤ min(50, 行数×20%) → category（note 给 top3）
       否则 → text

示例:
    data_type_check("samples/dirty.csv")
"""
import warnings
from typing import Any

import numpy as np
import pandas as pd

from statlab_mcp.tools._common import EC, DataLabError, err, ok, read_table

_DATE_OK_RATIO = 0.95
_NUM_OK_RATIO = 0.95


def _fmt_example(v: Any) -> str:
    return str(v)[:20]


def _judge_numeric_col(s: pd.Series) -> dict[str, Any]:
    valid = s.dropna()
    n = int(valid.size)
    if n == 0:
        return {  # 全缺失数值列：判 missing（实现期修订，防 n=0 落入 numeric）
            "detected_type": "missing", "n_valid": 0,
            "n_missing": int(s.isna().sum()), "dirty_count": 0, "note": "全缺失列",
        }
    is_int_dtype = pd.api.types.is_integer_dtype(valid)
    all_ints = is_int_dtype or bool(
        np.all(valid.map(lambda v: float(v).is_integer())) if n else False
    )
    return {
        "detected_type": "integer" if all_ints else "numeric",
        "n_valid": n,
        "n_missing": int(s.isna().sum()),
        "dirty_count": 0,
        "note": None,
    }


def _judge_object_col(s: pd.Series, n_rows: int) -> dict[str, Any]:
    valid = s.dropna()
    n = int(valid.size)
    n_missing = n_rows - n
    out: dict[str, Any] = {"n_valid": n, "n_missing": n_missing, "dirty_count": 0, "note": None}
    if n == 0:
        out["detected_type"] = "missing"
        out["note"] = "全缺失列"
        return out

    text = valid.astype(str)
    as_num = pd.to_numeric(text, errors="coerce")
    num_ok = int(as_num.notna().sum())
    num_fail_mask = as_num.isna()
    num_dirty = n - num_ok

    # 3) 数值优先（防纯数字字符串被 to_datetime 误判为日期）
    if num_ok / n >= _NUM_OK_RATIO:
        out["detected_type"] = "numeric"
        out["dirty_count"] = num_dirty
        if num_dirty:
            ex = _fmt_example(text[num_fail_mask].iloc[0])
            out["note"] = f"{num_dirty} 个脏值（如 {ex}）"
        elif np.all(as_num.map(lambda v: float(v).is_integer())):
            out["detected_type"] = "integer"
        return out

    # 文本列逐元素解析会触发 pandas 格式推断警告，属预期行为，静默之
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        as_date = pd.to_datetime(text, errors="coerce")
    date_ok = int(as_date.notna().sum())
    date_fail_mask = as_date.isna()
    invalid_date = n - date_ok

    # 4) 日期判定
    if date_ok / n >= _DATE_OK_RATIO:
        out["detected_type"] = "date"
        out["dirty_count"] = invalid_date
        if invalid_date:
            ex = _fmt_example(text[date_fail_mask].iloc[0])
            out["note"] = f"含 {invalid_date} 个无法解析的日期（如 {ex}）"
        return out

    # 5) 混合：两种转换皆失败的值为脏值
    if num_ok > 0 or date_ok > 0:
        neither = int((num_fail_mask & date_fail_mask).sum())
        out["detected_type"] = "mixed"
        out["dirty_count"] = neither
        if neither:
            ex = _fmt_example(text[num_fail_mask & date_fail_mask].iloc[0])
            out["note"] = f"{neither} 个脏值（如 {ex}）"
        return out

    # 6) 类别 / 文本（text 列顺带揪出"疑似数字文本"，如千分位/单位后缀的脏值）
    suspicious = text[text.str.contains(r"\d", regex=True, na=False)]
    s_count = int(suspicious.size)
    uniq = int(valid.nunique())
    threshold = min(50, int(n * 0.2))
    if uniq <= threshold:
        top3 = text.value_counts().head(3).index.tolist()
        out["detected_type"] = "category"
        out["note"] = "取值 top3: " + ", ".join(_fmt_example(v) for v in top3)
    else:
        out["detected_type"] = "text"
        if s_count:
            out["dirty_count"] = s_count
            out["note"] = f"含 {s_count} 个疑似数字/日期文本（如 {_fmt_example(suspicious.iloc[0])}）"
    return out


def data_type_check(file_path: str) -> dict:
    """识别每列类型（numeric/integer/category/date/text/mixed/missing）并输出脏数据提示。"""
    try:
        df = read_table(file_path)
        n_rows = len(df)
        columns = {}
        invalid_dates, mixed_cols, missing_cols = [], [], []
        for col in df.columns:
            s = df[col]
            d = (_judge_numeric_col(s) if pd.api.types.is_numeric_dtype(s)
                 else _judge_object_col(s, n_rows))
            columns[col] = d
            if d["detected_type"] == "missing":
                missing_cols.append(col)
            elif d["detected_type"] == "mixed":
                mixed_cols.append(col)
            elif d["detected_type"] == "date" and d["dirty_count"]:
                invalid_dates.append(col)

        # summary 由代码模板拼数字生成
        type_counts: dict[str, int] = {}
        for d in columns.values():
            type_counts[d["detected_type"]] = type_counts.get(d["detected_type"], 0) + 1
        parts = [f"共 {n_rows} 行 {df.shape[1]} 列"]
        parts.append("；".join(f"{k} {v} 列" for k, v in sorted(type_counts.items())))
        if missing_cols:
            parts.append(f"全缺失列：{', '.join(missing_cols)}，建议先处理")
        if invalid_dates:
            parts.append(f"含非法日期：{', '.join(invalid_dates)}")
        if mixed_cols:
            parts.append(f"混合脏数据列：{', '.join(mixed_cols)}")

        result = {
            "n_rows": n_rows,
            "n_columns": int(df.shape[1]),
            "columns": columns,
            "issue_summary": {
                "mixed_columns": mixed_cols,
                "fully_missing_columns": missing_cols,
                "invalid_date_columns": invalid_dates,
            },
        }
        return ok(result, "；".join(parts) + "。")
    except DataLabError as e:
        return err(e.code, str(e))
    except Exception:
        return err(EC.CALC, "计算失败，请检查数据内容与参数设置（详见服务端日志）")


def register(mcp) -> None:
    """注册到 MCPServer（mcp 2.x，工具名 = 函数名）。"""
    mcp.add_tool(data_type_check, description=__import__("sys").modules[__name__].__doc__)

