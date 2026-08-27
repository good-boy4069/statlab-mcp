"""plot_box —— 可视化组 · 箱线图（工具 25，核心实现）。

单列箱线图：图上标五数概括（min/q1/中位/q3/max）与 IQR 异常数（同 outlier_detect 口径，
但仅单列、无异常点导出表——异常定位请用工具 5）。
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
    err,
    ok,
    require_non_none,
    resolve_data,
    save_plot,
)

MIN_N = 4


def plot_box(file_path: str | None = None, column: str | None = None,
                   inline_data: list | dict | None = None) -> dict:
    """单列箱线图（图上标五数 + 异常数）。"""
    # D17 连锁 optional 化的运行期强校验（SPEC §12.6）
    require_non_none(column=column)
    try:
        df, data_source = resolve_data(file_path, inline_data)
        if column not in df.columns:
            raise DataLabError(f"缺少必需列: {column}；实际列: {list(df.columns)}", EC.COLUMN_MISSING)
        if not pd.api.types.is_numeric_dtype(df[column]):
            raise DataLabError(f"列 {column} 不是数值列，无法画箱线图", EC.COLUMN_TYPE)
        v = df[column].dropna()
        n = int(v.size)
        if n == 0:
            raise DataLabError(f"列 {column} 无有效数据", EC.INSUFFICIENT)
        n_missing = int(len(df) - n)

        q1 = float(v.quantile(0.25)) if n >= MIN_N else None
        q3 = float(v.quantile(0.75)) if n >= MIN_N else None
        median = float(v.median())
        v_min = float(v.min())
        v_max = float(v.max())
        n_outliers = 0
        if n >= MIN_N:
            iqr = q3 - q1
            lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            arr = v.to_numpy(dtype=float)
            # 常数列（iqr=0）无异常（同 outlier_detect）
            n_outliers = (0 if iqr == 0
                          else int(np.sum((arr < lo) | (arr > hi))))
        else:
            lo = hi = None

        fig, ax = plt.subplots(figsize=(3.6, 4.4))
        ax.boxplot(v.to_numpy(dtype=float))
        ax.set_xticks([])
        ax.set_ylabel(column)
        stats_txt = f"n={n}，min={v_min:.2f}，max={v_max:.2f}"
        if q1 is not None:
            stats_txt += f"，Q1={q1:.2f}，中位={median:.2f}，Q3={q3:.2f}"
        stats_txt += f"，异常={n_outliers}"
        ax.set_title(f"{column} 箱线图（{stats_txt}）" if CJK_FONT_OK
                     else f"{column} boxplot ({stats_txt})")
        fig.tight_layout()
        img = save_plot(fig, f"plot_box_{column}")

        result = {"column": column, "n": n, "n_missing": n_missing,
                  "min": v_min, "max": v_max,
                  "q1": q1, "median": median, "q3": q3,
                  "lower_bound": lo, "upper_bound": hi,
                  "n_outliers": n_outliers}
        summary = (f"箱线图已保存：{column}（n={n}，min={v_min:.2f}/max={v_max:.2f}"
                   + (f"，Q1={q1:.2f}/中位 {median:.2f}/Q3={q3:.2f}" if q1 is not None
                      else "，样本不足 4 无法定义 IQR")
                   + f"，IQR 异常 {n_outliers} 个"
                   + (f"，缺失 {n_missing}" if n_missing else "") + "）")
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
    mcp.add_tool(plot_box, description=__import__("sys").modules[__name__].__doc__)

