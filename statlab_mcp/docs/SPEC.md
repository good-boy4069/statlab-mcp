# statlab-mcp 协议与统计口径（SPEC）

> 面向使用者与 agent 的唯一协议文档：统一返回结构、统计口径定义、图片协议、运行时行为契约。
> 使用与接入见 README 与 statlab_mcp/docs/clients.md；每个工具的完整参数表/边界表/JSON Schema 见 statlab_mcp/docs/design/。
> （内部开发记录——验收台账、开发流程增补等——为本地维护，不入库。）
>
> **修订记录**：v1.0.3（2026-08-26，参数命名约定表 + 依赖双轨）；v1.1.0（2026-08-27，
> 第 1/9/10/4/5/2 节：error_code 错误码表、resources 与 description 双轨、文件缓存契约、
> 图片双轨、新参数约定）。

---

## 1. 统一返回协议

- 成功：`{"status": "ok", "result": {...}, "summary": "一句话中文结论"}`
- 失败：`{"status": "error", "error_code": "<CODE>", "message": "中文原因"}`（v1.1.0 起新增机器可读 `error_code`，码表见第 9 节；error 时禁止携带 result 字段；message 文案自 v1.0.3 起保持不变，agent 程序化分支判断请依据 error_code）
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
| `scenario` / `effect_size` | 分析场景选择 / 标准化效应量 Cohen's d | power_analysis |
| `p1` / `p2` | 两个总体比例（成对提供） | power_analysis(two_proportions) |
| `power_target` | 目标功效（求 n 模式） | power_analysis |

设计准则：同一语义永不换名；新工具按表选名；docstring 参数表即权威说明。

## 3. 统计口径定义（所有工具钉死）

- 分位数 = linear 插值（与 numpy.percentile 默认、Excel QUARTILE.INC 等价，非 QUARTILE.EXC）；验证示例 [1,2,3,4] → q1=1.75, q3=3.25
- 偏度 = scipy.stats.skew(x, bias=False)（Fisher 样本偏度）；峰度 = scipy.stats.kurtosis(x, fisher=True, bias=False)（超额峰度，正态=0）
- std 统一 ddof=1（同 Excel STDEV.S）
- 边界行为统一口径：文件不存在 / 空文件（0B，"文件为空或无可读数据"）/ 仅表头 / 全缺失列 / 列含空单元格 / 列不存在 / 非数值列 / 重复列名 / 中文及含空格特殊字符列名 / 非法日期（如 2024-02-30）/ 极端值 / 常量列；n=1 时 std/q1/q3=None 不报错、n=0 报错
- correlation_matrix 细节：p 值逐对取 scipy.stats.pearsonr；fdr_bh 用 statsmodels.stats.multitest.multipletests，校正单元 k=n(n-1)/2 上三角；常量列 r=None、p=None；数值列 >20 拒绝
- correlation_matrix 秩相关（v1.1.0 钉死）：spearman = scipy.stats.spearmanr；kendall（官方别名）/kendalltau（历史枚举名，向后兼容保留）= scipy.stats.kendalltau，无并列小样本时 scipy method="auto" 给精确 p；多重比较校正（fdr_bh/bonferroni）与 pearson 分支完全同口径同代码路径；summary 注明所用方法与是否经 fdr_bh 校正（pearson 默认分支 summary 逐字节不变）

## 4. 数据读取与安全（运行时行为契约）

