# statlab-mcp 协议与统计口径（SPEC）

> 面向使用者与 agent 的唯一协议文档：统一返回结构、统计口径定义、图片协议、运行时行为契约。
> 使用与接入见 README 与 docs/clients.md；每个工具的完整参数表/边界表/JSON Schema 见 docs/design/。
> （内部开发记录——验收台账、开发流程增补等——为本地维护，不入库。）

---

## 1. 统一返回协议

- 成功：`{"status": "ok", "result": {...}, "summary": "一句话中文结论"}`
- 失败：`{"status": "error", "message": "中文原因"}`（error 时禁止携带 result 字段）
- 含图工具：顶层附加 `__image__` = 图片绝对路径字符串（与 status/result/summary 平级，不重复进 result，禁 base64）
- result 内数值键一律存真实 float/int；"<0.001" 仅允许出现在 summary 文案
- 数值类型：全部为 Python 原生类型（int/float/bool/str/None）；NaN/Infinity 一律输出 null；Timestamp 转字符串

## 2. 参数命名约定（全部工具统一，v1.0.3 起文档化）

按"语义场景"命名，agent 与使用者按表查参，避免混用：

| 参数名 | 语义 | 使用工具 |
|---|---|---|
| `column` | 单值分析列（数值） | hypothesis_test / normality_test / confidence_interval / plot_box / plot_histogram |
| `value_col` | 分组或时序场景下的数值列 | effect_size / anova_test / nonparametric_test(mw·kw) / 时序组 5 工具 |
| `group_col` | 分组列（类别） | effect_size / anova_test / nonparametric_test(mw·kw) |
| `sample2_col` | 配对第二组测量 | hypothesis_test(paired) / nonparametric_test(wilcoxon) |
| `col_a` / `col_b` | 两列类别变量 | chi_square_test |
| `x_col` / `y_col` | 散点坐标列 | plot_scatter |
| `target` / `features` | 建模目标列 / 特征列清单 | linear_regression / logistic_regression / feature_importance |
| `date_col` | 时序日期列 | 时序组 5 工具（值列同用 value_col） |

设计准则：同一语义永不换名；新工具按表选名；docstring 参数表即权威说明。

## 3. 统计口径定义（所有工具钉死）

- 分位数 = linear 插值（与 numpy.percentile 默认、Excel QUARTILE.INC 等价，非 QUARTILE.EXC）；验证示例 [1,2,3,4] → q1=1.75, q3=3.25
- 偏度 = scipy.stats.skew(x, bias=False)（Fisher 样本偏度）；峰度 = scipy.stats.kurtosis(x, fisher=True, bias=False)（超额峰度，正态=0）
- std 统一 ddof=1（同 Excel STDEV.S）
- 边界行为统一口径：文件不存在 / 空文件（0B，"文件为空或无可读数据"）/ 仅表头 / 全缺失列 / 列含空单元格 / 列不存在 / 非数值列 / 重复列名 / 中文及含空格特殊字符列名 / 非法日期（如 2024-02-30）/ 极端值 / 常量列；n=1 时 std/q1/q3=None 不报错、n=0 报错
- correlation_matrix 细节：p 值逐对取 scipy.stats.pearsonr；fdr_bh 用 statsmodels.stats.multitest.multipletests，校正单元 k=n(n-1)/2 上三角；常量列 r=None、p=None；数值列 >20 拒绝

## 4. 数据读取与安全（运行时行为契约）

- 格式白名单 {csv, tsv, xlsx, json}，其他格式中文报错；xlsx 只读第一个 sheet
- read_table 三路分派：csv/tsv → utf-8-sig → gbk → 中文报错；json → 仅 UTF-8（不做 gbk 回退，GBK 静默乱码比报错更危险）；xlsx → openpyxl 引擎
- check_file：拒绝开头为 \\、//、\\?\、\.\ 的路径（UNC）与 NUL 字节，先 abspath 归一化；>50MB 拒绝；5-50MB 预检行数（>200 万行拒）；读取后内存占用 >500MB 拒绝
- 资源防护：时序工具重采样/聚合前日期跨度校验（预估点数 >200 万即拒绝）；xlsx 打开前 zip 解压体积预检（>500MB 拒绝，防压缩炸弹）；json 文件 >20MB 拒绝（解析放大防护）；异常/异常列表等输出有数量上限（截断并标记）
- 路径信任声明：工具不校验文件来源（按传入路径直接读取），请勿传入不受信来源的路径

