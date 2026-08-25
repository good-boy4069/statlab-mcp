# 建模组 · 接口设计文档（整组交付）

> 交付物：linear_regression / logistic_regression / cluster_analysis / pca_analysis / feature_importance。
> 全局约定沿用前两组：error 无 result；数值原生类型；NaN→null；summary 代码模板；确定性可复现
> （本组所有随机过程固定 random_state=42 / default_rng(42)）。
> 建模组的共同原则：结果必须来自真实库计算；"模型是工具不是真理"始终写进结论。

---

# 工具 12：linear_regression(file_path, target, features, add_constant=True, alpha=0.05)【核心】

一句话用途：用多个自变量预测一个连续因变量，输出每个变量的系数与显著性、模型整体 R²、共线性诊断与残差诊断图。

## 参数表
| 参数名 | 类型 | 默认值 | 校验规则 | 例子 |
|---|---|---|---|---|
| file_path | str | 必填 | 同全局 | `file_path="clean.csv"` |
| target | str | 必填 | 存在且数值列；连续因变量 | `target="income"` |
| features | list[str] | 必填 | 至少 1 个；须都存在；重复项去重报错 | `features=["age","score"]` |
| add_constant | bool | True | 是否加截距；False 时 GOF 指标失效要注明 | `add_constant=False` |
| alpha | float | 0.05 | ∈ (0,1)，显著性阈值（报告用） | `alpha=0.01` |

## 统计口径（钉死）
1. **矩阵接口**：`statsmodels.api.OLS(y, X)` —— **禁止 formula 字符串**（规格硬性规定）
2. **类别列自动 one-hot**（`pd.get_dummies(drop_first=False)`：每个类别一列 0/1，并输出列名→原类别映射表 `dummy_mapping`）；数值列原样
3. **零方差列自动剔除并报告**（`drop_zero_var` 清单）
4. **缺失处理**：listwise `dropna()`（任一特征或目标缺失的行整行剔除），输出 **"已剔除 N 行"**；剔除后 n=0 → error
5. **样本量门槛**：n ≤ 特征数+2 → error："样本量不足（n=N ≤ 特征数+2），无法稳定估计"
6. 输出：β/std err/t/p(双尾)/R²/adjusted R²/F 统计量+p、VIF（每个数值特征；>10 标注"强共线性"）、残差 Shapiro（正态性）、**Durbin-Watson**（相邻残差自相关，≈2 正常）、n、dummy_mapping、drop_zero_var
7. **残差图**（附录 D）：残差 vs 拟合值散点 + 残差直方图（2 子图），`__image__` 顶层
8. 结论模板：`模型 R²=x（调整后 y），F 检验 p=z 说明模型整体{显著/不显著}；系数显著的自变量：…`；summary 注明"相关≠因果、模型未做外部验证"

## 返回（成功）
```jsonc
{
  "status": "ok",
  "result": {
    "method": "ols", "n": 48, "dropped_rows": 2, "n_features": 3,
    "r_squared": 0.62, "adj_r_squared": 0.59,
    "f_statistic": 22.4, "f_p_value": 0.0001,
    "durbin_watson": 1.98, "residual_shapiro": {"statistic": 0.97, "p_value": 0.55, "normal": true},
    "coefficients": [{"name": "const", "beta": 500.2, "std_err": 120.1, "t": 4.16, "p_value": 0.000, "vif": null}, ...],
    "vif_flags": ["age(11.2)>10 强共线性"],
    "dummy_mapping": {"categoryA": "category=A", ...}, "drop_zero_var": [],
    "conclusion": "R²=0.62（调整后 0.59），F 检验 p<0.001 模型整体显著；income 显著相关变量：age"
  },
  "__image__": "C:\\...\\residuals_linear_regression_all_20260826_123456.png",
  "summary": "线性回归：R²=0.62，F=22.4(p<0.001) 模型显著；显著系数 1 个（age）；VIF 全 <10；已剔除缺失 2 行；相关≠因果"
}
```
| 键 | 说明 |
|---|---|
| coefficients | 每特征一行：beta（未标准化原始单位）、std_err、t、p_value（双尾）；const 的 vif=null |
| vif_flags | VIF>10 的特征与数值标注 |
| dummy_mapping / drop_zero_var | one-hot 映射 / 被剔除的零方差列 |
| dropped_rows | listwise 剔除行数（summary 固定注明"已剔除 N 行"） |

