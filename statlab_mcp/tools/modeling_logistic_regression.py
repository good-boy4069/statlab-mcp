"""logistic_regression —— 建模组 · 逻辑回归（工具 13，核心实现）。

docstring = agent 使用说明书，与 statlab_mcp/docs/design/05_modeling.md 同步维护。

参数:
    file_path (str): 本地数据文件（csv/tsv/xlsx/json）
    target (str): 二分类目标列（恰好 2 类；类名映射为 0/1 输出 label_mapping）
    features (list[str]): 数值特征（本工具不做 one-hot，规格未要求；非数值报错）
    test_size (float, 0.3): train/test 分层划分比例 ∈(0,1)
    random_state (int, 42): 划分与复制的固定随机种子
    class_weight (str, "balanced"): balanced 用少数类确定性复制实现（statsmodels
        Logit 无内置类权重，如实披露；复制样本 w=n/(2*n_class) 于训练集内，seed 固定）

固定五项输出（规格硬性）:
    类别分布 / accuracy（仅对照，受类别不平衡影响）/ 混淆矩阵 / ROC-AUC+95%CI
    （Hanley-McNeil 正态近似）/ 特征 OR 与 p 值（statsmodels Logit 矩阵接口，
    OR=exp(beta)）。ConvergenceWarning（完美可分）-> convergence_warning 注明系数不稳定。

示例:
    logistic_regression("tests/fixtures/binary_noisy.csv", target="label", features=["score"])
"""
import warnings

import numpy as np
import pandas as pd

from statlab_mcp.tools._common import EC, DataLabError, err, ok, read_table

ALPHA = 0.05


def _fmt_p(p: float) -> str:
    return "<0.001" if p < 0.001 else f"{p:.4f}"


def _auc_ci_hanley(auc: float, n_pos: int, n_neg: int) -> tuple:
    """Hanley-McNeil 正态近似 95% CI。"""
    q1 = auc / (2 - auc)
    q2 = 2 * auc ** 2 / (1 + auc)
    se = float(np.sqrt((auc * (1 - auc) + (n_pos - 1) * (q1 - auc ** 2)
                        + (n_neg - 1) * (q2 - auc ** 2)) / (n_pos * n_neg)))
    lo, hi = auc - 1.959964 * se, auc + 1.959964 * se
    return float(max(lo, 0.0)), float(min(hi, 1.0))


