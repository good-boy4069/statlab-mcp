# -*- coding: utf-8 -*-
"""effect_size —— 统计推断组 · 效应量（工具 11，简化实现）。

docstring = agent 使用说明书，与 docs/design/04_inference_batch2.md 同步维护。

参数:
    file_path (str): 本地数据文件（csv/tsv/xlsx/json）
    group_col (str): 分组列（须恰好 2 组）
    value_col (str): 数值列
    method (str, "cohens_d"): cohens_d / hedges_g / cliff_delta
    paired (bool, False): True 时两组样本数必须相等，按"各自有效值序列的
        第 i 个"配对（简化语义：无 ID 列时的确定性约定，见设计文档）

口径:
    cohens_d: |m1-m2|/pooled_sd（pooled_sd 同 hypothesis_test）
    hedges_g: d * (1 - 3/(4(n1+n2)-9))（小样本修正）
    cliff_delta: delta = (gt-lt)/(n1*n2)，gt/lt 为所有跨组值对比较计数（numpy 向量化，
        不依赖 mannwhitneyu 的 U 定义，避免方向歧义）
    CI: 正态近似 se（d/g: sqrt(1/n1+1/n2+d^2/(2(n1+n2)))；cliff: sqrt((1-delta^2)/(n1*n2))），
        mean ± 1.96*se；输出注明"正态近似"
    阈值（标注为经验惯例）：d/g 0.2/0.5/0.8（Cohen）；cliff 0.147/0.33/0.474（Romano）

【简化】略过声明: 无 bootstrap CI、无分布假设检验、cliff_delta 无配对版本。

示例:
    effect_size("samples/clean.csv", group_col="category", value_col="score")
"""
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from statlab_mcp.tools._common import DataLabError, err, ok, read_table

_METHODS = {"cohens_d", "hedges_g", "cliff_delta"}
Z_975 = 1.959963984540054
D_THRESHOLDS = [(0.2, "小"), (0.5, "中"), (0.8, "大")]
CLIFF_THRESHOLDS = [(0.147, "小"), (0.33, "中"), (0.474, "大")]


def _label(v: float, thrs: List[Any]) -> str:
    for t, name in thrs:
        if v < t:
            return name
    return "大"          # 超过最大阈值仍记"大"（设计文档档位：小/中/大）


def _cliff_delta(x: np.ndarray, y: np.ndarray) -> float:
    gt = int(np.count_nonzero(x[:, None] > y[None, :]))
    lt = int(np.count_nonzero(x[:, None] < y[None, :]))
    return float((gt - lt) / (x.size * y.size))


def effect_size(file_path: str, group_col: str, value_col: str,
                method: str = "cohens_d", paired: bool = False) -> dict:
    """两组差异的效应量（d/g/cliff_delta）+ 正态近似 95% CI + 经验阈值解释。"""
    try:
        if method not in _METHODS:
            raise DataLabError("method 仅支持 cohens_d/hedges_g/cliff_delta")
        df = read_table(file_path)
        for c in (group_col, value_col):
            if c not in df.columns:
                raise DataLabError(f"缺少必需列: {c}；实际列: {list(df.columns)}")
        if not pd.api.types.is_numeric_dtype(df[value_col]):
            raise DataLabError(f"列 {value_col} 不是数值列，无法计算效应量")
        if df[group_col].notna().sum() == 0:
            raise DataLabError(f"列 {group_col} 无有效数据")

        keys = list(dict.fromkeys(df[group_col].dropna().values))
        if len(keys) != 2:
            raise DataLabError("effect_size 只支持恰好 2 组比较")
        g1, g2 = keys[0], keys[1]
        x = df.loc[df[group_col] == g1, value_col].dropna().to_numpy(dtype=float)
        y = df.loc[df[group_col] == g2, value_col].dropna().to_numpy(dtype=float)
        if x.size < 2 or y.size < 2:
            raise DataLabError(f"组 {g1}(n={x.size}) / {g2}(n={y.size}) 样本量不足 2")
        if paired and method == "cliff_delta":
            raise DataLabError("cliff_delta 暂不支持配对模式（简化实现）")
        if paired and x.size != y.size:
            raise DataLabError("paired=True 要求两组样本数相等（按行序配对）")

        n1, n2 = int(x.size), int(y.size)
        mean1, mean2 = float(x.mean()), float(y.mean())
        if paired:  # 简化配对：各自有效值序列按位置配对
            diffs = x - y
            sd_diff = float(diffs.std(ddof=1))
            if sd_diff == 0:
                raise DataLabError("配对差值无变异（所有差值相同），无法计算效应量")
            d = abs(float(diffs.mean())) / sd_diff
            se = float(np.sqrt(1.0 / n1 + d ** 2 / (2 * n1)))   # 配对近似
            threshold = D_THRESHOLDS
        else:
            pooled = float(np.sqrt(((n1 - 1) * float(x.var(ddof=1))
                                    + (n2 - 1) * float(y.var(ddof=1))) / (n1 + n2 - 2)))
            if pooled == 0:
                raise DataLabError("两组合并方差为 0（全常量），无法计算效应量")
            d = abs(mean1 - mean2) / pooled
            if method == "cliff_delta":
                d = _cliff_delta(x, y)
                se = float(np.sqrt((1 - d ** 2) / (n1 * n2)))
                threshold = CLIFF_THRESHOLDS
            else:
                se = float(np.sqrt(1.0 / n1 + 1.0 / n2 + d ** 2 / (2 * (n1 + n2))))
                threshold = D_THRESHOLDS

        if method == "hedges_g":
            d = d * (1 - 3 / (4 * (n1 + n2) - 9))       # 小样本修正
            se = float(np.sqrt(1.0 / n1 + 1.0 / n2 + d ** 2 / (2 * (n1 + n2))))

        ci_lower, ci_upper = d - Z_975 * se, d + Z_975 * se
        label = _label(d, threshold)

        result = {
            "method": method, "paired": paired,
            "n1": n1, "n2": n2, "mean1": mean1, "mean2": mean2,
            "effect_size": d, "ci_lower": ci_lower, "ci_upper": ci_upper,
            "ci_note": "正态近似",
            "interpretation": {"label": label, "thresholds":
                "d/g: 小<0.2, 中<0.5, 大<0.8（Cohen）" if threshold is D_THRESHOLDS
                else "cliff_delta: 小<0.147, 中<0.33, 大<0.474（Romano）"},
        }
        tname = {"cohens_d": "Cohen's d", "hedges_g": "Hedges' g",
                 "cliff_delta": "Cliff's delta"}[method]
        c0 = "CI 含 0，效应不显著" if ci_lower <= 0 <= ci_upper else "CI 不含 0，效应显著"
        summary = (f"{tname}={d:.3f}（95% CI [{ci_lower:.3f}, {ci_upper:.3f}]，正态近似），"
                   f"{label}效应；{c0}")
        return ok(result, summary)
    except DataLabError as e:
        return err(str(e))
    except Exception as e:
        return err("计算失败，请检查数据内容与参数设置（详见服务端日志）")


def register(mcp) -> None:
    """注册到 MCPServer（mcp 2.x，工具名 = 函数名）。"""
    mcp.add_tool(effect_size, description=effect_size.__doc__)