## 边界行为表
| 场景 | 行为 |
|---|---|
| target 非数值 / 缺列 | error（同前文案） |
| features 为空列表 | error："features 至少需要 1 个特征" |
| features 有重复 | error："features 含重复项，请去重" |
| 零方差特征 | 自动剔除并列入 drop_zero_var（不报错） |
| n ≤ 特征数+2 | error（见口径 5） |
| 全类别特征 | one-hot 后照常建模（dummy 数多时与零方差规则协同） |
| 常数目标 | R²=0 输出 + summary 注明"目标为常数列" |
| 中文列名 | 键原样输出；图片文件名走 _safe_name |
| 极端值 | 如实参与（残差图会暴露它，这正是诊断图的意义） |

## 错误路径（≥3 种）
1. `样本量不足（n=.. ≤ 特征数+2），无法稳定估计`
2. `features 至少需要 1 个特征`
3. `缺少必需列: target`
4. `features 含重复项，请去重`

## 验证命令与预期值来源
```powershell
& .\.venv\Scripts\python.exe -c "from statlab_mcp.tools.modeling_linear_regression import linear_regression; import json; print(json.dumps(linear_regression('samples/clean.csv', target='income', features=['age']), ensure_ascii=False, indent=1))"
```
- Excel 可复算：单特征 OLS 与 Excel 回归结果一致（SLOPE/INTERCEPT/RSQ/LINEST 可核对）；multi 特征用 LINEST 数组公式
- 已知数学事实：对 clean.csv 的 income ~ age，相关系数 r≈0.30（correlation_matrix 已实测）→ R²≈r²≈0.09（可交叉验证！）

---

# 工具 13：logistic_regression(file_path, target, features, test_size=0.3, random_state=42, class_weight="balanced")【核心】

一句话用途：预测二分类结果（是/否），输出类别分布、准确率（仅对照）、混淆矩阵、ROC-AUC（含 95% CI）、每个特征的 OR 与 p 值。

## 参数表
| 参数名 | 类型 | 默认值 | 校验规则 | 例子 |
|---|---|---|---|---|
| file_path | str | 必填 | 同全局 | 例子 |
| target | str | 必填 | 存在；**恰好 2 个类别**；多分类 → error："当前 N 类，本工具仅支持二分类" | `target="category"`（构造二分类时） |
| features | list[str] | 必填 | 至少 1 个；数值列；缺列/重复报错 | `features=["age","score"]` |
| test_size | float | 0.3 | ∈ (0,1)（train/test 划分） | `test_size=0.2` |
| random_state | int | 42 | 固定划分与重采样 | `random_state=7` |
| class_weight | str | "balanced" | ∈ {balanced, none}（实现见口径 4） | `class_weight="none"` |

## 统计口径（钉死）
1. `sklearn.model_selection.train_test_split(stratify=y, random_state=...)`（分层划分）
2. 拟合：**statsmodels Logit（矩阵接口，禁 formula）**；`sm.Logit(y, sm.add_constant(X)).fit(disp=False)` —— p 值取 `params` 的 pvalues、OR = `np.exp(params)`（指数化系数）；`add_constant` 恒为 True（二分类惯例，不加参数）
3. **固定五项输出**（规格硬性）：①类别分布（每类 n 与占比，train+test）②accuracy（**仅对照**，summary 注"准确率受类别不平衡影响，不以它论英雄"）③混淆矩阵（TP/FP/FN/TN + 行列说明）④**ROC-AUC + 95% CI**（`sklearn.metrics.roc_auc_score` + Hanley-McNeil 正态近似 se=sqrt((auc(1-auc)+(n1-1)(Q1-auc²)+(n2-1)(Q2-auc²))/(n1*n2))，Q1=auc/(2-auc)、Q2=2auc²/(1+auc)）⑤特征 OR 与 p 值表
4. **class_weight="balanced" 的实现（如实披露）**：statsmodels Logit 无内置类权重 → 用**加权复制**：少数类按 w = n_total/(2*n_class) 复制次数 = round(w)-1 复制样本（确定性，random_state 固定生成顺序），Logit 在复制后样本上拟合；summary 注明"balanced 以少数类复制实现（n 增 N）"。class_weight="none" 时原样拟合
5. **ConvergenceWarning 捕获**：statsmodels 报"Maximum Likelihood optimization failed to converge"（或完美可分）→ result 附 `warning: "存在完美可分特征，系数不稳定（分离现象）；OR 值可能极端"`（不中断，规格要求注明）
6. 结论模板：`ROC-AUC=x（95% CI [a,b]）；显著 OR：{特征: OR}；准确率 y（仅对照）`