## 5. 图片输出协议（唯一约定，禁止偏离）

1. 所有图片存 `reports/plots/YYYYmmdd/`（按日期归档），文件名 = `工具名_<主列名或all>_YYYYmmdd_HHMMSS_fff.png`（多列图用 all，毫秒时间戳防覆盖、防堆积）；
2. 返回 JSON 的 `__image__` 字段 = 图片绝对路径字符串，禁止 base64（防撑爆上下文）；
3. 统一封装 save_plot(fig, name)：matplotlib.use("Agg") 必须在 import pyplot 之前；中文字体 Microsoft YaHei/SimHei + unicode_minus=False（字体缺失时降级英文并在图内注明）；dpi=150，bbox_inches="tight"；
4. agent 看图：DeepSeek Harness 用 read_image 工具，Claude Code 用 Read 工具读 `__image__` 路径。

## 6. auto_analysis 协议（编排层）

用户丢 CSV + 自然语言问题，自动产出 Markdown 报告。二选一（默认 A，禁止混用）：
- 方案 A（client 侧工作流，推荐）：它不是 MCP 工具，而是一份交付物文档《分析方法选择决策树 + 报告模板》+ 示例 agent 提示词；由外层 agent 按决策树调用第一层工具、套模板生成报告（见 docs/design/08_auto_analysis.md）。
- 方案 B（server 侧规则工具）：若实现为 MCP 工具，必须是 100% 确定性代码（规则决策树，可测试），输出结构化 {chosen_methods, tool_calls_plan, report_template}，不含任何 LLM 调用；"LLM 解释"只发生在 client 拿结果之后。

无论 A/B：报告固定章节（数据概览/方法选择理由/结果/结论/局限）；防幻觉铁律——报告中每个数字必须来自第一层工具返回的 JSON 并标注来源工具名，任何无来源数字禁止出现；想用的方法未实现时必须如实告知，禁止 LLM 心算替代；结论必须附固定局限声明（样本量、p 值是否经多重比较校正、相关≠因果、未做外部验证）。

## 7. 运行时行为契约（日志/描述/校验）

- 第一层工具禁止输出到 stdout（污染 stdio JSON-RPC 流）；日志走 logging → stderr
- 全部工具签名带完整类型注解；返回前经统一 JSON 类型转换（单入口 + 注册层兜底）
- MCP 工具描述 = 各工具模块 docstring（含参数表/返回/示例，作为 agent 使用说明书）
- 错误处理：对外一律中文脱敏文案（如"计算失败，请检查数据内容与参数设置"），不泄内部异常/路径；完整堆栈由服务端 logger 记录到 stderr
- 输入校验：路径拒绝 NUL；浮点参数（threshold/alpha/confidence）拒绝 NaN/Inf

## 8. 依赖与版本（实测记录）

最低要求 Python 3.12+（pyproject `requires-python >=3.12`——锁定依赖 numpy 2.5.2 的最低要求；代码 target py312；README/CI 同口径，CI 于 3.12/3.13 双版本实测）。
以下为 Python 3.13.14 下的实测兼容组合：numpy 2.5.2 / pandas 3.0.5 / scipy 1.18.1 / statsmodels 0.14.6 / sklearn 1.9.0 / matplotlib 3.11.1 / pmdarima 2.1.1 / openpyxl 3.1.5 / mcp 2.1.0 / pytest 9.1.1（互操作冒烟通过：OLS/ARIMA/KMeans/read_excel 全真跑）。
pywin32 仅 Windows 安装（requirements 环境标记 `sys_platform == "win32"`），Linux/macOS 自动跳过。
若未来出现不兼容：降级路径 = pandas==2.3.*（numpy 不降），重跑冒烟并更新本记录。
requirements.txt 为**开发/CI 锁定权威**（可复现性承诺）；pyproject.toml 的 `dependencies` 为**发布用范围约束**（v1.0.3 起双轨：下限=当前锁定版本，`pip install statlab-mcp` 时由 pip 解析范围内最新版；生产环境建议锁定 requirements.txt 或等价 pin）。
requirements 为 pip freeze 全量锁定，含 mcp 包传递引入的 Web 组件（starlette/uvicorn/PyJWT 等）：
纯 stdio 服务并不使用它们，保留仅为依赖树可复现（知情披露；若需最小攻击面可自行裁剪为
requirements.min）。