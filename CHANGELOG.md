# 变更日志

本项目遵循[语义化版本](https://semver.org/lang/zh-CN/)。所有重大变更均记录于此。

## [Unreleased] - v1.1.0（开发中）

### P1-1 性能补课（冷启动延迟导入 + read_table 文件缓存）
- **延迟导入（固定清单，不扩大）**：`pmdarima` / `sklearn` / `statsmodels` 三库改函数内
  导入；`_common.py` 模块级保留 numpy / pandas / matplotlib(Agg) / scipy（多数工具公共
  依赖且成本低于前三者）；其余依赖一律未动。
  **性能留档**（Windows / Python 3.13.14 / 本仓 venv 实测）：
  ① 进程 import + 注册 → tools/list：v1.0.3 三次均值 ≈ 2.43s（2.37/2.28/2.65）→
  本版 ≈ 1.79s（1.72/1.84/1.80），**约 -26%（省 ~0.6s）**，且进程内不再预载三重依赖；
  ② 已知代价单列：首个重依赖工具 `time_series_forecast` 首调 = statsmodels/pmdarima
  延迟载入 0.70s + auto_arima 拟合 2.26s ≈ 2.96s（仅首次调用发生，此后命中 sys.modules
  与缓存路径）。自动化断言：冷启动子进程 list_tools 后三库不得出现在 sys.modules。
- **read_table 两级键 LRU 文件缓存（规则钉死入 SPEC 第 4 节）**：
  廉价键 `(normcase 路径, size, mtime_ns)` 未命中不读全文件；命中后 SHA256 验内容
  （防 mtime 伪造/精度丢失），不一致即淘汰重读；容量 8 条目 + 500MB 总内存预算
  （memory_usage(deep=True) 口径），超限先淘汰后插入，单条超预算不进缓存；
  读写全程加锁（重复计算允许）、纯内存不持久化、50MB/200 万行防护先于缓存执行；
  命中返回共享引用依赖 pandas≥3 CoW 语义（锁定范围即 ≥3.0.5）。
  测试专用环境变量 `STATLAB_NO_CACHE=1` 完全绕过缓存直读（非行为开关、生产文档不宣传，
  非法取值 stderr 中文告警并忽略，铁律 9）。
- 新增 tests/test_perf_cache.py（7 用例）：两工具同文件三方输出逐字节一致、mtime/SHA
  伪造拦截、LRU 容量淘汰、并发首调、NO_CACHE 非法值告警、懒加载子进程断言、SHA 助手
  对标准库 hashlib 手算对照。
- README 测试计数 282 → 289。

### P0-3 图片返回双轨（ImageContent + `__image__`）
- **STATLAB_IMAGE_MODE 双轨开关**（进程启动解析一次；非法取值 stderr 中文告警回退默认 `path`）：
  `path`（默认）与 v1.0.3 行为逐字段一致（`__image__` 路径，禁 base64）；
  `content` 返回内容块列表 `[ImageContent(mimeType="image/png", data=<PNG base64>), TextContent(JSON)]`，
  TextContent JSON 与 path 模式完全相同、惟去掉 `__image__` 键；`structuredContent`
  同时为去键后的完整 `{status, result, summary}`（对"禁止删改现有返回结构"的唯一显式豁免，
  其余任何模式任何字段不适用）。
- **大图防护（钉死）**：content 模式单张 PNG > 2.0MB 自动回退 path 形态，
  summary 末尾追加"（图片较大已回退路径模式）"，stderr 记录一条 INFO 日志。
- **实现位置**：`statlab_mcp/_imaging.py` + StatlabServer.call_tool 成功路径统一改写——
  26 个工具模块零改动，仅带图成功结果被改写，错误/无图结果原样透传；风险提示
  （base64 进客户端上下文有膨胀风险，仅建议交互式客户端启用）强制写入 SPEC 第 5 节
  （任务原文引用的"SPEC 第 4 节"按现行编号即本节，已在 SPEC 注明映射关系）。
- 验收测试 `tests/test_image_modes.py`（7 用例）：块结构/惟去一键/structuredContent 同构、
  ImageContent base64 解码字节 == 源 PNG 字节逐字节一致、大图回退+INFO 日志、
  无图结果零透传感知、确定性（同输入两次绘图 PNG 字节级一致）、真实 stdio **双子进程**
  （env 启动语义）path 默认行为 + content 标准 MCP 客户端可解析。
- README 测试计数 275 → 282。

### P0-1 MCP resources 能力 + description 双轨模式（默认零变化）
- **resources 静态枚举**（不用 resource templates）：`statlab://spec` = SPEC.md 全文；
  每工具 `statlab://tools/<工具名>/manual` = 模块 docstring 全文 + 设计文档对应小节全文
  （锚点 = 各设计文档顶部新增「工具索引」行，映射表实现于 `statlab_mcp/_resources.py`）。
  数量恒 = 工具数 + 1（当前 27）；契约入 SPEC 第 10 节。
- **打包闭环**：docs/ 整体迁入包内 `statlab_mcp/docs/`（git mv 保留历史），setuptools
  package-data 随 wheel/sdist 分发，运行期经 `importlib.resources` 定位，
  PyPI 安装 / 源码仓 / 任意 cwd 同一口径。全仓文档引用同步更新；
  **tools/list 已知差异披露**：各工具 description 中"与 docs/design/…"同步维护字样
  随迁移变为"statlab_mcp/docs/design/…"，此为默认模式相对 v1.0.3 的唯一字符序列差异
  （其余逐字节一致，由 tests/fixtures/tools_list_full_v1_0_3.json 留档基线 +
  归一化对比测试机械证明）。
- **STATLAB_DESC_MODE 双轨开关**（进程启动解析一次）：`full`（默认）与上述 v1.0.3
  行为一致；`slim` = 一句话功能摘要 + 每参数名称/类型/必填性/取值约束原文。
  slim 实测（stdio 子进程 tools/list 全量 JSON 口径）：28645B → 13220B，削减 53.8%
  （≥50% 达标）；函数级口径 26995B → 12083B（55.2%）。自动化断言：每工具全部参数名
  必须出现在 slim 描述中（防瘦身过度），取值约束文本抽查原文保留。
  开关只影响 tools/list 的 description，不影响任何工具行为、测试、docstring 与 manual；
  非法取值启动时 stderr 中文告警并回退 full（铁律 9）。
- smoke_stdio.py 增补 resources 冒烟（数量=工具数+1、spec/manual 可读非空含工具名）。
- 新增 tests/test_resources_desc.py（9 用例）；README 测试计数 266 → 275。

### P0-2 机器可读错误码（向后兼容扩展）
- **失败结构新增 `error_code` 字段**：`{status:"error", error_code:"<CODE>", message:"<中文>"}`；
  既有 `message` 中文文案逐字不变。码格式 `E`+四位数字，码表钉入 SPEC 第 9 节
  （E1001 参数 / E1002 路径 / E1003 文件缺失 / E1004 空或损坏 / E1005 规模超限 /
  E1006 格式 / E1007 编码 / E1008 缺列 / E1009 列非数值 / E1010 样本量不足 /
  E1011 分组配对结构非法 / E9999 计算兜底）；**码一经发布永久稳定、只增不改不复用**。
- `err()` 的 `code` 参数设为必填（杜绝漏码）；`DataLabError(message, code)` 携带语义码，
  全仓 172 处 raise 点逐条归类（含人工复核修正：Shapiro 样本上限归 E1005、
  D'Agostino 下限归 E1010、期望频数过低与目标类别超限归 E1011、PCA 有效样本<2 归 E1010）；
  pydantic 层参数校验失败由 `StatlabServer` 转换通路注入 `E1001`。
- **被适配的既有断言清单（唯一一处键集合断言）**：
  `tests/test_common.py::test_err_structure_no_result`——错误 dict 键集合
  `["status", "message"]` → `["status", "error_code", "message"]`（并增补 error_code 值断言）。
- 新增 `tests/test_error_codes.py`：14 用例逐码覆盖（每码 ≥1 条真实触发路径，
  统一校验失败结构、无 result、JSON allow_nan=False 安全）；
  `tests/test_protocol_errors.py` NaN 场景增补 stdio 协议通路 `error_code=="E1001"` 断言。
- README 测试计数 252 → 266（check_readme_claims 当次提交同步核对通过）。

## [v1.0.3] - 2026-08-26

### 新增
- **`nonparametric_test`（工具 26）**：非参数检验三法——Wilcoxon 配对（含 0 差剔除与方向效应量 matched rank-biserial r）、Mann-Whitney 两组（rank-biserial r）、Kruskal-Wallis 多组（epsilon²=H/(N−1)）；alpha/alternative 参数与 NaN/Inf 防御；12 个手算对照测试（W=0/p=0.25、U=0/p=2/35、H=7.2 等）。hypothesis_test / normality_test 的"非参检验未实现"警示闭环为"可转用 nonparametric_test"。
- **PyPI 发布**：`pip install statlab-mcp` / `uvx statlab-mcp` / `pipx run statlab-mcp` 一行启动（console script `statlab-mcp`）。
- **packaging 双轨**：pyproject 写入 `dependencies`（范围约束，下限=锁定版本）；requirements.txt 保持开发/CI 锁定权威；SPEC 第 8 节说明。
- **CI 覆盖率证据**：pytest 带 `--cov=statlab_mcp --cov-fail-under=80`；覆盖率写入 job summary；README 顶部真实 Actions 徽章。
- **README 数字防漂移**：`tests/check_readme_claims.py`（pytest 数、工具数声明与实现自动比对，不符 CI 红）。
- **社区基建**：CONTRIBUTING.md、ROADMAP.md（含决策记录）、Dockerfile（python:3.13-slim + Noto CJK + PYTHONUTF8）、.dockerignore、issue 模板。
- **参数命名约定**：SPEC 第 2 节（column/value_col/group_col/x_col·y_col/col_a·col_b/target·features 按场景统一文档化）。
- `docs/design/09_inference_batch3.md`（工具 26 设计文档）。

### 变更
- README 全面更新：26 个工具计数（6 处）、工具表、PyPI 安装段、Docker 段、文档导航、CI/文档徽章。
- `requirements.min.txt` 头部说明同步双轨表述。
- pyproject version 1.0.2 → 1.0.3；description "25 个"→"26 个"。

### 验证
- pytest 252 全绿（新增 12 用例）；ruff All checks passed；smoke ALL-STDIO-OK；覆盖率 ≥80% 阈值断言（本地实测 90% 区间）。
- wheel 安装验证：干净 venv `pip install dist/*.whl` → import/console 脚本可用。
- CI 4 job（Windows/Ubuntu × Python 3.12/3.13）全绿后发布。

## [v1.0.2] - 2026-08-26

### 修复（Qoder 锐评 v1.0.1 轮）
- **协议一致性闭合**：NaN/Inf/类型错误等被 pydantic schema 层拦截的参数，此前由 MCP SDK
  以英文 `Error executing tool ... validation error` 文本返回；现由 `StatlabServer` 子类
  转换为统一的 `{status:"error", message:"参数校验失败：..."}` 中文 JSON，
  与工具内错误格式闭环（锐评 #1）。仅转换参数校验失败场景，其余 ToolError 原样透传，
  与 SDK 分类逻辑对齐（UnexpectedToolError 不误标为参数问题）。
- **mu0 防御补全**：`hypothesis_test` 的 `mu0` 参数此前无有限性校验（NaN/Inf 会污染
  t 统计量与 CI 输出），现拒绝并中文报错。

### 新增
- `requirements.min.txt`：纯 stdio 最小直接依赖裁剪版（锐评 #2 建议，SPEC 第 7 节预告兑现）。
- `tests/test_protocol_errors.py`：协议层错误中文化的 stdio 集成回归测试（3 个用例）。
- `.github/ISSUE_TEMPLATE/`：Bug 报告与功能请求模板；`CHANGELOG.md` 本文档。

### 其他
- README 测试数量口径统一为当前实测值（此前 223/233 并存）。
- **版本声明修正**：真实最低要求为 Python 3.12+（锁定依赖 numpy 2.5.2 要求 `>=3.12`；
  v1.0.1 声明的 3.11+ 有误——CI 首次运行即被 3.11 矩阵的安装失败暴露；pyproject/
  README/SPEC/ruff target 已同步，CI 矩阵改为 3.12/3.13）。
- **跨平台测试修复**：`test_non_seasonal_not_labelled_sarima` 原断言 pmdarima 拟合的
  季节性参数固定为全零，但 auto_arima stepwise 结果跨平台有细微差异（CI Ubuntu 实测
  P/D/Q 非零），改为断言 method/seasonal_order/summary 的同源一致性（M2 修复的实质）。

## [v1.0.1] - 2026-08-26

### 修复（首份外部锐评："锐评报告"全部 17 项）
- **P0**：月/季/年频时序数据 100% 失效（非固定频率 `.nanos` 抛异常/误判超限）——
  改为锚点实测步长，月频 forecast/trend/decompose/anomaly 全链路可用；
  趋势分析对头部缺失数据输出错误结论（kendalltau 遇 NaN 被改写为"无趋势"，
  summary 拼 "nan"）——dropna 后检验并报告 `head_dropped`。
- **P1（M1-M8）**：日内数据按天聚合如实说明；非季节数据不再误标 SARIMA；
  cluster/PCA 含 NaN 数值列 listwise 剔除并报告；cliff_delta 常量组不再误拒
  （负值效应按 |v| 判档并修正档位循环语义）；anomaly_detect 说明书同步 std 判据、
  iqr 不再打印无效 threshold；相关矩阵校正对数用实际可计算对数；卡方常量数值列
  友好中文报错。
- **P2（L1-L10 及工程）**：死代码清理；Welch df 保留小数；配对 mean1/mean2 语义；
  plot_box 补 min/max；plot_scatter 英文分支；趋势斜率恰为 0 不再误报方向；
  簇样本量单位；server 模块级注册（import 启动方式同样注册 25 工具）；
  describe 重复列名如实注明；10+ 测试盲区用例补齐；测试卫生清理
  （tmp_path/绝对路径/死分支）；pywin32 环境标记；Python 版本统一 3.11+；
  图片归档 30 天清理；outlier_detect 数值列上限 200；Linux 中文图降级漏网修复。

### 新增
- GitHub Actions CI：Windows/Ubuntu × Python 3.11/3.13（pytest + ruff + stdio 冒烟）。
- `requirements.txt` 锁定 pytest-cov/ruff；SPEC 增补（Web 栈知情披露、最低版本口径）。

### 红队复检轮
- 独立红队子代理逐项复检 + 重新攻击：确认无 P0/P1/中残留；修复其新发现的
  GBK 表头误报、尾部 NaN 外推、PCA 单样本、CI 镜像四项轻级问题。

## [v1.0.0] - 2026-08-26

### 初始发布
- 25 个纯计算统计工具（数据探查 5 / 统计推断 6 / 建模 5 / 时序 4 / 可视化 5）
  + auto_analysis 编排层方案（文档交付物）。
- 统一协议：`{status:"ok", result, summary}` / `{status:"error", message}`；
  图片顶层 `__image__`；确定性（seed=42，两次运行逐字节一致）。
- 安全防护：仅本地路径（拒绝 UNC/NUL）、50MB/200 万行/500MB 上限、
  xlsx zip 炸弹预检、JSON 20MB 放大防护、异常输出截断、错误中文脱敏。
- 中文全链路：GBK 回退、中文字体图表（无字体降级英文）、中文错误消息。
- 文档：SPEC（协议与统计口径）+ 8 份设计文档 + 客户端接入配置。
- 锁定依赖（requirements.txt 全量 pip freeze）+ 223 个 pytest + ruff + stdio 冒烟。