## 返回（成功）
```jsonc
{
  "status": "ok",
  "result": {
    "class_distribution": {"train": {"0": {"n": 30, "pct": 0.55}, "1": {"n": 25, "pct": 0.45}}, "test": {...}},
    "accuracy": 0.78, "accuracy_note": "仅对照；受类别不平衡影响",
    "confusion_matrix": {"tp": 8, "fp": 2, "fn": 4, "tn": 13, "label_positive": "1"},
    "roc_auc": 0.86, "auc_ci_lower": 0.74, "auc_ci_upper": 0.98, "auc_ci_method": "Hanley-McNeil 正态近似",
    "odds_ratios": [{"name": "age", "or": 1.12, "p_value": 0.003, "significant": true}, ...],
    "n_train": 55, "n_test": 25, "convergence_warning": null,
    "class_weight_note": "balanced：少数类复制实现，复制后 n=70"
  },
  "summary": "逻辑回归：AUC=0.86（95% CI [0.74, 0.98]）；显著 OR：age(1.12)；acc=0.78（仅对照）；无分离警告；相关≠因果"
}
```

## 边界行为表
| 场景 | 行为 |
|---|---|
| target >2 类 | error："当前 N 类，本工具仅支持二分类" |
| target 只有 1 类 | error："目标列只有 1 个类别" |
| 任一类别样本过少 | 分层划分仍可能失败 → error："类别 1 样本过少（n=k），无法分层划分" |
| 特征非数值 | error："特征 xxx 不是数值列"（本工具不做 one-hot——规格未要求，注明与 linear 的差异） |
| 缺失 | listwise dropna 并注"已剔除 N 行" |
| 完美可分 | convergence_warning 非 null（见口径 5），OR 给真实值但标注不稳定 |
| 类别名非 0/1 | 映射为 0/1（较大的类别为 1？按排序首位为 0、次位为 1），输出 label_mapping |
| test_size 越界 / random_state 负数 | error |

## 错误路径（≥3 种）
1. `当前 N 类，本工具仅支持二分类`
2. `类别 1 样本过少（n=k），无法分层划分`
3. `test_size 必须在 (0,1) 之间`

## 验证命令与预期值来源
```powershell
& .\.venv\Scripts\python.exe -c "from statlab_mcp.tools.modeling_logistic_regression import logistic_regression; import json; print(json.dumps(logistic_regression('samples/clean.csv', target='category', features=['age','score']), ensure_ascii=False, indent=1))"
```
- clean.csv 的 category 有 3 类 → 需先用 describe/type_check 看清，测试用二分类 fixture（tests/fixtures 补 binary.csv：A/B 由 score 高低构造 → 完美可分场景天然呈现分离警告；另造噪声版本）
- AUC 可在 Excel/SPSS 手工复核（ROC 曲线下面积）；OR 手算：系数 exp(β)

---

# 工具 14：cluster_analysis(file_path, k)【核心】

一句话用途：把样本分成 k 组"相似的人"，输出每簇的质心（还原到原始单位）与样本量、轮廓系数评估分簇质量。

## 参数表
| 参数名 | 类型 | 默认值 | 校验规则 | 例子 |
|---|---|---|---|---|
| file_path | str | 必填 | 同全局 | 例子 |
| k | int | 必填 | 2 ≤ k ≤ 样本数−1（整数；否则中文报错） | `k=3` |

