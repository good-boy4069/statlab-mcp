# samples/clean.csv 数据分析报告（方案 A 演示）

> 演示用途：外层 agent 按《方法选择决策树》调用第一层工具后套模板的产出样例。
> 所有数字均来自工具返回 JSON 并标注来源；报告由 AI 转述而非计算。

## 1. 数据概览
- 样本量 N=50，列数 6；总缺失 0 个（缺失率 0.0%）[来源: missing_report.total_missing / overall_missing_rate]
- 列类型：id=整数、age=整数、score=数值、income=数值、category=类别、date=日期，
  无脏值提示 [来源: data_type_check.columns.*.detected_type]
- 目标列 income：均值 7727.89、中位数 7387.97、标准差 2102.53、范围 [3735.91, 13827.72]、
  偏度 0.77（右偏）、无缺失 [来源: describe_statistics.columns.income]

## 2. 方法选择理由
- 问题类型：预测连续值（"什么因素影响收入"）+ 关系探索（收入与哪些列一起变）
- 使用工具：
  - correlation_matrix（pearson，fdr_bh 校正）——找与收入相关的列
  - linear_regression（income ~ age + score）——量化影响系数与显著性
  - plot_heatmap——直观呈现全部相关
- 理由：income 与 age 均为连续/整数列 → Pearson 相关与 OLS 回归适用；
  score 也纳入回归观察"成绩是否影响收入"

## 3. 结果
- **相关**：|r|≥0.2 的只有 age–income 一对：r=0.30
  [来源: correlation_matrix.correlation.age.income]；其余对 |r|<0.2
  （score–income r=0.02、id–income r≈0 [来源: correlation_matrix.correlation]）
- **回归**：R²=0.093（调整后），即 age+score 只解释收入变化的 9.3%
  [来源: linear_regression.r_squared]；系数：age β=49.90（p=0.034）、
  score β=4.82（p=0.878）[来源: linear_regression.coefficients]
- **图**：图 1 相关热力图（`C:\dsh工作文件夹\statlab-mcp\reports\plots\plot_heatmap_all_20260826_031536.png`）
  [来源: plot_heatmap.__image__]

## 4. 结论
1. 收入与年龄存在弱正相关（r=0.30），回归中 age 每 +1 岁收入平均 +49.9 元，p=0.034<0.05
   显著 [来源: correlation_matrix / linear_regression.coefficients.age]
2. score 对收入无显著解释力（p=0.878）[来源: linear_regression.coefficients.score]
3. 年龄+成绩合计只解释收入 9.3% 的变化，收入的主要影响因素不在本数据中
   [来源: linear_regression.r_squared]

## 5. 局限
- 样本量 N=50（偏小，检验功效有限）
- 相关矩阵 p 值已做 fdr_bh 校正；回归未做多重比较（系数独立检验）[来源: correlation_matrix.p_adjust_method]
- 相关≠因果：age 与收入相关不代表年龄"导致"收入
- 模型未做外部验证（无测试集/新数据核对）