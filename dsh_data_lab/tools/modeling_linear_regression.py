# -*- coding: utf-8 -*-
"""linear_regression —— 建模组 · 线性回归（工具 12，核心实现）。

docstring = agent 使用说明书，与 docs/design/05_modeling.md 同步维护。

参数:
    file_path (str): 本地数据文件（csv/tsv/xlsx/json）
    target (str): 连续因变量（数值列）
    features (list[str]): 自变量（数值列直用；类别列自动 one-hot 并输出映射）
    add_constant (bool, True): 是否加截距（False 时 GOF 指标参考意义受限，注明）
    alpha (float, 0.05): 显著性阈值（报告用，∈(0,1)）

口径:
    statsmodels OLS 矩阵接口（禁 formula）；类别列 get_dummies(drop_first=False) + 映射；
    零方差列自动剔除并报告；缺失 listwise dropna 并注明"已剔除 N 行"；
    n <= 设计矩阵列数+2 拒绝（无法稳定估计）；VIF>10 标注强共线性；
    残差 Shapiro + Durbin-Watson；残差诊断图（残差vs拟合 + 直方图，__image__ 顶层）。

示例:
    linear_regression("samples/clean.csv", target="income", features=["age"])
    linear_regression("samples/clean.csv", target="score", features=["age", "category"])
"""
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats as sps
from statsmodels.api import add_constant as sm_add_constant  # 别名防参数名遮蔽
from statsmodels.api import OLS
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import durbin_watson
from matplotlib import pyplot as plt

from statlab_mcp.tools._common import (
    CJK_FONT_OK, DataLabError, err, ok, read_table, save_plot,
)


def _fmt_p(p: float) -> str:
    return "<0.001" if p < 0.001 else f"{p:.4f}"