## 统计口径（钉死）
1. **仅数值列**：自动排除非数值列并列出 `excluded_columns`；无数值列 → error
2. 标准化：`sklearn.preprocessing.StandardScaler`（z-score）后再聚类；**质心反标准化回原单位**（scaler.inverse_transform）供解读
3. `sklearn.cluster.KMeans(n_clusters=k, random_state=42, n_init="auto")`（规格参数）
4. **质心解读必须附簇内样本量**（`np.bincount(labels)`）——禁止孤立解读质心（规格硬性）
5. 质量评估：`sklearn.metrics.silhouette_score`（标准化空间；范围 −1~1，>0.25 可接受，>0.5 结构良好）＋ **对比 k−1 / k+1 的轮廓系数**（同 seed 重跑，输出对照表）
6. 结论模板：`k=3 聚类完成，轮廓系数 s=x（k−1=k1 时为 y、k+1=k2 时为 z）；各簇样本量：…`

## 返回（成功）
```jsonc
{
  "status": "ok",
  "result": {
    "k": 3, "n_samples": 50, "excluded_columns": ["category", "date"],
    "silhouette": 0.42, "silhouette_compare": {"k_minus_1": {"k": 2, "silhouette": 0.38}, "k_plus_1": {"k": 4, "silhouette": 0.35}},
    "clusters": [
      {"cluster": 0, "n_members": 20, "centroid_original_units": {"age": 45.2, "score": 71.3, "income": 9200.0}, "note": "高收入高评分"}
    ]
  },
  "summary": "k=3 聚类：轮廓系数 0.42（可接受；k=2 为 0.38、k=4 为 0.35，k=3 最优或有更好 k 需业务判断）；簇 0 样本 20 人：均值 age=45 分 score=71 收入 9200"
}
```
| 键 | 说明 |
|---|---|
| silhouette_compare | k±1 的对照（k=2 时无 k−1，该键 null 并注明"k 已是最小值"） |
| clusters[].centroid_original_units | 反标准化质心（原单位）；note 由模板按质心相对高低生成（不含因果语言） |
| 标准化细节 | z-score 均值 0 方差 1；result 注明 `standardized: true` |

## 边界行为表
| 场景 | 行为 |
|---|---|
| k<2 或 k>样本数−1 | error："k 必须在 2 到 N−1 之间（样本数 N=..）" |
| k 非整数/非数字 | error："k 必须是整数" |
| 无数值列 | error："未找到数值列，无法聚类" |
| 单行文件 | k 范围校验自然拒绝（k≤0） |
| 常数列 | z-score 后为 0（StandardScaler 对零方差给 0），聚类照常（KMeans 不炸），输出时注明"常数列已标准化为 0" |
| 中文列名 | 键原样输出 |

## 错误路径（≥3 种）
1. `k 必须在 2 到 N−1 之间（样本数 N=..）`
2. `k 必须是整数`
3. `未找到数值列，无法聚类` / `缺少必需列: ..`（不存在）

## 验证命令与预期值来源
```powershell
& .\.venv\Scripts\python.exe -c "from statlab_mcp.tools.modeling_cluster_analysis import cluster_analysis; import json; print(json.dumps(cluster_analysis('samples/clean.csv', k=3), ensure_ascii=False, indent=1))"
```
- 手算校验例：两特征完全分离的两团数据（如 age 20~30 与 60~80 各 15 人）→ k=2 轮廓系数应明显高于 k=3（结构真有两团）
- 质心反标准化 = 簇内均值（KMeans 质心在欧氏空间即均值）；Excel 可人工核对每簇均值

---

# 工具 15：pca_analysis(file_path, n_components)【核心】

一句话用途：降维看"数据的主要波动方向"，输出每个主成分的方差解释率与载荷（还原到原始变量含义）。

## 参数表
| 参数名 | 类型 | 默认值 | 校验规则 | 例子 |
|---|---|---|---|---|
| file_path | str | 必填 | 同全局 | 例子 |
| n_components | int | 必填 | 1 ≤ n_components ≤ min(样本数, 特征数)；超界中文报错 | `n_components=2` |

