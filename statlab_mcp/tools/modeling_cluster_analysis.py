"""cluster_analysis —— 建模组 · KMeans 聚类（工具 14，核心实现）。

docstring = agent 使用说明书，与 statlab_mcp/docs/design/05_modeling.md 同步维护。

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
inline 数据:
    本工具支持可选 inline_data 参数（v1.2.0 起）：与 file_path 二选一，
    支持 records 数组或 {"header": [...], "rows": [[...], ...]} 对象两种形态；
    规模上限/类型域/data_source 来源标注见 statlab_mcp/docs/SPEC.md 第 12 节。

"""
from typing import Any

import numpy as np
import pandas as pd

from statlab_mcp.tools._common import EC, DataLabError, err, ok, require_non_none, resolve_data


def _run_kmeans(Xs: np.ndarray, k: int | None = None):
    """KMeans 单次拟合（seed=42 确定性）+ 轮廓系数，供 k±1 对照复用。"""
    from sklearn.cluster import KMeans  # 延迟导入（P1-1）
    from sklearn.metrics import silhouette_score
    km = KMeans(n_clusters=k, random_state=42, n_init="auto").fit(Xs)
    sil = float(silhouette_score(Xs, km.labels_))
    return km, sil


def cluster_analysis(file_path: str | None = None, k: int | None = None,
                   inline_data: list | dict | None = None) -> dict:
    """KMeans 聚类：反标准化质心 + 簇样本量 + 轮廓系数（含 k±1 对照）。"""
    # D17 连锁 optional 化的运行期强校验（SPEC §12.6）
    require_non_none(k=k)
    try:
        if isinstance(k, bool) or not isinstance(k, (int, np.integer)):
            raise DataLabError("k 必须是整数", EC.PARAM)
        k = int(k)
        df, data_source = resolve_data(file_path, inline_data)
        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        excluded = [c for c in df.columns if c not in numeric_cols]
        if not numeric_cols:
            raise DataLabError("未找到数值列，无法聚类", EC.INSUFFICIENT)
        n = len(df)
        # 含 NaN 数值列须 listwise 剔除并报告（与 linear/logistic 对齐；否则 KMeans 抛
        # "Input contains NaN" 被通用 except 吞成"计算失败"，外部评审 M3）
        raw_df = df[numeric_cols].dropna()
        n_used = len(raw_df)
        dropped = n - n_used
        if n_used == 0:
            raise DataLabError("所有行的数值列均含缺失值，无法聚类", EC.INSUFFICIENT)
        if not (2 <= k <= n_used - 1):
            raise DataLabError(
                f"k 必须在 2 到有效样本数-1 之间（剔除缺失后有效样本 N={n_used}）", EC.PARAM)

        raw = raw_df.to_numpy(dtype=float)
        from sklearn.preprocessing import StandardScaler  # 延迟导入（P1-1，与 _run_kmeans 内配合覆盖主函数使用点）
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
        compare: dict[str, Any] = {}
        if k > 2:
            _, s1 = _run_kmeans(Xs, k - 1)
            compare["k_minus_1"] = {"k": k - 1, "silhouette": s1}
        else:
            compare["k_minus_1"] = None                # k 已是最小值
        if k < n_used - 1:
            _, s2 = _run_kmeans(Xs, k + 1)
            compare["k_plus_1"] = {"k": k + 1, "silhouette": s2}
        else:
            compare["k_plus_1"] = None

        sil_label = ("结构良好" if sil > 0.5 else "可接受" if sil > 0.25 else "结构弱")
        sizes = "；".join(f"簇{c} {clusters[c]['n_members']} 个样本" for c in range(k))
        cmp_txt = []
        if compare["k_minus_1"]:
            cmp_txt.append(f"k={k-1} 时为 {compare['k_minus_1']['silhouette']:.2f}")
        if compare["k_plus_1"]:
            cmp_txt.append(f"k={k+1} 时为 {compare['k_plus_1']['silhouette']:.2f}")
        cmp_s = "、".join(cmp_txt)
        summary = (f"k={k} 聚类完成：轮廓系数 {sil:.2f}（{sil_label}）"
                   + (f"；对照 {cmp_s}" if cmp_s else "")
                   + f"；各簇样本量：{sizes}"
                   + (f"；已剔除 {dropped} 行含缺失值" if dropped else "")
                   + "；标准化(z-score)后计算，质心已还原原单位")

        result = {
            "k": k, "n_samples": n_used,
            "dropped_na_rows": dropped,
            "excluded_columns": excluded,
            "standardized": True,
            "silhouette": sil,
            "silhouette_compare": compare,
            "clusters": clusters,
            "conclusion": (f"k={k}，轮廓系数 {sil:.2f}（{sil_label}）；"
                           f"k 的选择需结合业务判断（轮廓系数仅参考）"),
        }
        _payload = ok(result, summary)
        _payload["data_source"] = data_source
        return _payload
    except DataLabError as e:
        return err(e.code, str(e))
    except Exception:
        return err(EC.CALC, "计算失败，请检查数据内容与参数设置（详见服务端日志）")


def register(mcp) -> None:
    """注册到 MCPServer（mcp 2.x，工具名 = 函数名）。"""
    mcp.add_tool(cluster_analysis, description=__import__("sys").modules[__name__].__doc__)

