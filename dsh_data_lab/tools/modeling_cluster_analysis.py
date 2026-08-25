# -*- coding: utf-8 -*-
"""cluster_analysis —— 建模组 · KMeans 聚类（工具 14，核心实现）。

docstring = agent 使用说明书，与 docs/design/05_modeling.md 同步维护。

参数:
    file_path (str): 本地数据文件（csv/tsv/xlsx/json）
    k (int): 簇数，2 <= k <= 样本数-1（非法中文报错）

口径:
    仅数值列（非数值列自动排除并列出）；StandardScaler z-score 标准化后
    KMeans(n_clusters=k, random_state=42, n_init="auto")；质心反标准化回原始单位
    （标准化空间质心即簇内均值，反标准化后 = 原空间簇均值，可手算核对）；
    质心解读强制附簇内样本量；轮廓系数（标准化空间）+ k-1/k+1 同 seed 对照。

示例:
    cluster_analysis("samples/clean.csv", k=3)
"""
from typing import Any, Dict

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from statlab_mcp.tools._common import DataLabError, err, ok, read_table


def _run_kmeans(Xs: np.ndarray, k: int):
    km = KMeans(n_clusters=k, random_state=42, n_init="auto").fit(Xs)
    sil = float(silhouette_score(Xs, km.labels_))
    return km, sil


def cluster_analysis(file_path: str, k: int) -> dict:
    """KMeans 聚类：反标准化质心 + 簇样本量 + 轮廓系数（含 k±1 对照）。"""
    try:
        if isinstance(k, bool) or not isinstance(k, (int, np.integer)):
            raise DataLabError("k 必须是整数")
        k = int(k)
        df = read_table(file_path)
        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        excluded = [c for c in df.columns if c not in numeric_cols]
        if not numeric_cols:
            raise DataLabError("未找到数值列，无法聚类")
        n = int(len(df))
        if not (2 <= k <= n - 1):
            raise DataLabError(f"k 必须在 2 到 N-1 之间（样本数 N={n}）")

        raw = df[numeric_cols].to_numpy(dtype=float)
        scaler = StandardScaler().fit(raw)
        Xs = scaler.transform(raw)                     # 标准化（z-score）
        km, sil = _run_kmeans(Xs, k)

        # ---- 质心反标准化回原单位 ----
        centroids = scaler.inverse_transform(km.cluster_centers_)
        counts = np.bincount(km.labels_, minlength=k)
        clusters = []
        for c in range(k):
            centro = {numeric_cols[j]: float(centroids[c, j]) for j in range(len(numeric_cols))}
            clusters.append({
                "cluster": int(c),
                "n_members": int(counts[c]),
                "centroid_original_units": centro,
            })

        # ---- k±1 对照 ----
        compare: Dict[str, Any] = {}
        if k > 2:
            _, s1 = _run_kmeans(Xs, k - 1)
            compare["k_minus_1"] = {"k": k - 1, "silhouette": s1}
        else:
            compare["k_minus_1"] = None                # k 已是最小值
        if k < n - 1:
            _, s2 = _run_kmeans(Xs, k + 1)
            compare["k_plus_1"] = {"k": k + 1, "silhouette": s2}
        else:
            compare["k_plus_1"] = None

        sil_label = ("结构良好" if sil > 0.5 else "可接受" if sil > 0.25 else "结构弱")
        sizes = "；".join(f"簇{c} {clusters[c]['n_members']} 人" for c in range(k))
        cmp_txt = []
        if compare["k_minus_1"]:
            cmp_txt.append(f"k={k-1} 时为 {compare['k_minus_1']['silhouette']:.2f}")
        if compare["k_plus_1"]:
            cmp_txt.append(f"k={k+1} 时为 {compare['k_plus_1']['silhouette']:.2f}")
        cmp_s = "、".join(cmp_txt)
        summary = (f"k={k} 聚类完成：轮廓系数 {sil:.2f}（{sil_label}）"
                   + (f"；对照 {cmp_s}" if cmp_s else "")
                   + f"；各簇样本量：{sizes}；标准化(z-score)后计算，质心已还原原单位")

        result = {
            "k": k, "n_samples": n,
            "excluded_columns": excluded,
            "standardized": True,
            "silhouette": sil,
            "silhouette_compare": compare,
            "clusters": clusters,
            "conclusion": (f"k={k}，轮廓系数 {sil:.2f}（{sil_label}）；"
                           f"k 的选择需结合业务判断（轮廓系数仅参考）"),
        }
        return ok(result, summary)
    except DataLabError as e:
        return err(str(e))
    except Exception as e:
        return err(f"计算失败: {e}")


def register(mcp) -> None:
    """注册到 MCPServer（mcp 2.x，工具名 = 函数名）。"""
    mcp.add_tool(cluster_analysis)