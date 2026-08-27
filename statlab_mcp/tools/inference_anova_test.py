"""anova_test —— 统计推断组 · 方差分析（工具 7，核心实现）。

docstring = agent 使用说明书，与 statlab_mcp/docs/design/04_inference_batch2.md 同步维护。

参数:
    file_path (str): 本地数据文件（csv/tsv/xlsx/json）
    group_col (str): 分组列（类别或数值均可，按唯一值分组；2~20 组）
    value_col (str): 数值列（检验对象）
    alpha (float, 0.05): 显著性水平 ∈ (0,1)

流程（确定性）:
    1. 前置：Levene 方差齐性（scipy.stats.levene，稳健中位数版）+ 各组 Shapiro
       （3<=n<=5000 时执行，违反警示不阻断）
    2. 方差齐 -> scipy.stats.f_oneway；方差不齐（Levene p<alpha）-> Welch ANOVA
       （statsmodels.stats.oneway.anova_oneway(use_var="unequal")，避免手写公式出错）
    3. 事后：齐 -> Tukey HSD（statsmodels pairwise_tukeyhsd，含 p 值与族校正）；
       不齐 -> Games-Howell（手写：libqsturng.qsturng 学生化极差临界值，
       se=sqrt(si2/ni+sj2/nj)，显著判定 = |diff| > q*se/sqrt(2)；
       p 值省略并以"CI 是否含 0"判定，输出注明——statsmodels 无现成实现，诚实披露）

示例:
    anova_test("samples/clean.csv", group_col="category", value_col="score")
inline 数据:
    本工具支持可选 inline_data 参数（v1.2.0 起）：与 file_path 二选一，
    支持 records 数组或 {"header": [...], "rows": [[...], ...]} 对象两种形态；
    规模上限/类型域/data_source 来源标注见 statlab_mcp/docs/SPEC.md 第 12 节。

"""
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sps

from statlab_mcp.tools._common import EC, DataLabError, err, ok, require_non_none, resolve_data

SHAPIRO_MIN_N, SHAPIRO_MAX_N = 3, 5000
MAX_GROUPS = 20


def _fmt_p(p: float) -> str:
    return "<0.001" if p < 0.001 else f"{p:.4f}"


def _welch_df(s1: float, s2: float, n1: int, n2: int) -> float:
    a, b = s1 ** 2 / n1, s2 ** 2 / n2
    denom = a ** 2 / (n1 - 1) + b ** 2 / (n2 - 1)
    return float((a + b) ** 2 / denom) if denom > 0 else float("nan")


def _shapiro_one(x: np.ndarray) -> dict[str, Any]:
    n = int(x.size)
    if not (SHAPIRO_MIN_N <= n <= SHAPIRO_MAX_N):
        return {"statistic": None, "p_value": None, "normal": None,
                "note": f"n={n} 超出 Shapiro 适用范围 3~{SHAPIRO_MAX_N}，自动跳过"}
    stat, p = sps.shapiro(x)
    return {"statistic": float(stat), "p_value": float(p),
            "normal": bool(p > 0.05), "note": None}


def _games_howell_pairs(groups: dict[str, np.ndarray], keys: list[str],
                        alpha: float) -> list[dict[str, Any]]:
    """Games-Howell 事后（手写）：q 临界值 + 每对 CI + 显著判定（p 值省略并注明）。"""
    k = len(keys)
    pairs = []
    for a in range(k):
        for b in range(a + 1, k):
            x, y = groups[keys[a]], groups[keys[b]]
            na, nb = int(x.size), int(y.size)
            ma, mb = float(x.mean()), float(y.mean())
            sa2, sb2 = float(x.var(ddof=1)), float(y.var(ddof=1))
            diff = ma - mb
            se = float(np.sqrt(sa2 / na + sb2 / nb))
            df = _welch_df(float(np.sqrt(sa2)), float(np.sqrt(sb2)), na, nb)
            from statsmodels.stats.libqsturng import qsturng  # 延迟导入（P1-1）
            q = float(qsturng(1 - alpha, k, max(df, 1e-9)))
            crit = q * se / np.sqrt(2.0)
            pairs.append({
                "pair": f"{keys[a]}-{keys[b]}",
                "diff": diff,
                "ci_lower": diff - crit,
                "ci_upper": diff + crit,
                "p_value": None,          # 学生化极差分布无 CDF 现成实现，诚实省略
                "significant": bool(abs(diff) > crit),
            })
    return pairs


