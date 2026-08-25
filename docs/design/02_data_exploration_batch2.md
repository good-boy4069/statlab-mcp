# 数据探查组 · 接口设计文档（批 2）

> 交付物：correlation_matrix / outlier_detect 两个工具的完整接口定义。
> 涉及：多重比较校正（p_adjust）、图片输出协议（附录 D）、IQR 规则。
> 批 1（describe_statistics / data_type_check / missing_report）已确认并实现。

## 全局约定（同批 1，两工具共用）
- 失败 `{"status":"error","message":"中文原因"}`，error 时禁止携带 result 字段
- 数值经 to_jsonable() 输出 Python 原生类型；NaN/Infinity → null
- summary 由代码模板拼数字生成；同一文件两次运行结果一致（本批无随机过程）
- 含图工具：图片存 reports/plots/，返回 JSON **顶层**附加 `__image__`（绝对路径字符串，禁 base64）；
  result 内不重复放图路径（红队裁决 3：`__image__` 与 status/result/summary 平级，schema 记为 `__image__?: string`）
- 中文字体 Microsoft YaHei/SimHei 已探测存在（CJK_FONT_OK=True），标签用中文；若未来环境无字体则降级英文并在图内注明

---

# 工具 4：correlation_matrix(file_path, method="pearson", p_adjust="fdr_bh")

一句话用途：输出全部数值列两两之间的相关系数矩阵 + 逐对 p 值（默认 BH-FDR 多重比较校正），并附成对样本量与"相关≠因果"警示。

## 参数表
| 参数名 | 类型 | 默认值 | 校验规则 | 例子 |
|---|---|---|---|---|
| file_path | str | 必填 | 本地 csv/tsv/xlsx/json；拒绝 UNC/空串 | `"data/clean.csv"` |
| method | str | "pearson" | ∈ {pearson, spearman, kendalltau}；非法值报中文错误 | `method="spearman"` |
| p_adjust | str | "fdr_bh" | ∈ {none, bonferroni, fdr_bh}；非法值报中文错误 | `p_adjust="none"` |

## 统计口径（钉死）
- 相关系数与 p 值**逐对**取自 scipy：`pearsonr` / `spearmanr` / `kendalltau`
  （pandas corr 无 p 值；scipy≥1.9 返回对象，取 `.statistic` 与 `.pvalue`）
- 每对用**成对完整样本**（该两列同时非 NaN 的行），样本量记入 n_pairwise
- 多重比较校正用 `statsmodels.stats.multitest.multipletests(pvals, method=...)`：
  - fdr_bh → `method="fdr_bh"`，取 `pvals_corrected`；bonferroni → `method="bonferroni"`
  - **校正单元 k = n(n-1)/2（上三角对数）**；p_adjust="none" 时不校正
  - 返回中标注 `p_adjust_method`：如 `"fdr_bh（Benjamini-Hochberg 校正，共 10 对）"`
- p<0.001 一律显示为 "<0.001"（仅 summary 文案；result 内 p_value 存真实 float，红队裁决 2）
- 常量列（std=0）：该对 r=null、p=null（协方差无定义）；全缺失列直接排除并列出
- 非数值列自动排除并列入 excluded_columns；排除后数值列 <2 → error

