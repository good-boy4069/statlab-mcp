# statlab-mcp 规格原文（SPEC）

> 本文件收录项目提示词（v5 定稿）的附录 A-D 完整原文，是会话续接窗口与文档同步维护的基准。
> 来源：项目提示词 v5（工作文件夹 statlab-mcp-提示词-v5-定稿.md）。

---

## 附录 A：auto_analysis 协议（最后实现，交付前先出方案设计文档等确认）

auto_analysis(file_path, question)：用户丢 CSV + 自然语言问题，自动产出 Markdown 报告。二选一（默认 A，禁止混用）：
- 方案 A（client 侧工作流，推荐）：它不是 MCP 工具，而是一份交付物文档《分析方法选择决策树 + 报告模板》+ 示例 agent 提示词；由外层 agent（Claude Code 等）按决策树调用第一层工具、套模板生成报告。
- 方案 B（server 侧规则工具）：若实现为 MCP 工具，必须是 100% 确定性代码（规则决策树，可测试），输出结构化 {chosen_methods, tool_calls_plan, report_template}，不含任何 LLM 调用；"LLM 解释"只发生在 client 拿结果之后。

无论 A/B：报告固定章节（数据概览/方法选择理由/结果/结论/局限）；防幻觉铁律——报告中每个数字必须来自第一层工具返回的 JSON 并标注来源工具名，任何无来源数字禁止出现；想用的方法未实现时必须如实告知，禁止 LLM 心算替代；结论必须附固定局限声明（样本量、p 值是否经多重比较校正、相关≠因果、未做外部验证）。

---

## 附录 B：PROGRESS.md 模板

```markdown
# statlab-mcp 进度
## 里程碑（1-4 状态）
## 已完成（工具名 | 提交号 | 日期 | 验收人）
## 进行中（当前工具、当前步骤）
## 待办（按组列）
## 验收状态（每工具三条件逐项勾选）
## 数据与样例（data/ samples/ 内容说明）
## 下次会话起点（从哪继续、先跑什么命令）
```

---

## 附录 C：设计文档检查单（使用者 review 用）

每工具 6 问：
①参数完整有类型默认值？
②返回含 status/result(英文键名)/summary，且附完整 JSON Schema 字段表？
③数据来源明确？
④至少 3 种错误路径含中文提示？
⑤无任何"AI 判断数字"字样？
⑥有验证命令和"预期值来源"说明（可复算示例）？

每组 3 问：
⑦组内参数风格一致？
⑧与已确认组无功能重叠？
⑨统计方法使用条件写明？

外加使用者三大白话确认问题（AI 必须用大白话问）：
①这个工具算出来的数字，我能在 Excel 里验证吗（给一个可复算的小例子和期望值）？
②我的真实数据（中文列名、混合格式日期、缺数据）它接得住吗？
③同一个文件跑两次，结果会一样吗？

全部"有"才回复"确认"；任一条"没有/看不懂"就把编号贴回给 AI 要求重讲。

---

## 附录 D：图片输出协议（唯一约定，禁止偏离）

1. 所有图片存 reports/plots/，文件名 = 工具名_<主列名或all>_YYYYmmdd_HHMMSS.png（多列图用 all，时间戳防覆盖）；
2. 返回 JSON 的 __image__ 字段 = 图片绝对路径字符串，禁止 base64（防撑爆上下文）；
3. 统一封装 save_plot(fig, name)：matplotlib.use("Agg") 必须在 import pyplot 之前；中文字体+unicode_minus 设置见第 5 节；dpi=150，bbox_inches="tight"；
4. README 写明 agent 如何看图：DeepSeek Harness 用 read_image 工具，Claude Code 用 Read 工具。

---

## 红队裁决补充（2026 会话产物，作为规格增补生效）

以下为红队审查后由主 agent 裁决的增补规则，优先级等同附录（冲突时以本增补为准）：

1. **统计定义**（探查组批 1 设计文档强制写入）：
   - 分位数 = linear 插值（与 numpy.percentile 默认、Excel QUARTILE.INC 等价，非 QUARTILE.EXC）；验证示例 [1,2,3,4] → q1=1.75, q3=3.25
   - 偏度 = scipy.stats.skew(x, bias=False)（Fisher 样本偏度）；峰度 = scipy.stats.kurtosis(x, fisher=True, bias=False)（超额峰度，正态=0）；Excel 的 SKEW/KURT 是不同口径，验收时 Excel 只复算 mean/median/std/min/max/q1/q3
   - std 用 ddof=1（同 Excel STDEV.S）