## 统计口径（钉死）
1. 仅数值列（自动排除列出）；无数值列 → error
2. 标准化（StandardScaler）后 `sklearn.decomposition.PCA(n_components, random_state=42)`（PCA 无随机性，random_state 仅为接口一致）
3. 输出：`explained_variance_ratio`（每个成分解释方差比例 + 累积 `cumulative_ratio`）、`components_` **载荷矩阵（反标准化解读）**：载荷 = 成分向量 × 对应特征标准差（回到原始单位权重的近似，规格"载荷反标准化解读"），输出 `loadings: [{component: 1, feature: "age", loading: 0.71}]`
4. **载荷图**（附录 D）：2 子图（方差解释条形图 + 前两主成分载荷向量图），`__image__` 顶层
5. 结论模板：`前 N 个主成分累计解释 x% 方差；PC1 主要载荷：age(0.71)、score(−0.62)…`（注明"主成分是线性组合，不等于业务因子"）

## 返回（成功）
```jsonc
{
  "status": "ok",
  "result": {
    "n_components": 2, "n_features": 4, "n_samples": 50,
    "excluded_columns": ["category", "date"],
    "explained_variance_ratio": [0.52, 0.28], "cumulative_ratio": [0.52, 0.80],
    "loadings": [{"component": 1, "feature": "age", "loading": 0.71}, ...],
    "conclusion": "前 2 个主成分累计解释 80% 方差；PC1 载荷集中在 age/income"
  },
  "__image__": "C:\\...\\pca_analysis_all_20260826_123456.png",
  "summary": "PCA：PC1 解释 52%、PC2 解释 28%（累计 80%）；PC1 主要载荷 age(0.71)、income(0.68)"
}
```

## 边界行为表
| 场景 | 行为 |
|---|---|
| n_components 超界 | error："n_components 必须在 1 到 min(样本,特征)=x 之间" |
| 特征数=1 | 只出 PC1（解释 100%），注明"单特征 PCA 无降维意义" |
| 无数值列 | error（同 cluster） |
| 常数列 | 标准化为 0，载荷 0（注明） |
| 中文列名 | 键原样输出 |

## 错误路径（≥3 种）
1. `n_components 必须在 1 到 min(样本,特征)=x 之间`
2. `未找到数值列，无法做主成分分析`
3. `n_components 必须是整数`

## 验证命令与预期值来源
```powershell
& .\.venv\Scripts\python.exe -c "from statlab_mcp.tools.modeling_pca_analysis import pca_analysis; import json; print(json.dumps(pca_analysis('samples/clean.csv', n_components=2), ensure_ascii=False, indent=1))"
```
- 数学事实校验：方差解释率总和 = 1（前 min 个成分）；特征值分解结果可用 numpy.linalg.eigh 交叉核验（测试内独立实现）

---

# 工具 16：feature_importance(file_path, target, method="permutation", n_estimators=200, random_state=42, n_repeats=10)【核心】

一句话用途：回答"哪个变量对预测目标贡献最大"，输出重要性排序（两种方法可选），明确标注"重要性≠因果"。

## 参数表
| 参数名 | 类型 | 默认值 | 校验规则 | 例子 |
|---|---|---|---|---|
| file_path | str | 必填 | 同全局 | 例子 |
| target | str | 必填 | 存在；类别（≤20 类）→ 分类树；连续 → 回归树 | `target="income"` |
| method | str | "permutation" | ∈ {permutation, impurity}；非法报错 | `method="impurity"` |
| n_estimators | int | 200 | ≥10（整数）；过小报错 | `n_estimators=100` |
| random_state | int | 42 | 固定森林随机性 | `random_state=7` |
| n_repeats | int | 10 | ≥1；permutation 专用（打乱次数） | `n_repeats=20` |

