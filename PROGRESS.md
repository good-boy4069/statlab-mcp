# statlab-mcp 进度

> 本文件是会话续接的唯一进度依据，随每次 git 提交更新（附录 B 模板）。

## 里程碑（1-4 状态）
- M1 数据探查组（5 工具）— ✅ 全部完成 + 冒烟 ALL-STDIO-OK（tests/smoke_stdio.py：
  握手/list_tools/5 工具真实 stdio 调用全绿，__image__ 协议往返正常；启动方式实测结论
  = `-m statlab_mcp.server` + cwd 项目根，客户端配置见 docs/clients.md）
  **本周可展示的东西**：5 个可用的数据探查工具 + 一张带中文标签的箱线图（reports/plots/）+
  多客户端接入配置
- M2 统计推断组（6 工具）— 待办（下一个：hypothesis_test 设计文档）
- M3 建模组（5 工具）+ 时序组（4 工具）— 待办
- M4 可视化组（5 工具）+ auto_analysis — 待办

## 已完成（工具名 | 提交号 | 日期 | 验收人）
- describe_statistics | feat: describe_statistics (489e948) | 2026-08-26 | 周翔宇（三亲手豁免记录）
- data_type_check | feat: data_type_check | 2026-08-26 | 周翔宇（2026-08-26 起三亲手废止，AI 代做模式，SPEC 增补 16）
- missing_report | feat: missing_report | 2026-08-26 | 周翔宇（AI 代做模式）
- correlation_matrix | feat: correlation_matrix | 2026-08-26 | 周翔宇（AI 代做模式）
- outlier_detect | feat: outlier_detect | 2026-08-26 | 周翔宇（AI 代做模式）

## 进行中（当前工具、当前步骤）
- 阶段二：项目初始化 ✅（提交 chore: 项目初始化 21e4d94；git 身份 good-boy4069/369235902@qq.com，LICENSE=周翔宇）
- tools/_common.py：✅ 已实现并测试全绿（21/21）+ MCPServer 链路预检 LINK-CHECK-OK（提交 feat: _common 待做）
- 下一步：探查组设计文档批 1（describe/data_type_check/missing_report），等使用者确认 _common 后开始

## 重要实测结论（mcp 2.1.0）
- `mcp.server.fastmcp.FastMCP` 已不存在；高层服务器 = `mcp.server.mcpserver.MCPServer`（FastMCP 1.x 重构继承者，add_tool/tool/call_tool 兼容）
- list_tools/call_tool/run_stdio_async 均为 async API（await 调用）
- 工具注册名默认 = 函数名（add_tool 可传 name 覆盖）；call_tool 返回 CallToolResult，content[0].text 为 JSON 字符串
- 此结论影响里程碑 1 冒烟测试（npx inspector 走 stdio run() 不受影响）

## 待办（按组列）
- 探查组：describe_statistics → correlation_matrix → missing_report → outlier_detect → data_type_check
- 推断组：hypothesis_test → anova_test → chi_square_test → normality_test → confidence_interval → effect_size
- 建模组：linear_regression → logistic_regression → cluster_analysis → pca_analysis → feature_importance
- 时序组：time_series_forecast → seasonal_decompose → trend_analysis → anomaly_detect
- 可视化组：plot_scatter → plot_histogram → plot_heatmap → plot_forecast → plot_box
- 编排层：auto_analysis（方案 A，最后交付，交付前出方案设计文档）
- 基础设施：tools/_common.py（七函数，先于工具 1）

## 验收状态（每工具三条件逐项勾选：①pytest 绿 ②两套数据实跑核对 ③commit+PROGRESS 验收人=使用者）
- describe_statistics：①✅ 14/14+回归35/35 ②✅ data/销量.csv（使用者数据，AI 代跑）+ samples/dirty.csv 核对：销量 n=6/n_missing=2、库存全缺失 null 不中断、dirty extreme 均值被 1e9 拉高=极端值信号 ③✅ commit feat: describe_statistics，验收结论（使用者授权代写）：
  "describe_statistics 把一列数据压成 11 个数字：有多少个数、缺多少、平均水平、波动多大、从哪到哪、歪不歪。在拿到新数据不知道从哪看起时用，先看 n 和缺失数判断数据能不能信，再看均值和最大值差多远判断有没有极端值。"
  ⚠️ 三亲手豁免记录（唯一一次）：使用者 2026-08-26 明确授权 AI 代做三亲手并确认验收。