def anova_test(file_path: str | None = None, group_col: str | None = None,
               value_col: str | None = None, alpha: float = 0.05,
                   inline_data: list | dict | None = None) -> dict:
    """多组均值比较（ANOVA / Welch ANOVA + Tukey / Games-Howell 事后）。"""
    # statsmodels 三个子模块延迟导入（P1-1）：主函数唯一入口、各分支共享此作用域
    from statsmodels.stats.multicomp import pairwise_tukeyhsd
    from statsmodels.stats.oneway import anova_oneway
    # D17 连锁 optional 化的运行期强校验（SPEC §12.6）
    require_non_none(group_col=group_col, value_col=value_col)
    try:
        if not (0 < alpha < 1):
            raise DataLabError("alpha 必须在 (0,1) 之间", EC.PARAM)
        df_all, data_source = resolve_data(file_path, inline_data)
        if value_col not in df_all.columns:
            raise DataLabError(f"缺少必需列: {value_col}；实际列: {list(df_all.columns)}", EC.COLUMN_MISSING)
        if group_col not in df_all.columns:
            raise DataLabError(f"缺少必需列: {group_col}；实际列: {list(df_all.columns)}", EC.COLUMN_MISSING)
        if not pd.api.types.is_numeric_dtype(df_all[value_col]):
            raise DataLabError(f"列 {value_col} 不是数值列，无法做方差分析", EC.COLUMN_TYPE)
        if df_all[group_col].notna().sum() == 0:
            raise DataLabError(f"列 {group_col} 无有效数据", EC.INSUFFICIENT)

        keys = list(dict.fromkeys(df_all[group_col].dropna().values))
        if len(keys) < 2:
            raise DataLabError("分组至少需要 2 组", EC.STRUCTURE)
        if len(keys) > MAX_GROUPS:
            raise DataLabError(f"组数超过 {MAX_GROUPS}，请合并类别", EC.STRUCTURE)

        groups: dict[str, np.ndarray] = {}
        group_meta: dict[str, dict[str, Any]] = {}
        sets = []
        for key in keys:
            idx = df_all[group_col] == key
            vals = df_all.loc[idx, value_col].dropna().to_numpy(dtype=float)
            if vals.size < 2:
                raise DataLabError(f"组 {key} 样本量不足 2", EC.INSUFFICIENT)
            groups[key] = vals
            sets.append(vals)
            group_meta[key] = {"n": int(vals.size), "mean": float(vals.mean()),
                               "std": float(vals.std(ddof=1))}
        n_total = int(sum(v.size for v in sets))
        k = len(keys)

        # 前置：Levene + 各组 Shapiro
        lev_stat, lev_p = sps.levene(*sets)
        equal_var = bool(lev_p >= alpha)
        shapiro_by_group = {key: _shapiro_one(groups[key]) for key in keys}
        warn = any(s.get("normal") is False for s in shapiro_by_group.values())

        # 主检验
        if equal_var:
            method = "anova"
            f_stat, p_value = sps.f_oneway(*sets)
            df_between, df_within = k - 1, n_total - k
            res_f, res_p = float(f_stat), float(p_value)
        else:
            method = "welch_anova"
            res = anova_oneway(sets, use_var="unequal")
            res_f, res_p = float(res.statistic), float(res.pvalue)
            # Welch 的 df_denom 通常为小数（Welch-Satterthwaite），保留精度不取整（外部评审 L3）
            df_between, df_within = int(res.df_num), float(res.df_denom)  # statsmodels 0.14.6 实测属性名

        # 事后检验
        all_vals = np.concatenate(sets)
        all_keys = np.concatenate([[key] * int(v.size) for key, v in groups.items()])
        if equal_var:
            tuk = pairwise_tukeyhsd(all_vals, all_keys, alpha=alpha)
            pairs = []
            for a in range(k):
                for b in range(a + 1, k):
                    # pairwise_tukeyhsd 按 groupsunique 内部排序，用名字解析对（外部评审 L2：删死代码）
                    names = tuk.groupsunique.tolist()
                    ia, ib = names.index(keys[a]), names.index(keys[b])
                    flat_idx = sum(len(names) - 1 - x for x in range(ia)) + (ib - ia - 1)
                    d = float(tuk.meandiffs[flat_idx])      # statsmodels: mean[ib]-mean[ia]
                    ci = tuk.confint[flat_idx]              # 同方向区间
                    pairs.append({
                        "pair": f"{keys[a]}-{keys[b]}",     # 统一为"前组-后组"方向
                        "diff": -d,
                        "ci_lower": -float(ci[1]),
                        "ci_upper": -float(ci[0]),
                        "p_value": float(tuk.pvalues[flat_idx]),
                        "significant": bool(tuk.reject[flat_idx]),   # 0.14.6 实测属性名 confint/pvalues
                    })
            posthoc: dict[str, Any] = {"method": "tukey_hsd", "pairs": pairs,
                                       "correction": "family-wise（按族校正，Tukey）"}
        else:
            gh = _games_howell_pairs(groups, keys, alpha)
            posthoc = {"method": "games_howell", "pairs": gh,
                       "correction": "family-wise（按族校正，Games-Howell）；p 值省略，"
                                     "以 95% 置信区间是否含 0 判定（学生化极差分布无现成 CDF）"}

        if res_p < alpha:
            conclusion = (f"p<α 拒绝 H0（F={res_f:.2f}, p={_fmt_p(res_p)} < α={alpha}）："
                          f"组间均值存在显著差异")
        else:
            conclusion = (f"p≥α 不能拒绝 H0（F={res_f:.2f}, p={_fmt_p(res_p)} ≥ α={alpha}）："
                          f"组间均值无显著差异")

        sig_pairs = [p for p in posthoc["pairs"] if p["significant"]]
        sig_txt = "；".join(p["pair"] for p in sig_pairs) if sig_pairs else "无"
        summary = (f"{method}：F={res_f:.2f}, p={_fmt_p(res_p)}，"
                   f"{'拒绝 H0' if res_p < alpha else '不能拒绝 H0'}；"
                   f"事后（{posthoc['method']}）显著对：{sig_txt}"
                   + ("；非正态警示" if warn else "")
                   + "；方差" + ("齐" if equal_var else "不齐，已用 Welch 校正"))

        result = {
            "n_groups": k, "n": n_total,
            "groups": group_meta,
            "method": method,
            "statistic": res_f, "p_value": res_p,
            "df_between": df_between, "df_within": df_within,
            "levene": {"statistic": float(lev_stat), "p_value": float(lev_p),
                       "equal_variance": equal_var},
            "shapiro_by_group": shapiro_by_group,
            "posthoc": posthoc,
            "conclusion": conclusion,
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
    mcp.add_tool(anova_test, description=__import__("sys").modules[__name__].__doc__)

