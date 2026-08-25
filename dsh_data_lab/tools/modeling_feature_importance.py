# -*- coding: utf-8 -*-
"""feature_importance —— 建模组 · 特征重要性（工具 16，核心实现）。

docstring = agent 使用说明书，与 docs/design/05_modeling.md 同步维护。

参数:
    file_path (str): 本地数据文件（csv/tsv/xlsx/json）
    target (str): 目标列（<=20 类 -> 分类随机森林 class_weight=balanced；连续 -> 回归森林）
    method (str, "permutation"): permutation（打乱验证集特征，验证集思想）/
        impurity（训练集内基尼/方差减少；两者都输出，默认 permutation）
    n_estimators (int, 200): 森林树数 >=10
    random_state (int, 42): 森林与划分固定种子
    n_repeats (int, 10): permutation 专用，打乱次数 >=1

硬性门槛: n < 50 拒绝（规格）；特征重要性排序 + "重要性≠因果"尾注。

第 4.1 条实现（确定性）:
    train_test_split(0.25, random_state) 划分；模型在训练集拟合；impurity 取
    feature_importances_；permutation 在测试集上打乱（sklearn.inspection.permutation_importance）。

示例:
    feature_importance("samples/clean.csv", target="income")
"""
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.model_selection import train_test_split

from statlab_mcp.tools._common import DataLabError, err, ok, read_table

MIN_N = 50
MAX_CLASSES = 50
MIN_ESTIMATORS = 10


def feature_importance(file_path: str, target: str, method: str = "permutation",
                       n_estimators: int = 200, random_state: int = 42,
                       n_repeats: int = 10) -> dict:
    """随机森林特征重要性（permutation / impurity 二选一）。"""
    try:
        if method not in ("permutation", "impurity"):
            raise DataLabError("method 仅支持 permutation/impurity")
        if isinstance(n_estimators, bool) or not isinstance(n_estimators, (int, np.integer)) \
                or n_estimators < MIN_ESTIMATORS:
            raise DataLabError(f"n_estimators 必须 >= {MIN_ESTIMATORS}")
        if isinstance(n_repeats, bool) or not isinstance(n_repeats, (int, np.integer)) \
                or n_repeats < 1:
            raise DataLabError("n_repeats 必须 >=1")
        df = read_table(file_path)
        if target not in df.columns:
            raise DataLabError(f"缺少必需列: {target}；实际列: {list(df.columns)}")
        y_all = df[target].dropna()
        n = int(y_all.size)
        if n < MIN_N:
            raise DataLabError(f"样本量 n={n} 小于 50，特征重要性不稳定，请积累数据或抽样")

        # ---- 特征矩阵：数值直用 + 类别 one-hot ----
        dummy_mapping: Dict[str, str] = {}
        parts = []
        for c in df.columns:
            if c == target:
                continue
            if pd.api.types.is_numeric_dtype(df[c]):
                parts.append(df[c])
            else:
                dummies = pd.get_dummies(df[c], prefix=c)
                for col in dummies.columns:
                    dummy_mapping[col] = f"{c}={col[len(c) + 1:]}"
                parts.append(dummies)
        if not parts:
            raise DataLabError("目标列之外没有可用特征")
        X_all = pd.concat(parts, axis=1)
        feature_names = list(X_all.columns)
        m = X_all.copy()
        m[target] = df[target]
        m = m.dropna()
        dropped = n - int(len(m))
        X = m[feature_names].to_numpy(dtype=float)
        y = m[target]

        if not pd.api.types.is_numeric_dtype(y):
            is_classification = True               # 类别标签（字符串）
        elif int(y.nunique()) <= 20:
            is_classification = True               # 数值但只取少量离散值（如 0/1 标签）
        else:
            is_classification = False              # 连续数值 -> 回归
        if is_classification and int(y.nunique()) > MAX_CLASSES:
            raise DataLabError(f"目标类别数 {int(y.nunique())} 超过 {MAX_CLASSES}，请先合并类别")

        # ---- 划分（0.25 测试集）----
        X_tr, X_te, y_tr, y_te = train_test_split(
            X, y, test_size=0.25, random_state=random_state,
            stratify=y if is_classification else None)

        if is_classification:
            model = RandomForestClassifier(n_estimators=n_estimators,
                                           random_state=random_state,
                                           class_weight="balanced")   # 串行：严格确定性（1 ulp 级浮点可复现）
            model_type = "classification"
        else:
            model = RandomForestRegressor(n_estimators=n_estimators,
                                          random_state=random_state)   # 串行：严格确定性
            model_type = "regression"
        model.fit(X_tr, y_tr)

        if method == "impurity":
            raw = model.feature_importances_
        else:
            imp = permutation_importance(model, X_te, y_te, n_repeats=n_repeats,
                                         random_state=random_state)    # 串行：严格确定性
            raw = imp.importances_mean
        ranks = np.argsort(-raw)
        importances = [{"feature": feature_names[i], "importance": float(raw[i]),
                        "rank": int(pos) + 1} for pos, i in enumerate(ranks)]

        top = importances[0]
        conclusion = (f"按 {method} 法（随机森林{model_type}），最重要的特征是 "
                      f"{top['feature']}（importance={top['importance']:.3f}）；"
                      f"重要性≠因果")
        note = ("；分类模型" if is_classification else "；回归模型")
        summary = (f"{method} 重要性（n={int(len(m))}" 
                   + (f"，已剔除缺失 {dropped} 行" if dropped else "")
                   + f"）：" + " > ".join(f"{v['feature']} {v['importance']:.3f}"
                                         for v in importances[:5])
                   + f"{note}；重要性≠因果")

        result = {
            "method": method, "model_type": model_type,
            "n": int(len(m)), "dropped_rows": dropped,
            "importances": importances,
            "n_estimators": int(n_estimators), "n_repeats": int(n_repeats),
            "dummy_mapping": dummy_mapping or None,
            "conclusion": conclusion,
        }
        return ok(result, summary)
    except DataLabError as e:
        return err(str(e))
    except Exception as e:
        return err("计算失败，请检查数据内容与参数设置（详见服务端日志）")


def register(mcp) -> None:
    """注册到 MCPServer（mcp 2.x，工具名 = 函数名）。"""
    mcp.add_tool(feature_importance, description=feature_importance.__doc__)