2. **数值协议裁决**：result 内数值键一律存真实 float/int；"<0.001" 仅允许出现在 summary 中文文案；测试断言用 json.dumps(result, allow_nan=False) 不抛异常
3. **__image__ 层级**：顶层可选字段（与 status/result/summary 平级），result 内不重复
4. **验收时间线**：实现+自测绿 → AI 输出讲解并停止 → 使用者完成三亲手（亲手造 CSV/亲手改参/亲手写结论）→ 使用者确认后 AI 才 commit + PROGRESS 更新；此前不得 commit、不得标完成、不得开始下一工具
5. **read_table 三路分派**：csv/tsv → utf-8-sig → gbk → 中文报错；json → 仅 utf-8-sig，失败报"JSON 文件编码无法识别(仅支持 UTF-8)"（不做 gbk 回退，GBK 静默乱码比报错更危险）；xlsx → pd.read_excel(sheet_name=0, engine="openpyxl")，损坏时报中文错误
6. **check_file**：拒绝开头为 \\、//、\\?\、\.\ 的路径（UNC），先 os.path.abspath 归一化；>50MB 拒绝；5-50MB 用二进制流读前 1MB 数换行外推行数（>200 万行拒），xlsx 用 openpyxl read_only 流式 max_row 预检；读取后 df.memory_usage(deep=True).sum() > 500MB 拒绝
7. **权限与卫生**：第一层工具禁止裸 print()（污染 stdio JSON-RPC 流），日志走 logging → stderr
8. **to_jsonable 位置**：ok() 内部第一行执行 data = to_jsonable(data)；server 注册层返回前再兜底一次（双保险）；工具签名必须写全类型注解（mcp 2.x 对返回值校验严格）
9. **save_plot**：文件名字符清洗 re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name) + strip(" .") + 尾长截断；输出目录锚定项目根（Path(__file__).resolve()），禁止相对 cwd；字体检测用 font_manager.fontManager.ttflist 遍历匹配（findfont 默认 fallback 不报错、fc-list 是 Linux 命令）
10. **探查组设计文档交付**：拆两批——批 1：describe_statistics / data_type_check / missing_report（无图、建 schema 范式）；批 2：correlation_matrix / outlier_detect（p 值与图协议）。各挂一次 WAITING_FOR_APPROVAL
11. **correlation_matrix 细节**：p 值逐对取 scipy.stats.pearsonr（pandas corr 无 p）；fdr_bh 用 statsmodels.stats.multitest.multipletests(method="fdr_bh") 取 pvals_corrected，校正单元 k=n(n-1)/2 上三角；常量列 r=None、p=None；列数 >20 拒绝
12. **边界行为表最小 12 项**：文件不存在 / 空文件(0B，check_file 统一拒"文件为空或无可读数据") / 仅表头 / 全缺失列 / 列含空单元格 / 列不存在 / 非数值列 / 重复列名 / 中文及含空格特殊字符列名 / 非法日期(2024-02-30) / 极端值 1e9 / 常量列；n=1 时 std/q1/q3=None 不报错、n=0 报错
13. **测试独立性三级策略**：小样例手算期望值硬编码（附推导注释）为主 + statistics.mean（标准库独立）为辅 + 设计文档附 Excel 复算表供三亲手复核；numpy.corrcoef 与 scipy.pearsonr 同源不作互证
14. **fixtures 单一 seed 源**：tests/make_fixtures.py 复用 samples/make_sample_data.py 生成函数（import 方式），防 seed 漂移；专用变体单独追加
15. **依赖安装实测结论**（2026 本机）：Python 3.13.14 下 numpy 2.5.2 / pandas 3.0.5 / scipy 1.18.1 / statsmodels 0.14.6 / sklearn 1.9.0 / matplotlib 3.11.1 / pmdarima 2.1.1 / openpyxl 3.1.5 / mcp 2.1.0 / pytest 9.1.1 互操作冒烟通过（OLS/ARIMA/KMeans/read_excel 全真跑）；若 pandas 3.x 未来出现不兼容，降级路径 = pandas==2.3.*（numpy 不降），重跑冒烟并记录
16. **三亲手变更记录**（使用者 2026-08-26 决定，替代原「学生每工具三亲手」）：废除使用者亲手验收，改为 AI 代做模式——①pytest 全绿（真实输出留档）②AI 实跑两套数据（data/ + samples/）核对关键数字并把真实 stdout 贴进对话 ③commit + PROGRESS 更新（验收人仍记使用者，附"代做"注与输出可回看说明）。使用者保有随时抽检权。原因：使用者时间有限，明确授权 AI 代做；项目防污点承诺改由"独立第三方对照测试 + 真实输出留档"保证。
17. **第二轮红队修复记录**（2026-08-26 全视角审查后的增补，优先级等同附录）：
    - 图片输出归档：reports/plots/YYYYmmdd/ 子目录（防堆积、不删旧图），文件名含毫秒时间戳
    - MCP 工具描述：register 时传**模块 docstring**（description=模块.__doc__，
      含参数表/返回/示例，agent 说明书传协议层；MCPServer 原样透传无截断——复检确认）
    - 资源防护：时序预处理器重采样/聚合前日期跨度校验（预估点数 >200 万即拒绝，防内存爆炸）；
      xlsx 打开前 zip 解压体积预检（>500MB 拒绝，防压缩炸弹）；json 文件 >20MB 拒绝（解析放大防护）
    - 输出条数上限：anomaly 异常点列表截断 100 条 + truncated 标记；describe 数值列 >200 拒绝
    - 错误处理：对外统一中文文案（不泄内部异常/路径），完整堆栈走 logger（stderr）
      —— read_table 层已接 logger.exception；工具层统一文案"计算失败，请检查数据内容与参数设置（详见服务端日志）"
    - 输入校验：路径 NUL 字节拒绝；threshold 等浮点参数 isfinite 校验（拒 inf/nan）
    - README 同步：三亲手→AI 代做模式；License 姓名；路径信任声明（不校验来源，勿传不受信路径）
18. **项目更名记录**（2026-08-26，发布前）：
    - 原项目名 dsh-data-lab（包 dsh_data_lab）更名为 **statlab-mcp**（包 statlab_mcp）——
      原缩写与 DeepSeek Harness 官方简称冲突，易被误认为 DSH 官方插件；新名中立无厂商前缀；
      PyPI 占用实证通过（statlab-mcp 未占用）
    - 全量替换：代码 import / server 启动（-m statlab_mcp.server）/ 测试 / README/SPEC/design×8 /
      clients.md / pyproject（name=statlab-mcp）/ PROGRESS；残留扫描为零
    - git 历史已用 git-filter-repo 全历史重写（38 提交，零旧名残留，未推送故无外部影响）
    - 本机项目文件夹名仍为 dsh-data-lab（仅存放位置，与发布无关；.venv 依赖相对位置不建议改名）