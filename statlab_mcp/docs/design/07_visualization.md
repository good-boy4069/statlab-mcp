# 可视化组 · 接口设计文档（整组交付）
> **工具索引**（v1.1.0 起 statlab://tools/<名>/manual 取本文件对应小节，锚点=一级标题行“# 工具 N：<函数名>(”）：plot_scatter（21）｜plot_histogram（22）｜plot_heatmap（23）｜plot_forecast（24）｜plot_box（25）

> 交付物：plot_scatter / plot_histogram / plot_heatmap / plot_forecast / plot_box。
> 本组为纯作图工具（核心实现）：计算部分仅输出"读图必需的最小统计量"，与探查/推断组
> 的对应计算工具不重复（heatmap 直接复用 correlation_matrix 的矩阵计算逻辑）。
> 图协议（附录 D）全部由 _common.save_plot 承载：Agg 先行、中文字体（缺失降级英文并图内注明）、
> dpi=150、文件名 工具名_<主列名或all>_时间戳.png、返回顶层 __image__ 绝对路径。

## 本组统一约定
- 缺失处理：成对/列内 dropna，缺失数写入 result（如 n=成对有效数、dropped_rows）
- 非数值列校验：目标列须为数值（中文报错）；heatmap 自动排除非数值列并列出
- 中文/特殊列名：键原样输出；图文件名走 _safe_name 清洗
- 全部确定性（无随机过程）；两次运行图文件不同仅因时间戳命名（result 一致）
- 图内标注：统计量直接画进图（读数不依赖外部 JSON）

---

# 工具 21：plot_scatter(file_path, x_col, y_col)

一句话用途：两列关系散点图（图上标 Pearson r 与样本量）。
## 参数表：file_path / x_col / y_col（均必填，须存在且数值列）
## 口径: 成对 dropna（n=成对有效数、dropped_rows）；图上标注 `r=xx（n=yy）`；
   x/y 全部缺失 -> error"列 xxx 无有效数据"；r 用 numpy.corrcoef（仅标注不导出 p）
## 返回（成功）
```jsonc
{
  "status": "ok",
  "result": {"x_col": "age", "y_col": "income", "n": 50, "dropped_rows": 0,
             "pearson_r": 0.30},
  "__image__": "C:\\...\\plot_scatter_all_....png",
  "summary": "散点图已保存：age vs income（n=50，r=0.30）；相关≠因果"
}
```
边界：单点/常量列（r 无法计算）-> r=null 并图内注明；非数值列 error。

---

# 工具 22：plot_histogram(file_path, column)

一句话用途：单列分布直方图（图上标 n/mean/std；分箱数 = min(40, max(8, ceil(√n)))）。
## 参数：file_path / column（数值列）
## 返回：result{column, n, n_missing, mean, std, bins} + __image__
边界：n<2 -> error"至少需要 2 个有效值"；全缺失 error；极端值如实参与（图会拉长横轴，注明）。

---

# 工具 23：plot_heatmap(file_path)

一句话用途：全部数值列两两相关热力图（颜色=相关强度，格内标 r）。
## 参数：仅 file_path
## 口径: 复用 correlation_matrix 的矩阵逻辑（仅取相关系数、无 p/无校正）；至少 2 数值列
   （否则 error："至少需要 2 个数值列"）；数值列>20 -> error（同 correlation 上限）
## 返回：result{numeric_columns, n, matrix(嵌套，对角1.0)} + __image__
边界：常量列对 r=null（格内标"—"）；排除列列出。

---

# 工具 24：plot_forecast(file_path, date_col, value_col)

一句话用途：时序折线图（**仅作图不预测**，与工具 17 不重复计算）——原值线 + 7 日移动平均线。
## 参数：file_path / date_col / value_col
## 口径: 复用 _prepare_series（五项前置照走：插值/聚合/时区都报告）；7 日均线 rolling(7, min_periods=3)
## 返回：result{n, freq, metadata(五项前置), series_min/max/last} + __image__
边界：n<5 -> error"样本过短（n=N<5）"；日期无法解析 error。

---

# 工具 25：plot_box(file_path, column)

一句话用途：单列箱线图（图上标 n/q1/中位/q3/异常数——IQR 规则，与 outlier_detect 同口径但单列）。
## 参数：file_path / column（数值列）
## 口径: IQR 边界（同 outlier_detect）；异常点数（>边界）计入 result；图上标注五数概括
## 返回：result{column, n, n_missing, q1, median, q3, lower_bound, upper_bound, n_outliers} + __image__
边界：n<4 -> bounds=null、n_outliers=0（同 outlier_detect 语义）；常量列正常。

---

# 附录：可视化组自查（附录 C 组内 3 问）
- ⑦ 参数风格一致：file_path 首位 + 列参数；全部返回 __image__ 顶层 + 最小统计 result
- ⑧ 无重叠：本组只有图+最小统计；heatmap 复用 correlation 矩阵（无 p 值计算）；
  24 与 17 明确分工（作图 vs 预测）；25 与 5（多列 Box+异常检测）单列版互补不重复
- ⑨ 使用条件写明：散点 r 标注（线性相关提示）、直方图分箱规则、heatmap 需要 ≥2 数值列、
  IQR 异常点口径注明

## 大白话三问
1. **能在 Excel 里验证吗？** 能看图：散点/直方图/箱线图与 Excel 图表样式一致，r 用 CORREL、
   五数概括用 QUARTILE.INC 可复算；图上的数字都能在探测组工具里交叉查到。
2. **真实数据接得住吗？** 接得住。中文列名（文件名自动清洗）、缺失成对剔除并报数、
   非数值列自动排除（heatmap）、时序工具的五项前置在 plot_forecast 里照走。
3. **同一文件跑两次一样吗？** result 一样；图文件因时间戳命名不同（防覆盖约定），
   图内容本身一样。