def logistic_regression(file_path: str, target: str, features: list[str],
                        test_size: float = 0.3, random_state: int = 42,
                        class_weight: str = "balanced") -> dict:
    """二分类逻辑回归：类别分布/acc/混淆矩阵/AUC-CI/OR 与 p。"""
    try:
        if not (0 < test_size < 1):
            raise DataLabError("test_size 必须在 (0,1) 之间", EC.PARAM)
        if class_weight not in ("balanced", "none"):
            raise DataLabError("class_weight 仅支持 balanced/none", EC.PARAM)
        if not isinstance(features, list) or not features:
            raise DataLabError("features 至少需要 1 个特征", EC.PARAM)
        if len(set(features)) != len(features):
            raise DataLabError("features 含重复项，请去重", EC.PARAM)
        df = read_table(file_path)
        if target not in df.columns:
            raise DataLabError(f"缺少必需列: {target}；实际列: {list(df.columns)}", EC.COLUMN_MISSING)
        for f in features:
            if f not in df.columns:
                raise DataLabError(f"缺少必需列: {f}；实际列: {list(df.columns)}", EC.COLUMN_MISSING)
            if not pd.api.types.is_numeric_dtype(df[f]):
                raise DataLabError(f"特征 {f} 不是数值列（本工具不做 one-hot）", EC.COLUMN_TYPE)

        m = df[[target, *features]].dropna()
        len(m)
        labels = m[target].dropna()
        uniq = sorted(labels.unique().tolist())
        if len(uniq) < 2:
            raise DataLabError("目标列只有 1 个类别，无法做二分类", EC.STRUCTURE)
        if len(uniq) > 2:
            raise DataLabError(f"当前 {len(uniq)} 类，本工具仅支持二分类", EC.STRUCTURE)
        label_mapping = {str(uniq[0]): 0, str(uniq[1]): 1}
        y = m[target].map({uniq[0]: 0, uniq[1]: 1}).to_numpy(dtype=float)
        X = m[features].to_numpy(dtype=float)

        # ---- 分层划分 ----
        try:
            from sklearn.metrics import roc_auc_score  # 延迟导入（P1-1）
            from sklearn.model_selection import train_test_split
            from statsmodels.api import Logit, add_constant
            X_tr, X_te, y_tr, y_te = train_test_split(
                X, y, test_size=test_size, random_state=random_state, stratify=y)
        except ValueError:
            raise DataLabError("类别样本过少，无法分层划分，请增大样本或合并类别", EC.INSUFFICIENT) from None
        n_tr0 = int(np.sum(y_tr == 0))
        n_tr1 = int(np.sum(y_tr == 1))
        if n_tr0 < 2 or n_tr1 < 2:
            raise DataLabError("训练集某类别样本 <2，无法拟合", EC.INSUFFICIENT)

        # ---- class_weight：少数类确定性复制（如实披露）----
        copied = 0
        if class_weight == "balanced" and n_tr0 != n_tr1:
            minor = ((X_tr[y_tr == 1], y_tr[y_tr == 1]) if n_tr0 > n_tr1
                     else (X_tr[y_tr == 0], y_tr[y_tr == 0]))
            n_train_tot = n_tr0 + n_tr1
            w = n_train_tot / (2 * minor[1].size)    # sklearn balanced 口径：n/(2*类计数)
            copies = max(0, round(w) - 1)
            if copies > 0:
                rng = np.random.default_rng(random_state)      # 局部固定：复制顺序恒定
                idx = rng.integers(0, minor[1].size, size=copies * minor[1].size)
                X_tr = np.vstack([X_tr, minor[0][idx % minor[0].shape[0]]])
                y_tr = np.concatenate([y_tr, minor[1][idx % minor[1].size]])
                copied = int(copies * minor[1].size)

        # ---- statsmodels Logit（捕获分离警告）----
        Xtr_df = pd.DataFrame(X_tr, columns=features)   # 保留列名（add_constant 对 ndarray 不保留）
        Xt = add_constant(Xtr_df, has_constant="add")
        with warnings.catch_warnings(record=True) as wlist:
            warnings.simplefilter("always")
            model = Logit(y_tr, Xt)
            try:
                res = model.fit(disp=False)
            except Exception:
                raise DataLabError("Logit 拟合失败（可能存在完全共线特征）", EC.CALC) from None
        conv_msg = None
        for w in wlist:
            text = str(w.message)
            if ("Maximum" in text or "Singular" in text or "converge" in text.lower()
                    or "perfect" in text.lower()):
                conv_msg = "存在完美可分特征，系数不稳定（分离现象）；OR 值可能极端"
                break
        if conv_msg is None and getattr(res, "mle_retvals", None) is not None \
                and res.mle_retvals.get("converged") is False:
            conv_msg = "存在完美可分特征，系数不稳定（分离现象）；OR 值可能极端"

        params = res.params
        pvalues = res.pvalues
        names = [c for c in Xt.columns]
        ors = []
        for name in names:
            if name == "const":
                ors.append({"name": "const", "or": float(np.exp(params[name])),
                            "p_value": float(pvalues[name]), "significant": False})
            else:
                o = float(np.exp(params[name]))
                p = float(pvalues[name])
                ors.append({"name": name, "or": o, "p_value": p,
                            "significant": bool(p < ALPHA)})

        # ---- 评估（test 集）----
        Xte_df = pd.DataFrame(X_te, columns=features)
        prob = res.predict(add_constant(Xte_df, has_constant="add"))
        pred = (prob > 0.5).astype(int)
        tp = int(np.sum((pred == 1) & (y_te == 1)))
        fp = int(np.sum((pred == 1) & (y_te == 0)))
        fn = int(np.sum((pred == 0) & (y_te == 1)))
        tn = int(np.sum((pred == 0) & (y_te == 0)))
        acc = float(np.mean(pred == y_te))
        n_pos_test = int(np.sum(y_te == 1))
        n_neg_test = int(np.sum(y_te == 0))
        auc = float(roc_auc_score(y_te, prob)) if n_pos_test >= 1 and n_neg_test >= 1 else None
        if auc is None:
            auc_ci = (None, None)
        elif auc == 1.0:
            auc_ci = (1.0, 1.0)          # 完美预测时 CI 退化为点（se=0 风险规避）
        else:
            auc_ci = _auc_ci_hanley(auc, n_pos_test, n_neg_test)

        dist = {"train": {"0": {"n": n_tr0, "pct": n_tr0 / (n_tr0 + n_tr1)},
                          "1": {"n": n_tr1, "pct": n_tr1 / (n_tr0 + n_tr1)}},
                "test": {"0": {"n": n_neg_test, "pct": n_neg_test / len(y_te) if len(y_te) else 0},
                         "1": {"n": n_pos_test, "pct": n_pos_test / len(y_te) if len(y_te) else 0}}}

        sig_ors = [o for o in ors if o["significant"] and o["name"] != "const"]
        sig_txt = "；".join(f"{o['name']}(OR={o['or']:.2f})" for o in sig_ors) or "无"
        warn_txt = "；" + conv_msg if conv_msg else ""
        note_txt = (f"；balanced 复制少数类 {copied} 行（训练 n={len(y_tr)}）"
                    if copied else "")
        summary = (f"逻辑回归：AUC={auc:.2f}（95% CI [{auc_ci[0]:.2f}, {auc_ci[1]:.2f}]"
                   if auc is not None else "逻辑回归：AUC 不可计算（test 集缺一个类别）") + \
            f"；显著 OR：{sig_txt}；acc={acc:.2f}（仅对照）{note_txt}{warn_txt}；相关≠因果"

        result = {
            "class_distribution": dist,
            "accuracy": acc,
            "accuracy_note": "仅对照；准确率受类别不平衡影响，不以它论英雄",
            "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
                                 "label_positive": str(uniq[1])},
            "roc_auc": auc,
            "auc_ci_lower": auc_ci[0], "auc_ci_upper": auc_ci[1],
            "auc_ci_method": "Hanley-McNeil 正态近似",
            "odds_ratios": ors,
            "n_train_after_weight": len(y_tr), "copied_rows": copied,
            "n_test": len(y_te),
            "label_mapping": label_mapping,
            "convergence_warning": conv_msg,
            "class_weight_note": f"balanced 以少数类复制实现（复制 {copied} 行）" if copied
                                 else "class_weight=none（未加权）",
        }
        return ok(result, summary)
    except DataLabError as e:
        return err(e.code, str(e))
    except Exception:
        return err(EC.CALC, "计算失败，请检查数据内容与参数设置（详见服务端日志）")


def register(mcp) -> None:
    """注册到 MCPServer（mcp 2.x，工具名 = 函数名）。"""
    mcp.add_tool(logistic_regression, description=__import__("sys").modules[__name__].__doc__)