- data_type_check：①✅ 10/10+回归46/46 ②✅ 实跑 data/销量.csv（备注列混 "1,000" → text+脏值提示 1 个）+ samples/dirty.csv（bad_date→date+非法日期 2024-02-30、empty_col→missing）核对 ③✅ commit feat: data_type_check，验收结论（代写）：
  "data_type_check 给每列贴类型标签：数字、整数、日期、类别、文本、混合、全空。拿到新文件不知道该用什么工具、哪列能算数时先用它；看到 mixed 或"疑似数字文本"就去洗数据，看到 missing 列就直接跳过。"
  ⚠️ 三亲手已于 2026-08-26 经使用者决定废止（AI 代做模式，详见 SPEC 增补 16）。
- outlier_detect：①✅ 11/11+回归78/78 ②✅ 实跑 data/销量.csv（无异常、备注跳过、库存样本不足注记）+ samples/dirty.csv（1e9 在上界 137 之外检出、idx=5）+ clean.csv（income 13827.72 为真实正态尾部异常——非 bug）核对；__image__ 顶层绝对路径真实验证 ③✅ commit feat: outlier_detect，验收结论（代写）：
  "outlier_detect 用 IQR 规则找'离群太远'的值：先算 Q1/Q3，正常范围是 Q1−1.5×IQR 到 Q3+1.5×IQR，范围外的标红。数据到手后跑一遍，先看异常值是录入错误（1e9）还是真实大单——它只报告不删除，删不删你决定；样本不足 4 的列算不了，属正常。"
- correlation_matrix：①✅ 12/12+回归66/66 ②✅ 实跑 data/销量.csv（周次–销量 r=0.66 中等、成对样本 6 个、库存/备注正确排除）+ samples/clean.csv（无强相关对、age–income r=0.30、fdr_bh 校正 6 对）核对 ③✅ commit feat: correlation_matrix，验收结论（代写）：
  "correlation_matrix 算出两两相关：r 在 -1~1 之间，越接近 ±1 关联越强，接近 0 没关系。想找'哪两列一起变'时用它；先看 |r|≥0.7 的强对，再看 p 值是否显著（已自动做 fdr_bh 校正），样本量小的对（n<10）别信；记住相关≠因果。"
- missing_report：①✅ 8/8+回归54/54 ②✅ 实跑 data/销量.csv（总缺失 14、率 43.75%、库存全缺失、成对"库存&备注"4 行）+ samples/dirty.csv（总缺失 23/率 23%、完整行 0=全缺失列所致）核对 ③✅ commit feat: missing_report，验收结论（代写）：
  "missing_report 告诉你每列缺多少、整张表缺多少、哪些列总是一起缺。数据到手先看缺失率超不超 20%，再看成对缺失——两列一起丢通常是同源故障，比单列丢更值得查；全缺失列直接跳过别较劲。"

## 数据与样例（data/ samples/ 内容说明）
- data/：空目录（不入库）。只放使用者亲手造的 8-12 行测试 CSV（三亲手用）
- samples/：入库。clean.csv（50x6）、dirty.csv（20x5 含空单元格/全缺失列/非法日期/极端值）、timeseries.csv（120 天 3 缺失）；生成脚本 make_sample_data.py（seed=42）
- tests/fixtures/：入库。复用 samples 生成函数 + 特殊变体（重复列名/中文列名/常量列/单行/tiny_numeric/空文件/仅表头）

## 环境与依赖（以实测为准，2026 安装记录）
- Python 3.13.14 + venv + 清华源；pip check 零冲突；互操作冒烟 ALL-INTEROP-OK
- numpy 2.5.2 / pandas 3.0.5 / scipy 1.18.1 / statsmodels 0.14.6 / sklearn 1.9.0 / matplotlib 3.11.1 / pmdarima 2.1.1 / openpyxl 3.1.5 / mcp 2.1.0 / pytest 9.1.1
- 中文字体 Microsoft YaHei/SimHei 探测存在；requirements.txt 为依赖唯一权威
- git：身份已配置 good-boy4069 / 369235902@qq.com（core.autocrlf=true）；LICENSE Copyright=周翔宇

## 下次会话起点（从哪继续、先跑什么命令）
1. 完成初始化：写 docs/SPEC.md（附录 A-D 原文）→ git init/config/首次提交
2. 运行 `& .\.venv\Scripts\python.exe samples\make_sample_data.py` 与 `tests\make_fixtures.py`（如未生成）
3. 实现 tools/_common.py（七函数）+ tests/test_common.py
4. 探查组设计文档（批 1：describe/data_type_check/missing_report；批 2：correlation/outlier_detect）