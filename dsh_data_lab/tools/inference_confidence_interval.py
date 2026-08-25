# -*- coding: utf-8 -*-
"""confidence_interval —— 统计推断组 · 置信区间（工具 10，核心实现）。

docstring = agent 使用说明书，与 docs/design/03_inference_batch1.md 同步维护。

参数:
    file_path (str): 本地数据文件（csv/tsv/xlsx/json）
    column (str): 分析列（须为数值列）
    confidence (float, 0.95): 置信水平 ∈ (0,1)
    method (str, "mean_t"): mean_t / bootstrap_median
        mean_t: mean ± t_{1-α/2, n-1} * sd/√n（sd 用 ddof=1，与 describe 同口径）
        bootstrap_median: 局部 default_rng(42) 重采样 1000 次取中位数，2.5%/97.5%
        分位数（percentile 法）——每次调用独立可复现（不依赖全局 rng 状态）

边界: n<3 / confidence 越界 / method 非法 / 非数值或缺列 —— 中文报错；
      常数列（sd=0）区间退化为点并注明。

示例:
    confidence_interval("samples/clean.csv", column="income")
    confidence_interval("samples/clean.csv", column="income", confidence=0.90,
                        method="bootstrap_median")
"""
from typing import Any, Dict

import numpy as np
import pandas as pd
from scipy import stats as sps

from statlab_mcp.tools._common import DataLabError, err, ok, read_table

_METHODS = {"mean_t", "bootstrap_median"}
N_BOOTSTRAP = 1000
BOOT_SEED = 42


def confidence_interval(file_path: str, column: str, confidence: float = 0.95,
                        method: str = "mean_t") -> dict:
    """均值（t 分布）或中位数（bootstrap）的置信区间。"""
    try:
        if method not in _METHODS:
            raise DataLabError("method 仅支持 mean_t/bootstrap_median")
        if not (0 < confidence < 1):
            raise DataLabError("confidence 必须在 (0,1) 之间")
        df_all = read_table(file_path)
        if column not in df_all.columns:
            raise DataLabError(f"缺少必需列: {column}；实际列: {list(df_all.columns)}")
        if not pd.api.types.is_numeric_dtype(df_all[column]):
            raise DataLabError(f"列 {column} 不是数值列，无法计算置信区间")
        x = df_all[column].dropna().to_numpy(dtype=float)
        n = int(x.size)
        if n < 3:
            raise DataLabError(f"至少需要 3 个有效值，当前 {n}")

        alpha = 1 - confidence
        if method == "mean_t":
            mean = float(x.mean())
            sd = float(x.std(ddof=1))
            se = sd / np.sqrt(n)
            t_crit = float(sps.t.ppf(1 - alpha / 2, n - 1))
            margin = t_crit * se
            ci_lower, ci_upper = mean - margin, mean + margin
            result: Dict[str, Any] = {
                "method": method, "confidence": confidence, "n": n,
                "point_estimate": mean, "estimate_type": "mean",
                "ci_lower": ci_lower, "ci_upper": ci_upper,
                "std_error": se, "margin": margin,
                "n_bootstrap": None, "seed": None,
            }
            est_name = "均值"
        else:
            rng = np.random.default_rng(BOOT_SEED)      # 局部固定种子：每次调用独立可复现
            meds = np.array([
                float(np.median(rng.choice(x, size=n, replace=True)))
                for _ in range(N_BOOTSTRAP)
            ])
            ci_lower, ci_upper = (
                float(np.percentile(meds, (1 - confidence) * 50)),
                float(np.percentile(meds, (1 + confidence) * 50)),
            )
            median = float(np.median(x))
            result = {
                "method": method, "confidence": confidence, "n": n,
                "point_estimate": median, "estimate_type": "median",
                "ci_lower": ci_lower, "ci_upper": ci_upper,
                "std_error": None, "margin": None,
                "n_bootstrap": N_BOOTSTRAP, "seed": BOOT_SEED,
            }
            est_name = "中位数"

        note = "（常数列：区间退化为点）" if method == "mean_t" and float(x.std(ddof=1)) == 0 else ""
        summary = (f"{est_name} {result['point_estimate']:.2f} 的 "
                   f"{int(confidence * 100)}% 置信区间为 "
                   f"[{ci_lower:.2f}, {ci_upper:.2f}]"
                   f"（{'t 分布' if method == 'mean_t' else f'bootstrap {N_BOOTSTRAP} 次, seed={BOOT_SEED}'}，"
                   f"n={n}）{note}")
        return ok(result, summary)
    except DataLabError as e:
        return err(str(e))
    except Exception as e:
        return err(f"计算失败: {e}")


def register(mcp) -> None:
    """注册到 MCPServer（mcp 2.x，工具名 = 函数名）。"""
    mcp.add_tool(confidence_interval)