# statlab-mcp 进度

> 本文件是会话续接的唯一进度依据，随每次 git 提交更新（附录 B 模板）。

## 里程碑（1-4 状态）
- M1 数据探查组（5 工具）— ✅ 全部完成 + 冒烟 ALL-STDIO-OK（tests/smoke_stdio.py：
  握手/list_tools/5 工具真实 stdio 调用全绿，__image__ 协议往返正常；启动方式实测结论
  = `-m statlab_mcp.server` + cwd 项目根，客户端配置见 docs/clients.md）
  **本周可展示的东西**：5 个可用的数据探查工具 + 一张带中文标签的箱线图（reports/plots/）+
  多客户端接入配置
- M2 统计推断组（6 工具）— ✅ 全部完成（hypothesis_test/normality_test/confidence_interval/
  anova_test/chi_square_test/effect_size，133 测试全绿）
  **本周可展示的东西**：6 个推断工具可用——从"均值是不是 70"到"三组差异+事后两两比较"、
  "类别关联+Fisher 自动切换"到"效应量多大"
- M3 建模组（5 工具）+ 时序组（4 工具）— 待办
- M4 可视化组（5 工具）+ auto_analysis — 待办

## 已完成（工具名 | 提交号 | 日期 | 验收人）
- describe_statistics | feat: describe_statistics (489e948) | 2026-08-26 | 周翔宇（三亲手豁免记录）
- data_type_check | feat: data_type_check | 2026-08-26 | 周翔宇（2026-08-26 起三亲手废止，AI 代做模式，SPEC 增补 16）
- missing_report | feat: missing_report | 2026-08-26 | 周翔宇（AI 代做模式）
- correlation_matrix | feat: correlation_matrix | 2026-08-26 | 周翔宇（AI 代做模式）
- outlier_detect | feat: outlier_detect | 2026-08-26 | 周翔宇（AI 代做模式）
- hypothesis_test | feat: hypothesis_test | 2026-08-26 | 周翔宇（AI 代做模式）
- normality_test | feat: normality_test | 2026-08-26 | 周翔宇（AI 代做模式）
- confidence_interval | feat: confidence_interval | 2026-08-26 | 周翔宇（AI 代做模式）
- anova_test | feat: anova_test | 2026-08-26 | 周翔宇（AI 代做模式）
- chi_square_test | feat: chi_square_test | 2026-08-26 | 周翔宇（AI 代做模式）
- effect_size | feat: effect_size | 2026-08-26 | 周翔宇（AI 代做模式）
- linear_regression | feat: linear_regression | 2026-08-26 | 周翔宇（AI 代做模式）
- logistic_regression | feat: logistic_regression | 2026-08-26 | 周翔宇（AI 代做模式）
- cluster_analysis | feat: cluster_analysis | 2026-08-26 | 周翔宇（AI 代做模式）
- pca_analysis | feat: pca_analysis | 2026-08-26 | 周翔宇（AI 代做模式）

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
- pca_analysis：①✅ 7/7+回归163/163 ②✅ 实跑 samples/clean.csv（PC1 32.7%+PC2 29.8% 累计 62.5%、income 载荷最大 1461.67）+ 独立 eigh 对照（标准化口径一致 1e-6）+ u 主导构造（PC1 载荷同号、噪声列载荷小）核对 ③✅ commit feat: pca_analysis，验收结论（代写）：
  "pca_analysis 找数据里'变化最大的方向'：PC1 是第一方向（解释最多差异），看每个主成分解释了百分之几、每个变量对它贡献多少（载荷）——用于降维（比如 20 个指标浓缩成 3 个）、画图（二维散点）和去冗余。注意：主成分是变量的线性组合，不等于业务因子，别给 PC1 乱起名。"
- cluster_analysis：①✅ 7/7+回归157/157 ②✅ 实跑 samples/clean.csv（k=3 轮廓 0.24、k±1 对照 0.22/0.22、簇样本量 22/15/13）+ 人造两团（质心=团均值 ±1.5 内、真结构 k=2 轮廓最高）核对 ③✅ commit feat: cluster_analysis，验收结论（代写）：
  "cluster_analysis 把样本分成 k 堆'相似的人'：输出每堆的中心（还原成业务单位，如'这堆人平均年龄 45 收入 9200'）和每堆多少人；轮廓系数评估分得清不清楚（>0.5 结构好，<0.25 说明本来就没有清晰的堆）。k 选几？它帮你自动对比 k-1/k+1，但最终拍板靠业务。"
- logistic_regression：①✅ 7/7+回归150/150 ②✅ 实跑 binary_noisy（AUC=0.95 CI[0.88,1.00]、score OR=1.59 显著、acc=0.89 仅对照）+ binary_separable（AUC=1.0 + 分离警告命中规格）+ 不平衡数据 balanced 复制手算对照（sklearn 口径 n/(2*类计数)）③✅ commit feat: logistic_regression，验收结论（代写）：
  "logistic_regression 预测'是/否'：输出每个因素的比值比 OR（X 每加 1 单位，'是'的几率翻 OR 倍）、OR 的 p 值（<0.05 才算数）、模型判别力 AUC（0.5=瞎猜 1=完美，0.8 以上不错），附带混淆矩阵（哪些被认错）。类别严重不平衡时 balanced 自动加权；数据完美可分（score 一刀切）时它会警告'系数不稳定'，这时别信 OR 数值。"