- 格式白名单 {csv, tsv, xlsx, json}，其他格式中文报错；xlsx 只读第一个 sheet
- read_table 三路分派：csv/tsv → utf-8-sig → gbk → 中文报错；json → 仅 UTF-8（不做 gbk 回退，GBK 静默乱码比报错更危险）；xlsx → openpyxl 引擎
- check_file：拒绝开头为 \\、//、\\?\、\.\ 的路径（UNC）与 NUL 字节，先 abspath 归一化；>50MB 拒绝；5-50MB 预检行数（>200 万行拒）；读取后内存占用 >500MB 拒绝
- 资源防护：时序工具重采样/聚合前日期跨度校验（预估点数 >200 万即拒绝）；xlsx 打开前 zip 解压体积预检（>500MB 拒绝，防压缩炸弹）；json 文件 >20MB 拒绝（解析放大防护）；异常/异常列表等输出有数量上限（截断并标记）
- **read_table 进程内文件缓存（v1.1.0 P1-1，规则钉死）**：
  - 两级键查询：先查廉价键 `(normcase 归一化绝对路径, 文件大小, mtime_ns)`，未命中不读全文件；命中后再验证内容 SHA256（防 mtime 被伪造/精度丢失），不一致按未命中处理并淘汰旧条目；
  - 容量上限 8 条目，LRU 淘汰；总内存预算 500MB（按 memory_usage(deep=True) 估算），超限先淘汰后插入；单条自身超预算不进缓存（照常返回）；
  - 并发语义：读写/淘汰全程加锁，两请求同时未命中同一键允许重复计算；
  - 不跨进程持久化、不落盘；50MB/200 万行预检等防护先于缓存执行，命中条目与该文件首次通过解析后内存闸门的结果逐字节一致；
  - 命中返回共享引用依赖 pandas≥3 写时复制（CoW）语义（依赖锁定即 ≥3.0.5），任何工具改写不会污染缓存条目；
  - 测试专用环境变量 `STATLAB_NO_CACHE=1` 时完全绕过缓存直读（非行为开关，生产文档不宣传）；非法取值 stderr 中文告警并忽略。
- 路径信任声明：工具不校验文件来源（按传入路径直接读取），请勿传入不受信来源的路径

## 5. 图片输出协议（唯一约定，禁止偏离）

1. 所有图片存 `reports/plots/YYYYmmdd/`（按日期归档），文件名 = `工具名_<主列名或all>_YYYYmmdd_HHMMSS_fff.png`（多列图用 all，毫秒时间戳防覆盖、防堆积）；
2. **STATLAB_IMAGE_MODE 双轨（v1.1.0 起，进程启动时读取一次；非法取值 stderr 中文告警并回退默认 `path`）**：
   - **path（默认）**：返回 JSON 的 `__image__` 字段 = 图片绝对路径字符串，禁止 base64（防撑爆上下文）；与 v1.0.3 行为逐字段一致；
   - **content**：工具返回内容块列表 `[ImageContent(mimeType="image/png", data=<PNG base64>), TextContent(JSON)]`；TextContent 的 JSON 与 path 模式完全相同、**惟去掉 `__image__` 键**；`structuredContent` 同时为去掉该键后的完整 `{status, result, summary}` 结构（对第 6 节"禁止删改"条款的唯一显式豁免）；
   - **大图防护（钉死）**：content 模式下单张 PNG > 2.0MB 自动回退 path 形态，`summary` 末尾追加"（图片较大已回退路径模式）"，并向 stderr 记录一条 INFO 日志；
   - **风险提示（强制披露）**：content 模式图片以 base64 进入客户端上下文，存在上下文膨胀风险，仅建议支持图片渲染的交互式客户端启用；headless/自动化流水线请保持默认 path；
3. 统一封装 save_plot(fig, name)：matplotlib.use("Agg") 必须在 import pyplot 之前；中文字体 Microsoft YaHei/SimHei + unicode_minus=False（字体缺失时降级英文并在图内注明）；dpi=150，bbox_inches="tight"；两种模式的图片文件本体完全相同（确定性渲染，字节级一致可复算）；
4. agent 看图：DeepSeek Harness 用 read_image 工具，Claude Code 用 Read 工具读 `__image__` 路径；content 模式由客户端直接渲染 ImageContent。

> 注：v1.1.0 迭代任务原文中本节被引用为"SPEC 第 4 节"，对应现行编号即本节（图片输出协议），实质口径以本节为准。

## 6. auto_analysis 协议（编排层）

