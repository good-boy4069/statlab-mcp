# -*- coding: utf-8 -*-
"""pca_analysis —— 建模组 · 主成分分析（工具 15，核心实现）。

docstring = agent 使用说明书，与 docs/design/05_modeling.md 同步维护。

参数:
    file_path (str): 本地数据文件（csv/tsv/xlsx/json）
    n_components (int): 主成分数，1 <= n <= min(样本数, 特征数)（超界中文报错）

口径:
    仅数值列（自动排除列出）；StandardScaler 标准化后 sklearn PCA（random_state=42，
    PCA 本身无随机性，仅为接口一致）；输出方差解释率+累积；
    载荷反标准化 = 成分向量 × 特征标准差（原单位近似权重，规格要求）；
    载荷图（方差解释条形 + 前两主成分载荷向量，__image__ 顶层）；
    结论注明"主成分是特征的线性组合，不等于业务因子"。

示例:
    pca_analysis("samples/clean.csv", n_components=2)
"""
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from matplotlib import pyplot as plt

from statlab_mcp.tools._common import (
    CJK_FONT_OK, DataLabError, err, ok, read_table, save_plot,
)


def pca_analysis(file_path: str, n_components: int) -> dict:
    """PCA 降维：方差解释率、反标准化载荷矩阵与载荷图。"""
    try:
        if isinstance(n_components, bool) or not isinstance(n_components, (int, np.integer)):
            raise DataLabError("n_components 必须是整数")
        n_components = int(n_components)
        df = read_table(file_path)
        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        excluded = [c for c in df.columns if c not in numeric_cols]
        if not numeric_cols:
            raise DataLabError("未找到数值列，无法做主成分分析")
        n_samples = int(len(df))
        n_features = len(numeric_cols)
        k_max = min(n_samples, n_features)
        if not (1 <= n_components <= k_max):
            raise DataLabError(f"n_components 必须在 1 到 min(样本,特征)={k_max} 之间")

        raw = df[numeric_cols].to_numpy(dtype=float)
        scaler = StandardScaler().fit(raw)
        Xs = scaler.transform(raw)
        pca = PCA(n_components=n_components, random_state=42).fit(Xs)

        evr = [float(v) for v in pca.explained_variance_ratio_]
        cum = []
        acc = 0.0
        for v in evr:
            acc += v
            cum.append(acc)
        # 载荷反标准化：成分向量 × 特征标准差（原单位近似权重）
        stds = scaler.scale_
        loadings: List[Dict[str, Any]] = []
        for i in range(n_components):
            for j, col in enumerate(numeric_cols):
                loadings.append({
                    "component": i + 1,
                    "feature": col,
                    "loading": float(pca.components_[i, j] * stds[j]),
                })

        # ---- 载荷图（方差解释条形 + PC1/PC2 载荷向量）----
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.5, 3.8))
        ax1.bar(range(1, n_components + 1), evr, color="#4C72B0")
        ax1.plot(range(1, n_components + 1), cum, "ro-", lw=1.2)
        ax1.set_title("方差解释率（红色=累积）" if CJK_FONT_OK
                      else "Explained variance (red=cumulative)")
        ax1.set_xlabel("主成分" if CJK_FONT_OK else "Component")
        ax1.set_ylabel("比例" if CJK_FONT_OK else "Ratio")
        if n_components >= 2:
            pc1 = {l["feature"]: l["loading"] for l in loadings if l["component"] == 1}
            pc2 = {l["feature"]: l["loading"] for l in loadings if l["component"] == 2}
            feats = numeric_cols
            ax2.bar(feats, [pc1[f] for f in feats], alpha=0.6, label="PC1")
            ax2.bar(feats, [pc2[f] for f in feats], alpha=0.6, label="PC2")
            ax2.axhline(0, color="gray", lw=0.7)
            ax2.set_title("载荷（反标准化）" if CJK_FONT_OK else "Loadings (de-standardized)")
            ax2.legend()
        else:
            ax2.text(0.5, 0.5, "单成分", ha="center",
                     transform=ax2.transAxes)
            ax2.axis("off")
        fig.tight_layout()
        img = save_plot(fig, "pca_analysis_all")

        # ---- 结论（模板）----
        top_note = []
        if n_components >= 1:
            pc_top = sorted((l for l in loadings if l["component"] == 1),
                            key=lambda x: -abs(x["loading"]))[:3]
            top_note = "、".join(f"{l['feature']}({l['loading']:.2f})" for l in pc_top)
        single_note = "；单特征数据，PCA 无降维意义（仅供参考）" if n_features == 1 else ""
        conclusion = (f"前 {n_components} 个主成分累计解释 {cum[-1]:.1%} 方差；"
                      f"PC1 主要载荷：{top_note}；主成分是特征线性组合，不等于业务因子{single_note}")
        summary = (f"PCA：PC1 解释 {evr[0]:.1%}" +
                   (f"、PC2 解释 {evr[1]:.1%}" if n_components >= 2 else "") +
                   f"（累计 {cum[-1]:.1%}）{single_note}；载荷图已保存")

        result = {
            "n_components": n_components,
            "n_features": n_features, "n_samples": n_samples,
            "excluded_columns": excluded,
            "explained_variance_ratio": evr,
            "cumulative_ratio": cum,
            "loadings": loadings,
            "conclusion": conclusion,
        }
        res = ok(result, summary)
        res["__image__"] = img
        return res
    except DataLabError as e:
        return err(str(e))
    except Exception as e:
        return err(f"计算失败: {e}")


def register(mcp) -> None:
    """注册到 MCPServer（mcp 2.x，工具名 = 函数名）。"""
    mcp.add_tool(pca_analysis)