## 返回（成功）
```jsonc
{
  "status": "ok",
  "result": {
    "method": "pearson",
    "n_pairs": 6,                       // 上三角对数 = 4*3/2
    "p_adjust_method": "fdr_bh（Benjamini-Hochberg 校正，共 6 对）",
    "excluded_columns": ["category", "date"],      // 非数值/全缺失列
    "correlation": {"score": {"score": 1.0, "age": -0.11, "income": 0.62}, ...},   // 嵌套全矩阵，对角=1.0
    "p_value":      {"score": {"score": null, "age": 0.45, "income": 0.0003}, ...}, // 对角 null，其余真实 float
    "n_pairwise":   {"score": {"score": 50, "age": 50, "income": 50}, ...}
  },
  "summary": "pearson 相关：强相关对 1 个（score–income r=0.62，p<0.001），其余 |r|<0.3；已 fdr_bh 校正；相关≠因果"
}
```
字段说明：
| 键 | 类型 | 说明 |
|---|---|---|
| correlation / p_value / n_pairwise | dict（嵌套） | 全矩阵（对称、含对角）；p 值对角为 null；常量列所在对 r/p 为 null、n_pairwise 记有效样本 |
| n_pairs | int | 上三角对数 k=n(n-1)/2（即校正单元数） |
| excluded_columns | list[str] | 被排除的非数值/全缺失列，summary 注明 |
| 阈值解释进 summary | str | r 分档：\|r\|≥0.7 强、0.3~0.7 中等、<0.3 弱；仅作描述不作因果 |

## 边界行为表
| 场景 | 行为 |
|---|---|
| 非数值列（category/date） | 自动排除，列入 excluded_columns，summary 注明"已排除 N 列非数值" |
| 数值列 <2 | error："至少需要 2 个数值列才能计算相关矩阵" |
| 常量列 | 该对 correlation=null、p_value=null（协方差无定义），不阻断其他对 |
| 全缺失列 | 排除并列出（同非数值列处理） |
| 列含 NaN | 该对按成对完整样本计算，n_pairwise 如实记录 |
| 列数 >20 | error："数值列超过 20 个，相关矩阵过大，请先挑选列"（防 JSON 爆炸，红队 I5） |
| method / p_adjust 非法值 | error："method 仅支持 pearson/spearman/kendalltau" / "p_adjust 仅支持 none/bonferroni/fdr_bh" |
| 中文列名 | 嵌套 dict 键原样输出 |
| 强相关对 | summary 列出（r≥0.7 或 ≤-0.7），并固定附"相关≠因果" |

## 错误路径（≥3 种）
1. `文件不存在或不可访问: xxx.csv`
2. `至少需要 2 个数值列才能计算相关矩阵`
3. `method 仅支持 pearson/spearman/kendalltau`
4. `数值列超过 20 个，相关矩阵过大，请先挑选列`

## 验证命令与预期值来源（可复算）
```powershell
& .\.venv\Scripts\python.exe -c "from statlab_mcp.tools.data_exploration_correlation_matrix import correlation_matrix; import json; print(json.dumps(correlation_matrix('samples/clean.csv'), ensure_ascii=False, indent=1))"
```
- Excel 可复算：`=CORREL(A1:A5,B1:B5)`；两列 [1,2,3,4,5]×[2,4,6,8,10] → r=1.0、p→0（"<0.001"）；
  完全无关列 → r≈0、p 大
- fdr_bh 复算参考：statsmodels 文档示例或 R p.adjust(method="BH") 同式

---

# 工具 5：outlier_detect(file_path, method="iqr")

一句话用途：按 IQR 规则（Q3+1.5×IQR / Q1−1.5×IQR）在每一数值列中找出异常值，输出异常点位置与数值，并保存箱线图（异常点红色标注）。

## 参数表
| 参数名 | 类型 | 默认值 | 校验规则 | 例子 |
|---|---|---|---|---|
| file_path | str | 必填 | 本地 csv/tsv/xlsx/json；拒绝 UNC/空串 | `"data/dirty.csv"` |
| method | str | "iqr" | 仅 {iqr}（规格 4 唯一定义；zscore 留待时序组 rolling_zscore 场景），非法值报中文错误 | `method="iqr"` |

## 统计口径（钉死）
- IQR 边界：lower = Q1 − 1.5×IQR，upper = Q3 + 1.5×IQR（IQR = Q3 − Q1，分位数 linear 插值，同批 1）
- 异常值 = 有效值中 <lower 或 >upper 的值；**绝不自动剔除数据**，只报告
- n<4 的列无法定义 IQR → 该列 n_outliers=0、bounds=null，summary 注明
- 常量列：IQR=0 → bounds 相等，无异常值（不报错）
- 非数值列跳过并列出（同 correlation_matrix）
- **图（附录 D）**：并列箱线图（每数值列一个 box，异常点 scatter 红色），
  文件名 outlier_detect_all_YYYYmmdd_HHMMSS.png，返回顶层 `__image__` 字段