用户丢 CSV + 自然语言问题，自动产出 Markdown 报告。二选一（默认 A，禁止混用）：
- 方案 A（client 侧工作流，推荐）：它不是 MCP 工具，而是一份交付物文档《分析方法选择决策树 + 报告模板》+ 示例 agent 提示词；由外层 agent 按决策树调用第一层工具、套模板生成报告（见 statlab_mcp/docs/design/08_auto_analysis.md）。
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
**下限矩阵验证（v1.2.0 T5 起）**：dep_matrix CI 工作流以 `scripts/gen_lower_constraints.py`
从 dependencies 现场生成 `pkg==下限` 约束文件（fail-loud，拒绝无下限条目；产物不入库），
按 `pip install . -c constraints-lower.txt` 安装后跑全量测试与 stdio 冒烟——验证
「下限组合仍可安装、可运行」。该矩阵只覆盖**直接依赖下限**（如实命名，非全传递依赖组合）；
BLAS 线程数与锁定权威同约定置 1。

## 9. 错误码表（v1.1.0 新增；一经发布永久稳定，只增不改不复用）

格式 `E` + 四位数字。机器可读码供 agent 程序化决策：E1001/E1002/E1006/E1008/E1009 通常"改参数/改输入可重试"；E1003/E1004/E1007 通常需更换文件本身；E1005 需缩减数据规模或拆分；E1010/E1011 需换方法或补数据。语义变化只能新增码，禁止修改既有码语义或复用已废弃码。

| 码 | 语义 | 典型触发场景 |
|---|---|---|
| E1001 | 参数校验失败 | 枚举值非法（method/test/alternative 等）、数值区间非法（alpha/confidence/threshold/k/horizon/n_components 等）、必填参数组合缺失、NaN/Inf 参数、pydantic schema 层拦截（StatlabServer 转换通路同返此码） |
| E1002 | 路径非法 | 路径为空 / 含 NUL / UNC 网络路径 |
| E1003 | 文件不存在或不可访问 | 路径无此文件 |
| E1004 | 文件为空或无可读数据 | 0 字节 / 仅空行 / xlsx 损坏无法打开 |
| E1005 | 文件/数据规模超限 | >50MB、预估 >200 万行、内存预估 >500MB、JSON>20MB 解析放大、xlsx zip 炸弹、日期跨度超限、样本量超出方法适用上限（如 Shapiro>5000）、数值列数超上限 |
| E1006 | 文件格式不支持 | 扩展名不在 {csv,tsv,xlsx,json} 白名单、JSON 非表格结构 |
| E1007 | 文件编码无法识别 | csv/tsv 双编码回退均失败、JSON 非 UTF-8 |
| E1008 | 缺少必需列 | 指定列不存在于表中（含目标列之外特征全部不可用的场景） |
| E1009 | 列非数值 | 列类型不符合工具要求（含两列配对均为非数值） |
| E1010 | 样本量/有效值不足 | 有效值 < 方法下限（n<2/3、组内<2、<MIN_N）、剔除缺失后为空、全缺失列、无任何数值列、样本量低于方法下限（如 D'Agostino<8）、周期/频率不可估、时间戳不足 |
| E1011 | 分组/配对结构非法 | 组数不符（≠2 组做两两检验、单类别、多类做二分类）、类别数超上限、配对差值无变异、常量列方差 0、零方差特征、配对两组样本数不等、乘法分解遇非正值 |
| E1012 | 数据无可处理对象（无须处理） | 输入健康但不存在工具所要求的可处理对象：impute_missing 三情形（全表无缺失 / 指定列均无缺失 / 缺失仅位于非数值列）。处置指引=无需任何修复动作，可直接进行其它分析；v1.2.0 起启用 |
| E9999 | 计算失败兜底 | 拟合不收敛/完全共线等运行期计算异常、未知解析异常兜底 |

