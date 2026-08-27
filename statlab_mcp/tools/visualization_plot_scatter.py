"""plot_scatter —— 可视化组 · 散点图（工具 21，核心实现）。

生成 x-y 散点图，图上标注 Pearson r 与样本量；缺失按成对剔除并报数。
图协议走 _common.save_plot（附录 D）；返回顶层 __image__ 绝对路径。
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


def plot_scatter(file_path: str | None = None, x_col: str | None = None, y_col: str | None = None,
                   inline_data: list | dict | None = None) -> dict:
    """x-y 散点图（图上标 r 与 n）。"""
    try:
        # D17 连锁 optional 化的运行期强校验（SPEC §12.6）
        require_non_none(x_col=x_col, y_col=y_col)
        df, data_source = resolve_data(file_path, inline_data)
        for c in (x_col, y_col):
            if c not in df.columns:
                raise DataLabError(f"缺少必需列: {c}；实际列: {list(df.columns)}", EC.COLUMN_MISSING)
            if not pd.api.types.is_numeric_dtype(df[c]):
                raise DataLabError(f"列 {c} 不是数值列，无法画散点图", EC.COLUMN_TYPE)
        m = df[[x_col, y_col]].dropna()
        n = len(m)
        if n == 0:
            raise DataLabError(f"列 {x_col}/{y_col} 无有效数据（成对剔除后为空）", EC.INSUFFICIENT)
        dropped = int(len(df) - n)
        x, y = m[x_col].to_numpy(dtype=float), m[y_col].to_numpy(dtype=float)

        r = None
        if n >= 2 and float(x.std(ddof=1)) > 0 and float(y.std(ddof=1)) > 0:
            r = float(np.corrcoef(x, y)[0, 1])

        fig, ax = plt.subplots(figsize=(6.5, 5))
        ax.scatter(x, y, s=18, alpha=0.7)
        ax.set_xlabel(x_col)
        ax.set_ylabel(y_col)
        r_txt = f"，r={r:.2f}" if r is not None else "，r 不可计算（常量列或 n<2）"
        r_txt_en = f", r={r:.2f}" if r is not None else ", r n/a (constant or n<2)"  # L6：非 CJK 分支不再裸拼 None
        ax.set_title(f"{x_col} vs {y_col}（n={n}{r_txt}）"
                     if CJK_FONT_OK else f"{x_col} vs {y_col} (n={n}{r_txt_en})")
        fig.tight_layout()
        img = save_plot(fig, "plot_scatter_all")

        result = {"x_col": x_col, "y_col": y_col, "n": n,
                  "dropped_rows": dropped, "pearson_r": r}
        summary = (f"散点图已保存：{x_col} vs {y_col}（n={n}"
                   + (f"，r={r:.2f}" if r is not None else "，r 不可计算")
                   + (f"，成对剔除缺失 {dropped} 行" if dropped else "")
                   + "）；相关≠因果")
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
    mcp.add_tool(plot_scatter, description=__import__("sys").modules[__name__].__doc__)