## 统计口径（钉死）
1. **n < 50 拒绝**（规格硬性）：error："样本量 n=N 小于 50，特征重要性不稳定，请积累数据或抽样"
2. 数值特征直用（缺失 listwise dropna 注明）；类别特征 one-hot（同 linear_regression 的 get_dummies，输出映射）
3. 模型：目标 ≤20 类 → `RandomForestClassifier`（n_estimators/random_state，`class_weight="balanced"` 分类时）；连续 → `RandomForestRegressor`
4. impurity（默认 spec 允许）：`feature_importances_`（基尼/方差减少，**训练集内**，森林集成后稳定）；permutation：`sklearn.inspection.permutation_importance(..., n_repeats=, random_state=42)`（打乱单特征看分数下降，**验证集思想**，更稳健）
5. 输出：`importances: [{feature, importance, rank}]`（降序）+ `method` + `model_type`（分类/回归）+ `n_estimators`；summary 固定尾注"**重要性≠因果**"
6. 结论模板：`按 {method} 法，最重要的特征是 {top1}（importance=x），其次 …；重要性≠因果`

## 返回（成功）
```jsonc
{
  "status": "ok",
  "result": {
    "method": "permutation", "model_type": "regression",
    "n": 50, "dropped_rows": 0,
    "importances": [{"feature": "age", "importance": 0.34, "rank": 1}, ...],
    "n_estimators": 200, "n_repeats": 10,
    "dummy_mapping": {...} | null,
    "conclusion": "最重要的特征：age（0.34）；重要性≠因果"
  },
  "summary": "permutation 重要性（随机森林回归，n=50）：age 0.34 > score 0.21 > …；重要性≠因果"
}
```

## 边界行为表
| 场景 | 行为 |
|---|---|
| n<50 | error（规格硬性） |
| target >20 类 | 分类模型仍可跑（多分类 RF 支持）——但注明"类别多，重要性仅供参考"；>50 类 error |
| 特征全是零方差 | 重要性全部 ≈0，输出 + 注明"特征无信息量" |
| 全类别特征 | one-hot 后照常（映射输出） |
| permutation 时某特征打乱无变化 | importance=0（排序最低），正常 |
| method 非法 / n_estimators<10 / n_repeats<1 | error 中文 |

## 错误路径（≥3 种）
1. `样本量 n=N 小于 50，特征重要性不稳定`
2. `method 仅支持 permutation/impurity`
3. `n_estimators 必须 ≥10`

## 验证命令与预期值来源
```powershell
& .\.venv\Scripts\python.exe -c "from statlab_mcp.tools.modeling_feature_importance import feature_importance; import json; print(json.dumps(feature_importance('samples/clean.csv', target='income', method='permutation'), ensure_ascii=False, indent=1))"
```
- 概念校验例：构造"只有 age 影响 target"的合成数据 → age 重要性应显著最高（构造数据本身可人工核验语义）
- 随机森林不可逐数手算（集成学习），以构造数据的语义结论为准

---

# 附录：建模组自查（附录 C 组内 3 问）
- ⑦ 参数风格一致：target/features 命名统一；random_state=42 全组默认；校验消息同款中文
- ⑧ 无重叠：linear（连续目标）vs logistic（二分类目标）vs cluster（无目标分群）vs PCA（降维）vs importance（变量贡献）——功能正交；与推断组（假设检验）不重叠
- ⑨ 使用条件写明：OLS 线性性/残差诊断（Shapiro+DW）；Logit 二分类前提；KMeans 需标准化且 k 由业务+轮廓系数共同定；PCA 需标准化且载荷非业务因子；重要性≠因果全部落进结论模板

## 大白话三问（附录 C 必答）
1. **能在 Excel 里验证吗？** 部分能：单特征线性回归（SLOPE/INTERCEPT/RSQ/LINEST）完全可复算；R²≈r² 可与 correlation_matrix 交叉验证。逻辑回归 AUC/OR 需要统计软件或手算 exp(β)；聚类/PCA/RF 是迭代算法，Excel 无法复现——以构造数据的语义结论 + pytest 断言为准。
2. **真实数据接得住吗？** 接得住。中文列名、缺失（listwise+明示）、类别列（one-hot）、零方差列（自动剔除）、极端值（图里暴露）都处理并报告；二分类限制会明确报错而不是悄悄跑。
3. **同一文件跑两次一样吗？** 一样。所有随机过程固定 seed（KMeans random_state=42、train_test_split random_state=42、森林/permutation random_state=42）。