实现约定：码常量集中于 `statlab_mcp/tools/_common.py` 的 `EC` 类；业务错误以 `DataLabError(message, code)` 抛出、工具层统一 `err(e.code, str(e))` 返回；pydantic 层由 StatlabServer 转换通路注入 E1001。`tests/check_readme_claims.py` 扩展项静态核对"SPEC 本表 ↔ EC 类常量集"双向一致（见 P2-B）。
## 10. MCP resources 与 description 双轨（v1.1.0 新增）

- resources 静态枚举（不用 resource templates），数量恒 = 注册工具数 + 1：
  `statlab://spec` = 本 SPEC 全文；`statlab://tools/<工具名>/manual` = 该工具模块 docstring 全文 + 其设计文档（docs/design/NN_*.md）对应小节全文。manual 内容不受任何开关影响，永远是完整说明书。
- 文档随包分发：docs/ 位于包内 statlab_mcp/docs/，运行期一律经 importlib.resources 定位，PyPI 安装、源码仓、任意 cwd 口径一致；工具→设计文档映射见 docs/design 各文档顶部「工具索引」行。
- STATLAB_DESC_MODE 环境开关（进程启动时读取一次）：full（默认）= tools/list 的 description 为 docstring 全文，与 v1.0.3 一致；slim = 仅一句话功能摘要 + 每参数的名称/类型/必填性/取值约束原文（验收：总字节较 full 降 ≥50%，且任何参数名不得丢失）。开关只影响 tools/list 的 description，不影响工具行为、测试、docstring、manual；非法取值启动时 stderr 中文告警并回退 full。
- 客户端建议：不支持/不读 resources 的客户端保持默认 full；管理端可按需切换 slim 降低上下文占用，传参依据缺失时由外层 agent 读对应 manual 补齐。

## 11. 文件输出协议（`__output__`）

1. **产生文件的工具**（自 v1.2.0 `impute_missing` 起）在返回 JSON 顶层附加 `__output__` = 新输出文件的**绝对路径字符串**，与 `__image__`/status/result/summary 平级；禁止内联数据（防上下文爆炸），路径仅供 agent/客户端读取；
2. **不参与图片双轨**：`__output__` 为纯路径字段，由工具直接返回；`STATLAB_IMAGE_MODE=content` 的内容块改写机制只作用于含 `__image__` 的成功结果，对 `__output__` 结果原样透传（_imaging.py 不扩展）；
3. **目录约定**：一切工具产物统一入 `reports/` 下按日期归档、**均不进版本库**（.gitignore 收录）——`reports/plots/YYYYmmdd/`（图片，见第 5 节）、`reports/imputed/YYYYmmdd/`（插补结果 CSV）；产物目录执行 30 天自动清理（过期日删除，不影响任何计算结果的可复现性——统计数字永远可由原始输入重新生成）；
4. **原文件不可变**：产生输出的工具绝不修改/覆写任何输入文件；输出文件名 = `<工具名>_<原文件干名>_<语义后缀>_YYYYmmdd_HHMMSS_fff.csv`（毫秒时间戳防覆盖；干名经 Windows 保留名清洗）；
5. **CSV 写出防护**：以 utf-8-sig 编码写出；字符串单元格若以 `=` `+` `-` `@` 开头则前置 `'` 转义（防 Excel 公式注入）；剔除字段内控制字符（`\x00-\x08\x0B\x0C\x0E-\x1F`）；上述防护在 SPEC 声明，读回方需知晓首字符转义规则。

## 12. inline 数据通道与来源标注（v1.2.0）

> 信任声明（与第 4 节"路径信任声明"同构）：工具不校验 inline 数据的出处与内容授权，
> 调用方对所传数据负责。工具亦不校验文件来源——两条边界由调用方/外层 agent 把守。

### 12.1 参数协议
- 所有**接受 `file_path` 的文件型/混合工具**（28 个 require_input 型 + analysis_plan 可选源）
  获得可选 `inline_data` 参数，与 `file_path` 二选一：
  file_path 与 inline_data 同时提供或同时缺失 → `E1001`；