- linear_regression：①✅ 12/12+回归144/144 ②✅ 实跑 samples/clean.csv（income~age：R²=0.09 与 correlation_matrix 的 r² 交叉验证分毫不差、age 显著 p=0.032、DW=1.47）+ 精确线性 y=2x+1（β=[1,2] 精确、R²=1.0）+ one-hot/缺失/零方差场景 ③✅ commit feat: linear_regression，验收结论（代写）：
  "linear_regression 用几个变量预测一个连续目标：输出每个变量的系数（X 每变 1 单位 Y 变多少）、显著性（p<α 才算数）、整体 R²（解释了多少变化）、VIF（变量间打架程度>10 要小心）和残差图（看模型漏洞）。类别列自动转 0/1，缺失行自动剔除并告诉你剔了几行。"
- effect_size：①✅ 7/7+回归133/133 ②✅ 实跑 A/B 组（d=0.352 中效应、CI 含 0 不显著）+ 手算对照（d=1.2、g=1.0839、cliff δ=-0.25、CI 公式精确吻合）核对 ③✅ commit feat: effect_size，验收结论（代写）：
  "effect_size 回答'差异有多大'——p 值看'有没有'，效应量看'多大'：d≈0.2 小、0.5 中、0.8 大。样本大时一点点差异也能显著（p 小），这时看 d 才知道值不值得关心；CI 含 0 表示这个效应也不稳。cliff_delta 用于不服从正态的分布比较。"
- chi_square_test：①✅ 8/8+回归126/126 ②✅ 实跑 data/销量.csv（备注×周次稀疏表 → 正确报错"请合并类别"；真实数据稀疏是常态）+ 均衡 2×2（χ²=0.00 p=1.0 V=0）核对；手算 [[10,15],[12,13]] χ²=0.3247 精确吻合（Yates 校正已关闭=Excel 口径）③✅ commit feat: chi_square_test，验收结论（代写）：
  "chi_square_test 回答'两个类别列有没有关系'：性别×是否购买这种。看 p 值（<0.05 有关联）和 Cramér's V（0~1，越大关系越强）；数值列会自动分箱；期望频数太低的稀疏表会提醒你合并类别或自动换 Fisher。关联≠因果，记住。"
- anova_test：①✅ 11/11+回归118/118 ②✅ 实跑 data/销量.csv（备注分组：1,000 组 n=1 被正确拒绝）+ samples/clean.csv（F=6.04 p=0.0046 拒绝 H0，Tukey 显著 B-C/A-C）+ 手算 F=13 精确吻合 ③✅ commit feat: anova_test，验收结论（代写）：
  "anova_test 回答'三组以上均值差是不是真的'：先查方差齐不齐（Levene），不齐自动换 Welch 校正；显著之后自动做两两比较（Tukey 或 Games-Howell，已按族校正），告诉你哪两组真的有差。多组比较别再一个个跑 t 检验——那会放大假阳性，ANOVA 一次搞定。"
- confidence_interval：①✅ 8/8+回归111/111 ②✅ 实跑 data/销量.csv（mean_t [119.08,145.92] vs bootstrap_median [119.00,146.50] 两口径接近）+ 手算对照（[1..5] 95% CI=[1.036757,4.963243] 精确吻合、90% 区间更窄）核对 ③✅ commit feat: confidence_interval，验收结论（代写）：
  "confidence_interval 给均值（或中位数）一个区间而不是一个数：'均值大概在 [119, 146] 之间'比'均值是 132.5'诚实得多。95% 区间的含义是反复抽样的话 95% 的区间会罩住真值；区间越窄估计越准。数据偏态或怕极端值时用 bootstrap_median（中位数法，对离群值稳）。"
- normality_test：①✅ 13/13+回归103/103 ②✅ 实跑 data/销量.csv（销量 n=6：p=0.7707 近似正态、skew 0.31 与 describe 同口径）+ samples/clean.csv（score 正态放行）+ 指数分布拒正（skew>1）核对 ③✅ commit feat: normality_test，验收结论（代写）：
  "normality_test 回答'这列数据像不像钟形曲线'：p≥0.05 放行（t 检验前提达标），p<0.05 拒绝（改非参方法）。先跑它再决定用 t 检验还是 Wilcoxon；skew/kurtosis 告诉你哪里不像——|skew|>1 明显斜、峰度离 0 远就是尾巴太厚或太扁。注意'不能拒绝'≠'证明是正态'。"
- hypothesis_test：①✅ 12/12+回归90/90 ②✅ 实跑 data/销量.csv（one_sample mu0=130：p=0.6522 不能拒绝、d=0.20）+ samples/clean.csv（score mu0=70：p=0.5586）+ 三组场景手算对照（t=-1.4142/df=4、Welch t=-1.8974/df=5.8824/d=1.2、paired t=-2.2361/d=1.0 全部吻合）③✅ commit feat: hypothesis_test，验收结论（代写）：
  "hypothesis_test 回答'差异是不是真的'：单样本比个数（H0: 均值=某数）、两组比（Welch t 不假设方差相等）、配对比（同一批人测两次）。看 p 值：p<α(默认0.05) 就拒绝'没差异'宣布显著；再看均值差和 95% 区间（含 0 就不显著）、效应量 d（≥0.5 才实际有意义）；非正态它会提醒改用 Wilcoxon（尚未实现）。"
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