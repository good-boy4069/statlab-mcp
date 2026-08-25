"""outlier_detect —— 数据探查组 · 异常值检测（工具 5，核心实现）。

docstring = agent 使用说明书，与 docs/design/02_data_exploration_batch2.md 同步维护。

参数:
    file_path (str): 本地数据文件（csv/tsv/xlsx/json），仅接受本地路径
    method (str, "iqr"): 仅支持 iqr（规格 4 唯一定义；zscore 场景在时序组 rolling_zscore）

口径:
    IQR 法：lower = Q1 - 1.5*IQR，upper = Q3 + 1.5*IQR（分位数 linear 插值，同 describe）；
    异常值 = 有效值中 <lower 或 >upper 的值；绝不自动剔除，只报告；
    数值列有效值 n<4 → IQR 无定义，bounds=null、n_outliers=0；常量列 bounds 相等无异常；
    非数值列跳过并列入 skipped_columns；单列异常值超 100 个时截断显示并注明。

图（附录 D）: 并列箱线图（异常值红色 scatter）；文件名 outlier_detect_all_YYYYmmdd_HHMMSS.png
存 reports/plots/；返回 JSON 顶层附加 __image__（绝对路径，禁 base64，与 result 平级）。

示例:
    outlier_detect("samples/dirty.csv")
"""
from typing import Any

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

from statlab_mcp.tools._common import (
    CJK_FONT_OK,
    DataLabError,
    err,
    ok,
    read_table,
    save_plot,
)

IQR_K = 1.5
MIN_N = 4
MAX_OUTLIERS_PER_COL = 100


def _detect_col(s: pd.Series) -> dict[str, Any]:
    """单列 IQR 检测：返回边界、异常行号（0 基，原行序）与数值。"""
    valid = s.dropna()
    n = int(valid.size)
    if n < MIN_N:
        return {"n_outliers": 0, "lower_bound": None, "upper_bound": None,
                "outlier_indices": [], "outlier_values": [], "n": n}
    q1 = float(valid.quantile(0.25, interpolation="linear"))
    q3 = float(valid.quantile(0.75, interpolation="linear"))
    iqr = q3 - q1
    lo, hi = q1 - IQR_K * iqr, q3 + IQR_K * iqr
    mask = (valid < lo) | (valid > hi)
    rows = [int(r) for r in valid.index[mask].tolist()]
    vals = [float(v) for v in valid[mask].tolist()]
    truncated = len(vals) > MAX_OUTLIERS_PER_COL
    return {
        "n_outliers": int(np.count_nonzero(mask)),
        "lower_bound": lo,
        "upper_bound": hi,
        "outlier_indices": rows[:MAX_OUTLIERS_PER_COL],
        "outlier_values": vals[:MAX_OUTLIERS_PER_COL],
        "truncated": truncated,
        "n": n,
    }


def _plot_boxplot(df: pd.DataFrame, cols: list[str], columns: dict[str, Any]) -> Any:
    """并列箱线图：异常值红色 scatter；无中文字体时自动切换英文标题（降级约定）。"""
    fig, ax = plt.subplots(figsize=(max(6.0, 1.4 * len(cols)), 4.2))
    data = [df[c].dropna().to_numpy() for c in cols]
    ax.boxplot(data, patch_artist=True)   # matplotlib 3.11 已移除 labels 参数
    ax.set_xticks(range(1, len(cols) + 1))
    ax.set_xticklabels(cols)
    total = sum(d["n_outliers"] for d in columns.values())
    title = f"箱线图（IQR 法，红色=异常值，共 {total} 个）" if CJK_FONT_OK else \
        f"Boxplot (IQR, red=outliers, n={total})"
    ax.set_title(title)
    if not CJK_FONT_OK:
        ax.set_xlabel("column")  # 降级英文并在图内注明
    labeled = False
    for i, c in enumerate(cols, start=1):
        d = columns[c]
        if d["outlier_indices"]:
            vals = df[c].dropna()
            ys = [float(vals.loc[r]) for r in d["outlier_indices"]]
            ax.scatter([i] * len(ys), ys, color="red", zorder=3, s=28,
                       label="异常值" if not labeled else None)
            labeled = True
    if labeled:
        ax.legend(loc="upper right")
    fig.tight_layout()
    return fig


def outlier_detect(file_path: str, method: str = "iqr") -> dict:
    """按 IQR 规则检测各数值列异常值，输出位置/数值与箱线图（异常红色标注）。"""
    try:
        if method != "iqr":
            raise DataLabError("method 仅支持 iqr")
        df = read_table(file_path)
        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        skipped = [c for c in df.columns if c not in numeric_cols]
        if not numeric_cols:
            raise DataLabError("至少需要 1 个数值列才能检测异常值")

        columns = {c: _detect_col(df[c]) for c in numeric_cols}
        total = int(sum(d["n_outliers"] for d in columns.values()))

        fig = _plot_boxplot(df, numeric_cols, columns)
        image_path = save_plot(fig, "outlier_detect_all")

        result = {
            "method": method,
            "n_numeric_cols": len(numeric_cols),
            "n_outliers_total": total,
            "skipped_columns": skipped,
            "columns": columns,
        }
        per_col = "；".join(f"{c} {d['n_outliers']} 个" for c, d in columns.items() if d["n_outliers"])
        if total == 0:
            summary = (f"共稽查 {len(numeric_cols)} 个数值列，未发现异常值；"
                       f"箱线图已保存至 reports/plots/")
        else:
            summary = (f"共发现 {total} 个异常值：{per_col}；"
                       f"异常值仅报告不剔除；箱线图已保存至 reports/plots/")
        if skipped:
            summary += f"；已跳过 {len(skipped)} 列非数值（{', '.join(skipped[:5])}）"
        if any(d["n"] < MIN_N for d in columns.values()):
            summary += "；样本不足 4 的列无法定义 IQR（bounds 为无）"

        res = ok(result, summary)
        res["__image__"] = image_path     # 顶层可选字段（红队裁决 3），与 result 平级
        return res
    except DataLabError as e:
        return err(str(e))
    except Exception:
        return err("计算失败，请检查数据内容与参数设置（详见服务端日志）")


def register(mcp) -> None:
    """注册到 MCPServer（mcp 2.x，工具名 = 函数名）。"""
    mcp.add_tool(outlier_detect, description=__import__("sys").modules[__name__].__doc__)