def linear_regression(file_path: str, target: str, features: List[str],
                      add_constant: bool = True, alpha: float = 0.05) -> dict:
    """OLS 线性回归：系数表、整体拟合、VIF、残差诊断与图。"""
    try:
        if not (0 < alpha < 1):
            raise DataLabError("alpha 必须在 (0,1) 之间")
        if not isinstance(features, list) or not features:
            raise DataLabError("features 至少需要 1 个特征")
        if len(set(features)) != len(features):
            raise DataLabError("features 含重复项，请去重")
        df = read_table(file_path)
        if target not in df.columns:
            raise DataLabError(f"缺少必需列: {target}；实际列: {list(df.columns)}")
        for f in features:
            if f not in df.columns:
                raise DataLabError(f"缺少必需列: {f}；实际列: {list(df.columns)}")
        if not pd.api.types.is_numeric_dtype(df[target]):
            raise DataLabError(f"列 {target} 不是数值列，无法做线性回归")

        # ---- one-hot 类别特征 + 设计矩阵 ----
        dummy_mapping: Dict[str, str] = {}
        parts = []
        for f in features:
            if pd.api.types.is_numeric_dtype(df[f]):
                parts.append(df[f])
            else:
                dummies = pd.get_dummies(df[f], prefix=f)     # 列名 f_值
                for c in dummies.columns:
                    dummy_mapping[c] = f"{f}={c[len(f) + 1:]}"
                parts.append(dummies)
        X_raw = pd.concat(parts, axis=1).astype(float)   # dummy 默认 bool dtype，统一 float
        y = df[target]

        # ---- 缺失 listwise ----
        mask = y.notna()
        for c in X_raw.columns:
            mask &= X_raw[c].notna()
        dropped = int((~mask).sum())
        X, y = X_raw[mask].reset_index(drop=True), y[mask].reset_index(drop=True)
        if len(y) == 0:
            raise DataLabError("剔除缺失后无有效样本")

        # ---- 零方差列自动剔除 ----
        drop_zero = [c for c in X.columns if int(X[c].nunique()) <= 1]
        if drop_zero:
            X = X.drop(columns=drop_zero)
        if X.shape[1] == 0:
            raise DataLabError("特征均为零方差列，无法建模")

        # ---- 截距与样本量门槛 ----
        Xd = sm_add_constant(X, has_constant="add") if add_constant else X
        n_cols = int(Xd.shape[1])
        n_rows = int(len(y))
        if n_rows <= n_cols + 2:
            raise DataLabError(f"样本量不足（n={n_rows} ≤ 特征数+2={n_cols + 2}），无法稳定估计")

        model = OLS(y, Xd).fit()

        # ---- VIF（不含截距）----
        vifs: Dict[str, Optional[float]] = {}
        for i, c in enumerate(Xd.columns):
            if c == "const":
                vifs[c] = None
                continue
            if Xd.shape[1] == 1:
                vifs[c] = 1.0          # 单列：无其他特征可共线（且避免 VIF 删列成空矩阵）
                continue
            vifs[c] = float(variance_inflation_factor(Xd.to_numpy(dtype=float), i))

        # ---- 系数表 ----
        coeffs = []
        for name in Xd.columns:
            coeffs.append({
                "name": name,
                "beta": float(model.params[name]),
                "std_err": float(model.bse[name]),
                "t": float(model.tvalues[name]),
                "p_value": float(model.pvalues[name]),
                "vif": vifs[name],
            })
        vif_flags = [f"{c}({v:.1f})>10 强共线性" for c, v in vifs.items()
                     if v is not None and v > 10]

        # ---- 残差诊断 ----
        resid = model.resid.to_numpy(dtype=float)
        if 3 <= n_rows <= 5000:
            sh_stat, sh_p = sps.shapiro(resid)
            sh = {"statistic": float(sh_stat), "p_value": float(sh_p),
                  "normal": bool(sh_p > 0.05), "note": None}
        else:
            sh = {"statistic": None, "p_value": None, "normal": None,
                  "note": f"n={n_rows} 超出 Shapiro 适用范围 3~5000，自动跳过"}
        dw = float(durbin_watson(resid))

        # ---- 残差诊断图 ----
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.5, 3.6))
        ax1.scatter(model.fittedvalues, resid, s=18, alpha=0.7)
        ax1.axhline(0, color="red", lw=0.8)
        ax1.set_title("残差 vs 拟合值" if CJK_FONT_OK else "Residuals vs Fitted")
        ax1.set_xlabel("拟合值" if CJK_FONT_OK else "Fitted")
        ax1.set_ylabel("残差" if CJK_FONT_OK else "Residuals")
        ax2.hist(resid, bins=min(20, max(5, n_rows // 5)), edgecolor="white")
        ax2.set_title("残差直方图" if CJK_FONT_OK else "Residual Histogram")
        fig.tight_layout()
        img = save_plot(fig, "residuals_linear_regression_all")

        # ---- 结论与 summary ----
        sig = [c["name"] for c in coeffs
               if c["p_value"] is not None and c["p_value"] < alpha and c["name"] != "const"]
        sig_txt = "、".join(sig) if sig else "无"
        f_p = float(model.f_pvalue)
        gof_note = "（无截距模型，R²/F 参考意义受限）" if not add_constant else ""
        conclusion = (f"R²={float(model.rsquared):.2f}（调整后 "
                      f"{float(model.rsquared_adj):.2f}）{gof_note}，F 检验 "
                      f"p={_fmt_p(f_p)} 模型整体{'显著' if f_p < alpha else '不显著'}；"
                      f"p<α 的显著自变量：{sig_txt}")
        parts = [f"线性回归（n={n_rows}，已剔除缺失 {dropped} 行）{gof_note}",
                 f"R²={float(model.rsquared):.2f}，F={float(model.fvalue):.2f}(p={_fmt_p(f_p)})"]
        parts.append(f"显著系数 {len(sig)} 个：{sig_txt}" if sig else "无显著系数")
        if vif_flags:
            parts.append("VIF 异常：" + "；".join(vif_flags))
        else:
            parts.append("VIF 均 <10（无强共线性）")
        parts.append(f"残差 Shapiro p={_fmt_p(sh['p_value'])}" if sh["p_value"] is not None
                     else "残差 Shapiro 已跳过")
        parts.append(f"Durbin-Watson={dw:.2f}（≈2 无自相关）")
        parts.append("相关≠因果、未做外部验证")
        summary = "；".join(parts) + "。"

        result = {
            "method": "ols", "n": n_rows, "dropped_rows": dropped,
            "n_features": len(coeffs) - (1 if add_constant else 0),
            "add_constant": add_constant,
            "r_squared": float(model.rsquared),
            "adj_r_squared": float(model.rsquared_adj),
            "f_statistic": float(model.fvalue), "f_p_value": f_p,
            "durbin_watson": dw,
            "residual_shapiro": sh,
            "coefficients": coeffs,
            "vif_flags": vif_flags,
            "dummy_mapping": dummy_mapping, "drop_zero_var": drop_zero,
            "conclusion": conclusion,
        }
        res = ok(result, summary)
        res["__image__"] = img
        return res
    except DataLabError as e:
        return err(str(e))
    except Exception as e:
        return err("计算失败，请检查数据内容与参数设置（详见服务端日志）")


def register(mcp) -> None:
    """注册到 MCPServer（mcp 2.x，工具名 = 函数名）。"""
    mcp.add_tool(linear_regression, description=linear_regression.__doc__)
