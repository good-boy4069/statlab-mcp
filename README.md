# statlab-mcp —— 统计分析 MCP Server

> **本项目与 DeepSeek Harness 无关，是一个独立项目。**
> 让 AI agent（Claude Code / Cursor / DeepSeek Harness 等）获得真实统计学能力：
> LLM 直接做统计会编造数字；本项目所有统计结果都来自真实计算（numpy/scipy/statsmodels/scikit-learn），
> AI 只负责调用与解释，第一层 25 个工具内**禁止任何 LLM 参与计算**。

## 核心价值
- **数字可追责**：结果确定、可复现、可测试，同一输入两次运行结果一致（全局 seed=42）
- **结构统一**：成功 `{status:"ok", result:{...}, summary:"一句话中文结论"}`；失败 `{status:"error", message:"中文原因"}`
- **图片附件**：含图工具在返回 JSON 顶层附加 `__image__`（图片绝对路径，禁止 base64）

## 25 个工具一览
| 组 | 工具 |
|---|---|
| 数据探查 | describe_statistics, correlation_matrix, missing_report, outlier_detect, data_type_check |
| 统计推断 | hypothesis_test, anova_test, chi_square_test, normality_test, confidence_interval, effect_size |
| 建模 | linear_regression, logistic_regression, cluster_analysis, pca_analysis, feature_importance |
| 时序 | time_series_forecast, seasonal_decompose, trend_analysis, anomaly_detect |
| 可视化 | plot_scatter, plot_histogram, plot_heatmap, plot_forecast, plot_box |
| 编排层 | auto_analysis（交付物：决策树文档+报告模板，非 MCP 工具，方案 A） |

## 环境准备（Windows）
1. 依赖 Python 3.13+，独立虚拟环境（仅 pip，禁止 uv/poetry/conda）：
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt --timeout 60
   ```
2. requirements.txt 是依赖唯一权威来源（pyproject.toml 只写元数据）。
3. **运行前必须设置 UTF-8**（否则 stdio 用 GBK 写中文 JSON，MCP 连接直接挂）：
   ```powershell
   $env:PYTHONUTF8="1"
   ```
   server 入口文件最顶端也已写 `sys.stdout.reconfigure(encoding="utf-8")` 兜底。
4. 数据读取统一走 `read_table()` 封装：utf-8-sig 试读 → csv/tsv 失败自动换 gbk → 再失败中文报错"文件编码无法识别，请另存为 UTF-8"；格式白名单 {csv, xlsx, tsv, json}，xlsx 只读第一个 sheet。

## Agent 如何看图
- DeepSeek Harness：用 `read_image` 工具读 `__image__` 返回的绝对路径
- Claude Code：用 `Read` 工具读同一路径
- 所有图片存 `reports/plots/YYYYmmdd/`（按日期归档防堆积），文件名 `工具名_<主列名或all>_YYYYmmdd_HHMMSS_fff.png`，中文字体 Microsoft YaHei/SimHei（缺失时降级英文并图内注明），dpi=150；目录可随时清理（不影响任何计算）

## 安全声明
- 仅分析**你主动提供**的本地数据文件；拒绝 UNC 路径；无任何网络上传
- **路径信任声明**：工具不校验文件来源（按你给的路径直接读取），请勿传入不受信来源的路径；真实数据请放项目目录之外
- 大数据保护：>50MB 拒绝；5-50MB 先估算行数/内存，超限拒绝

## 测试与验收
```powershell
& .\.venv\Scripts\python.exe -m pytest tests\ -q
```
- 测试数据由 `tests/make_fixtures.py` 固定 seed 生成并入库；关键数字用独立第三方计算对照（statistics.mean / 手算期望值表），禁止循环论证
- 验收流程（2026-08-26 起为 AI 代做模式，SPEC 增补 16）：pytest 全绿 + 两套数据实跑核对（真实 stdout 全部留档在对话/验收记录）→ commit + PROGRESS 登记；使用者保留随时抽检权

## 技术注记（mcp 2.x）
依赖锁定 mcp==2.1.0：`mcp.server.fastmcp.FastMCP` 已被 `mcp.server.mcpserver.MCPServer` 取代
（API 兼容 add_tool/`tool` 装饰器，`list_tools`/`call_tool`/`run_stdio_async` 为 async）。

## 目录结构
```
statlab_mcp/          # server.py（只注册工具+to_jsonable）+ tools/<组>_<工具>.py
docs/                  # SPEC.md（协议原文）、design/（接口设计文档）
samples/               # 入库样例数据 + 生成脚本
tests/                 # pytest + fixtures 生成脚本
data/                  # 使用者亲手造的测试数据（gitignore，不入库）
reports/plots/         # 图片输出（gitignore，按日期归档可随时清理）
```

## License
MIT（Copyright © 2026 周翔宇）。