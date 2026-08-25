# statlab-mcp 进度

> 本文件是会话续接的唯一进度依据，随每次 git 提交更新（附录 B 模板）。

## 里程碑（1-4 状态）
- M1 数据探查组（5 工具）— 进行中：阶段二 项目初始化（安装已完成待验收）
- M2 统计推断组（6 工具）— 待办
- M3 建模组（5 工具）+ 时序组（4 工具）— 待办
- M4 可视化组（5 工具）+ auto_analysis — 待办

## 已完成（工具名 | 提交号 | 日期 | 验收人）
（尚无工具验收；初始化完成后逐工具登记）

## 进行中（当前工具、当前步骤）
- 阶段二：项目初始化（LICENSE/README/.gitignore/PROGRESS/SPEC/samples 生成 → git init + 首次提交）

## 待办（按组列）
- 探查组：describe_statistics → correlation_matrix → missing_report → outlier_detect → data_type_check
- 推断组：hypothesis_test → anova_test → chi_square_test → normality_test → confidence_interval → effect_size
- 建模组：linear_regression → logistic_regression → cluster_analysis → pca_analysis → feature_importance
- 时序组：time_series_forecast → seasonal_decompose → trend_analysis → anomaly_detect
- 可视化组：plot_scatter → plot_histogram → plot_heatmap → plot_forecast → plot_box
- 编排层：auto_analysis（方案 A，最后交付，交付前出方案设计文档）
- 基础设施：tools/_common.py（七函数，先于工具 1）

## 验收状态（每工具三条件逐项勾选：①pytest 绿 ②两套数据实跑核对 ③commit+PROGRESS 验收人=使用者）
（表格在首个工具验收时建立）

## 数据与样例（data/ samples/ 内容说明）
- data/：空目录（不入库）。只放使用者亲手造的 8-12 行测试 CSV（三亲手用）
- samples/：入库。clean.csv（50x6）、dirty.csv（20x5 含空单元格/全缺失列/非法日期/极端值）、timeseries.csv（120 天 3 缺失）；生成脚本 make_sample_data.py（seed=42）
- tests/fixtures/：入库。复用 samples 生成函数 + 特殊变体（重复列名/中文列名/常量列/单行/tiny_numeric/空文件/仅表头）

## 环境与依赖（以实测为准，2026 安装记录）
- Python 3.13.14 + venv + 清华源；pip check 零冲突；互操作冒烟 ALL-INTEROP-OK
- numpy 2.5.2 / pandas 3.0.5 / scipy 1.18.1 / statsmodels 0.14.6 / sklearn 1.9.0 / matplotlib 3.11.1 / pmdarima 2.1.1 / openpyxl 3.1.5 / mcp 2.1.0 / pytest 9.1.1
- 中文字体 Microsoft YaHei/SimHei 探测存在；requirements.txt 为依赖唯一权威
- git：首次提交用占位身份 your-github-username / your-email@example.com（core.autocrlf=true），**待使用者提供真实 GitHub 用户名与邮箱后执行 `git config user.name/user.email` 修正**

## 下次会话起点（从哪继续、先跑什么命令）
1. 完成初始化：写 docs/SPEC.md（附录 A-D 原文）→ git init/config/首次提交
2. 运行 `& .\.venv\Scripts\python.exe samples\make_sample_data.py` 与 `tests\make_fixtures.py`（如未生成）
3. 实现 tools/_common.py（七函数）+ tests/test_common.py
4. 探查组设计文档（批 1：describe/data_type_check/missing_report；批 2：correlation/outlier_detect）