- JSON Schema 策略：`inline_data` 注解统一为 `list | dict | None`
  （property 级 anyOf:[array,object,null] 展开；**禁止嵌套 $ref/pydantic 子模型**
  防 MCP 客户端兼容性问题）；细粒度结构校验由运行期 `normalize_inline` 承担。

### 12.2 数据形态（运行期归一化规则）
- **records**：`[{"列名": 值, ...}, ...]` 行字典数组；列集取各行键的并集（保持首现顺序），缺失键视为缺失（null）；
- **split**：`{"header": ["列名", ...], "rows": [[值, ...], ...]}`；每行长度必须等于 header 长度；
- 形态自动识别：list → records；dict 且含 header+rows → split；其余 → E1001。
- 缺失唯一权威表示 = `null`；字符串 "NA"/""/"null" 等**不做缺失词归一**（是有内容的字符串，
  注意与 pandas.read_csv 默认 na_values 行为存在差异）；NaN/Infinity 为非法 JSON 字面量，
  仅宽容解析器（Python json）可发出，规范客户端以 null 表达缺失。

### 12.3 规模与类型上限（全部 E1005/E1001/E1004，见第 9 节）
- 行数 ≤ 10000、列数 ≤ 200、单元格总数 ≤ 50000、序列化总字节 ≤ 16MB、单个字符串单元格 ≤ 65536 字符
  （超限 E1005，提示"请落盘后改用 file_path"；单遍扫描在构造 DataFrame 前拒绝）；
- 单元格值域：str / bool / int / float / None（bool 判序先于 int）；嵌套 list/dict → E1001（参数结构非法）；
- 空数据（无行或无列）→ E1004；NaN/Inf 作为**数据值**允许进入（与文件读取口径一致，
  输出侧统一 to_jsonable 转 null，铁律 6 约束的是输出 JSON）。

### 12.4 dtype 归一规则（normalize_inline 出口契约）
- 全 null 列 → float64；int/float/(null) 混合列 → float64；含 str 的混合列 → object 保持
  （由各工具按自身口径报 E1009）；
- 等价性验收规约："inline 构造 vs 等价文件读取"的对比必须在上述 dtype 归一后进行
  （NaN-aware equals，禁止朴素 check_dtype=True 或裸 ==）。

### 12.5 来源标注 `data_source`
- 上述全部工具的 result 顶层新增 `data_source` 字段：`"file"` 或 `"inline"`
  （analysis_plan 未提供数据源时为 `null`，其 `data_aware=false` 同步表达）；纯增量字段，向后兼容；
- inline 数据不进 read_table 文件缓存（无路径可键控），每次调用重新构造，确定性不受影响；
- 实现：`_common.resolve_data(file_path, inline_data, *, require_input=True)` 单点分派
  （返回 `(df, data_source)`），禁止各工具自行解析。

### 12.6 D17 连锁 optional 化与运行期必填强校验（v1.2.0）
- 28 个文件型工具的 `file_path` 全部 optional 化（`file_path=None`）以接纳 `inline_data`；
  连锁后果：签名层面 `required` 集合清空，pydantic 不再拦截"漏传业务必填参数"；
- 等价强校验：原 schema required 的参数由工具内 `require_non_none(k=v, ...)` 在
  **运行期**逐一拒绝（`try:` 块内首行执行），漏传返回与 schema required 时代等价的
  `{status:"error", error_code:"E1001", message:"缺少必需参数: <名>"}` 中文 JSON
  ——经 MCP 通道与直接调用行为一致（C13b 红队 P0-1 修复后由 stdio 守护测试钉死）；
- 无业务必填参数的工具（describe_statistics/data_type_check/missing_report/outlier_detect/
  impute_missing/correlation_matrix/analysis_plan/power_analysis）无需强校验；
- slim 描述（§10）按工具源码扫描 `require_non_none` 集合，将运行期必填参数如实标注
  "必填（漏传将被拒绝）"，不以签名 default 误标"可选"。
