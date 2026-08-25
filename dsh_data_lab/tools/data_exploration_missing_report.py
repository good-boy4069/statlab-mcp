# -*- coding: utf-8 -*-
"""missing_report —— 数据探查组 · 缺失报告（工具 3，核心实现）。

docstring = agent 使用说明书，与 docs/design/01_data_exploration_batch1.md 同步维护。

参数:
    file_path (str): 本地数据文件（csv/tsv/xlsx/json），仅接受本地路径（拒绝 UNC）

返回:
    成功 {"status":"ok","result":{...},"summary":"一句话中文结论"}
    失败 {"status":"error","message":"中文原因"}
    result: {n_rows, n_columns, total_missing, overall_missing_rate,
             columns: {<列名>: {n_missing, missing_rate}},
             complete_rows, rows_with_missing,
             patterns: [{columns, rows, note}]}

缺失定义: 空单元格与空串在读表层统一为 NaN（read_csv 默认），一律计入缺失；
全缺失列 rate=1.0 并注记；成对模式 = 两列同时缺失的行数（同源故障信号）；
patterns 最多 10 条，按缺失行数降序；无缺失时 patterns=[]。

示例:
    missing_report("samples/dirty.csv")
"""
from typing import Any, Dict, List

import pandas as pd

from statlab_mcp.tools._common import DataLabError, err, ok, read_table

MAX_PATTERNS = 10
HIGH_RATE = 0.2


def missing_report(file_path: str) -> dict:
    """输出各列缺失数量/缺失率与缺失模式（单列/成对/全缺失）。"""
    try:
        df = read_table(file_path)
        n_rows = int(len(df))
        n_columns = int(df.shape[1])
        mask = df.isna()
        per_col = mask.sum()

        total_missing = int(mask.to_numpy().sum())
        overall_rate = total_missing / float(n_rows * n_columns) if n_rows * n_columns else 0.0
        columns: Dict[str, Any] = {
            c: {"n_missing": int(per_col[c]), "missing_rate": float(per_col[c]) / n_rows}
            for c in df.columns
        }
        complete_rows = int((~mask.any(axis=1)).sum())
        rows_with_missing = n_rows - complete_rows

        # 缺失模式：单列（全缺失列注记）+ 成对（同时缺失行数），行数降序取前 10
        missing_cols = [c for c in df.columns if per_col[c] > 0]
        patterns: List[Dict[str, Any]] = []
        for c in missing_cols:
            r = int(per_col[c])
            patterns.append({"columns": [c], "rows": r,
                             "note": "全缺失列" if r == n_rows else None})
        for i in range(len(missing_cols)):
            for j in range(i + 1, len(missing_cols)):
                a, b = missing_cols[i], missing_cols[j]
                r = int((mask[a] & mask[b]).sum())
                if r > 0:
                    patterns.append({"columns": [a, b], "rows": r, "note": None})
        patterns.sort(key=lambda x: (-x["rows"], len(x["columns"])))
        patterns = patterns[:MAX_PATTERNS]

        # summary 由代码模板拼数字生成
        if total_missing == 0:
            summary = f"共 {n_rows} 行 {n_columns} 列，数据完整无缺失。"
        else:
            keep_rows = [c for c in df.columns if columns[c]["n_missing"] > 0]
            high = [c for c in keep_rows if columns[c]["missing_rate"] >= HIGH_RATE]
            parts = [
                f"共 {n_rows} 行 {n_columns} 列，总缺失 {total_missing} 个"
                f"（缺失率 {overall_rate:.1%}）；"
                f"完整行 {complete_rows} 行（{complete_rows / n_rows:.1%}）"
            ]
            if high:
                parts.append(f"高缺失列（≥{HIGH_RATE:.0%}）：{', '.join(high)}")
            summary = "；".join(parts) + "。"

        result = {
            "n_rows": n_rows,
            "n_columns": n_columns,
            "total_missing": total_missing,
            "overall_missing_rate": overall_rate,
            "columns": columns,
            "complete_rows": complete_rows,
            "rows_with_missing": rows_with_missing,
            "patterns": patterns,
        }
        return ok(result, summary)
    except DataLabError as e:
        return err(str(e))
    except Exception as e:
        return err("计算失败，请检查数据内容与参数设置（详见服务端日志）")


def register(mcp) -> None:
    """注册到 MCPServer（mcp 2.x，工具名 = 函数名）。"""
    mcp.add_tool(missing_report, description=__import__("sys").modules[__name__].__doc__)