## 返回（成功）
```jsonc
{
  "status": "ok",
  "result": {
    "method": "iqr",
    "n_numeric_cols": 3,
    "skipped_columns": ["name", "bad_date"],       // 非数值列
    "columns": {
      "extreme": {
        "n_outliers": 1,
        "lower_bound": 57.5, "upper_bound": 135.5,
        "outlier_indices": [5],                    // 0 基行号
        "outlier_values": [1000000000.0]
      },
      "value": {"n_outliers": 0, "lower_bound": 30.3, "upper_bound": 64.1, "outlier_indices": [], "outlier_values": []}
    }
  },
  "__image__": "<PROJECT_ROOT>\\reports\\plots\\outlier_detect_all_20260826_123456.png",
  "summary": "共发现 1 个异常值（extreme 列 1 个：1e9）；异常值仅报告不剔除；箱线图已保存"
}
```
字段说明：
| 键 | 类型 | 说明 |
|---|---|---|
| columns.<列名>.n_outliers | int | 异常值个数 |
| lower_bound / upper_bound | float\|null | IQR 边界；n<4 → null |
| outlier_indices / outlier_values | list | 0 基行号与对应值（按行序） |
| __image__ | str（顶层） | 箱线图绝对路径 |

## 边界行为表
| 场景 | 行为 |
|---|---|
| 无异常值 | 各列 n_outliers=0，summary 注明"未发现异常值"，图照存 |
| 极端值 1e9 | 正常标出（upper 之外），是 IQR 的典型教学场景 |
| 常量列 | bounds 相等、无异常值 |
| n<4 的数值列 | n_outliers=0、bounds=null、summary 注明"列 xxx 样本不足 4 无法定义 IQR" |
| 单行文件 | 同上（n=1<4） |
| 非数值列 | 跳过并列入 skipped_columns |
| 全缺失数值列 | 跳过（n=0<4） |
| method 非法 | error："method 仅支持 iqr" |
| 中文列名 | 键原样输出；图文件名走 _safe_name 清洗 |

## 错误路径（≥3 种）
1. `文件不存在或不可访问: xxx.csv`
2. `method 仅支持 iqr`
3. `至少需要 1 个数值列才能检测异常值`（全表无数值列时）
4. `文件为空或无可读数据`

## 验证命令与预期值来源（可复算）
```powershell
& .\.venv\Scripts\python.exe -c "from statlab_mcp.tools.data_exploration_outlier_detect import outlier_detect; import json; print(json.dumps(outlier_detect('samples/dirty.csv'), ensure_ascii=False, indent=1))"
```
- Excel 可复算：=QUARTILE.INC 求 Q1/Q3 → 手算 Q1−1.5×IQR 与 Q3+1.5×IQR，肉眼核对 dirty.csv 的 1e9 是否在上界之外
- 输出索引核对：pandas 读入后第 5 行（0 基）= 文件第 6 行（1 基）= 生成脚本 loc[5]（extreme=1e9 在 row index 5，0 基）

---

# 附录：批 2 自查（附录 C 组内 3 问）
- ⑦ 参数风格一致：均 file_path 首位；method 均有枚举校验与中文报错，与批 1 一致
- ⑧ 与已确认组无重叠：correlation 与 describe（分布数字）互补不重复；outlier 与 missing（缺失）不同维度；与推断组 hypothesis/effect_size 无重叠（本组不做检验假设）
- ⑨ 统计方法使用条件写明：pearson 需线性关系+近似连续正态（spearman 为秩相关备选）；IQR 法对偏态分布稳健但对小样本（n<4）无定义——均已写明并落入边界表

