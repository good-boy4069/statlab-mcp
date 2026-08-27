# statlab-mcp —— 统计分析 MCP Server

> **独立项目，与任何厂商的官方插件无关**（README 历史声明：与 DeepSeek Harness 无关）。
> 让 AI agent（Claude Code / Cursor / DeepSeek Harness / Codex 等）获得**真实统计学能力**：
> LLM 直接口算统计会编造数字；本项目所有统计结果都来自真实计算
> （numpy / scipy / statsmodels / scikit-learn / pmdarima），AI 只负责调用与解释，
> 第一层 27 个工具内**禁止任何 LLM 参与计算**。
>
> **安装**：`pip install statlab-mcp` 或 `uvx --refresh statlab-mcp`（详见[快速开始](#快速开始)）。

## v1.1.0 新能力（协议补课 + 性能补课 + 功效分析）

| 能力 | 说明 |
|---|---|
| **机器可读错误码** | 失败返回 `{status:"error", error_code:"E****", message}`，12 个码一经发布永久稳定（SPEC 第 9 节）；agent 按码决策"改参数重试 / 缩数据 / 换方法" |
| **MCP resources** | `statlab://spec`（协议全文）+ 27 份工具 manual（docstring + 设计文档小节全文），随 PyPI 包分发，不依赖 cwd |
| **description 双轨** | `STATLAB_DESC_MODE=slim` 把 tools/list 描述瘦身为参数摘要（-53.8%），默认 full 零变化；完整说明书经 manual 获取 |
| **图片双轨** | `STATLAB_IMAGE_MODE=content` 返回标准 ImageContent 内容块；默认 path（`__image__` 路径）零变化；单图 >2MB 自动回退防上下文爆炸 |
| **功效分析 power_analysis** | 新工具：solve_n / detect_effect / verify 三模式，支持 t 系与两比例（Cohen's h），G*Power 对标数值锚定测试 |
| **性能补课** | 冷启动延迟导入 -26%（三库不再预载）；read_table 两级键 LRU 文件缓存（SHA256 防伪造、8 条/500MB、线程安全），命中不改任何输出 |

环境变量均默认零变化（详见 [SPEC 第 10 节与第 5 节](statlab_mcp/docs/SPEC.md)、[升级指引](CHANGELOG.md#unreleased---v110开发中)）。

| CI | 文档 | PyPI |
|---|---|---|
| [![CI](https://github.com/good-boy4069/statlab-mcp/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/good-boy4069/statlab-mcp/actions/workflows/ci.yml) | [贡献指南](CONTRIBUTING.md) · [路线图](ROADMAP.md) · [变更日志](CHANGELOG.md) · [SPEC](statlab_mcp/docs/SPEC.md) | [![PyPI version](https://img.shields.io/pypi/v/statlab-mcp)](https://pypi.org/project/statlab-mcp/) |

---

## 它有什么用

装上它之后，你对 AI 说"**帮我分析这个销售数据**"，AI 不再凭空断言，而是调用 27 个真实统计工具：算描述统计、查相关、跑假设检验、功效分析、拟合回归、做聚类、预测时序、画中文图表——**每个数字都出自经过验证的统计库，可复现、可追责**。`summary` 字段给出一句中文结论，`result` 给出完整结构化数据，如：

```json
{"status": "ok", "result": {"p_value": 0.0241, "mean_diff": 5.5, "effect_size": 0.65},
 "summary": "Welch t 检验：均值差 5.5（95% CI [0.74, 10.26]），p=0.0241 <0.05 拒绝 H0……相关≠因果"}
```

## 适合谁用

| 人群 | 用法 | 收益 |
|---|---|---|
| **用 AI 写代码/做分析的人**（数据分析师、运营、产品） | 让 Claude Code / Cursor 等按需调用 | 分析结论有真实计算背书，不再担心 AI 编数字 |
| **AI Agent 开发者** | 把它当统计后端接进自己的 agent/workflow | 27 个确定性工具 + 统一协议，好集成好测试 |
| **学过统计但不想手撸代码的人** | 自然语言提问，AI 代调工具 | 假设检验/回归/时序全自动选型，附逐步解释 |
| **需要输出可追责分析报告的人** | 配合 auto_analysis 方案（决策树+模板+提示词） | 报告每个数字都标注来源工具，防幻觉 |
| 想快速给数据画图的同学 | 一组 plot_* 工具 | 中文标签图表，图上直接标统计量 |

## 能解决什么问题

| 你的问题 | 对应能力 |
|---|---|
| "这堆数据长什么样、脏不脏" | describe / data_type_check / missing_report：体检、户口本、缺勤表 |
| "哪两列有关系？是真的还是碰巧" | correlation_matrix（含 fdr_bh 多重比较校正）+ 热力图 |
| "A 组和 B 组到底有没有差" | normality_test → hypothesis_test（Welch t）→ effect_size 三连；数据非正态则用 nonparametric_test（Wilcoxon/Mann-Whitney） |
| "多组分布是否不同（非正态）" | nonparametric_test：Kruskal-Wallis + ε² 效应量 |
| "三个门店的销量差多少是真实的" | anova_test：自动 Levene→Welch→Tukey/Games-Howell 事后比较 |
| "什么影响收入？能预测吗" | linear_regression（R²/VIF/残差诊断）+ feature_importance |
| "新客户会不会买（是/否）" | logistic_regression：OR + AUC + 混淆矩阵 + 分离警告 |
| "客户能分成几类？" | cluster_analysis（质心还原原单位 + 轮廓系数 k±1 对照） |
| "下个月销量大概多少？" | trend_analysis → time_series_forecast（SARIMA 自动定阶） |
| "这串日期里哪天不对劲" | anomaly_detect（STL/差分 IQR/滚动 z-score，只报告不删数据） |
| "联系我不想看表，想看图和报告" | plot_* 五件套 + auto_analysis 报告模板 |

## 特点与突出能力

1. **确定性至上**：全部随机过程固定 seed（42）；同一文件跑两次结果**逐字节一致**（这是可追责的根基，测试里有专门断言）
2. **防幻觉设计**：第一层 27 工具零 LLM；结论文案由代码模板拼数字生成；p<0.001 统一显示"<0.001"；每个结论固定附局限声明（相关≠因果、是否校正、样本量）
3. **口径钉死并可复算**：q1/q3=linear 插值（Excel QUARTILE.INC 同口径）、偏度/峰度=scipy Fisher 口径、std=ddof=1（Excel STDEV.S）——**文档写明，测试对手算公式和标准库独立核对**（**314 个 pytest**，覆盖见 statlab_mcp/docs/；CI 自动核对本数字，漂移即红）
4. **中文全链路**：中文列名、GBK 编码自动回退、中文字体图表（无字体自动降级英文并注明）、中文错误消息带解决建议
5. **硬核安全与防护**：仅本地文件、拒绝 UNC/NUL 路径、无网络上传、>50MB/200 万行/500MB 内存三重保护、xlsx zip 炸弹与日期跨度防护、异常输出有上限截断（防止恶意输入卡死）
6. **统一的调用体验**：所有工具同构（`参数校验 → 中文报错或 result+summary`），agent 和人都能无痛上手；MCP 工具描述 = 完整 docstring（参数表/返回结构/示例），**agent 打开工具列表就是使用说明书**；**参数命名按场景统一**（见 SPEC：column=单值列 / value_col=分组与时序值列 / group_col / x_col·y_col / col_a·col_b / target·features）
7. **工程完备**：13 份设计文档（每工具参数表/边界表/JSON Schema/验证方法）+ 客户端接入配置 + GitHub Actions CI（Windows/Ubuntu × Python 3.12/3.13：pytest + ruff + 覆盖率阈值 + README 数字自检 + stdio 冒烟）+ 覆盖率 82–96% + stdio 协议冒烟 + PyPI 发布

## 快速开始

### 方式 A：PyPI 一键安装（v1.0.3 起，推荐）

```powershell
# 免检车（Python 3.12+）
pip install statlab-mcp
# 或零安装直接跑（uvx 会自动装到隔离环境）
uvx statlab-mcp
# 或 pipx 常规安装
pipx install statlab-mcp
```

安装后命令行直接有 `statlab-mcp`（= stdio 服务器），MCP 客户端配置：

```json
{
  "mcpServers": {
    "statlab-mcp": {
      "command": "statlab-mcp",
      "args": [],
      "env": {"PYTHONUTF8": "1"}
    }
  }
}
```

> pip 安装会解析"范围内最新版"依赖；生产环境想完全复现开发栈，请用方式 B 的锁定 requirements.txt。

### 方式 B：源码安装（锁定开发栈）

```powershell
# 1. 安装（Python 3.12+，仅 pip）
git clone https://github.com/good-boy4069/statlab-mcp.git
cd statlab-mcp
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt --timeout 60

# 2. 验证能跑（应输出 ALL-STDIO-OK）
$env:PYTHONUTF8="1"
.\.venv\Scripts\python.exe tests\smoke_stdio.py
```

**接入 Claude Code**（项目根 `.mcp.json`）：
```json
{
  "mcpServers": {
    "statlab-mcp": {
      "command": "C:\\path\\to\\statlab-mcp\\.venv\\Scripts\\python.exe",
      "args": ["-m", "statlab_mcp.server"],
      "cwd": "C:\\path\\to\\statlab-mcp",
      "env": {"PYTHONUTF8": "1"}
    }
  }
}
```
> 三个必须：`-m statlab_mcp.server`（不是 server.py 路径）、`cwd` 指向项目根、`PYTHONUTF8=1`。其他客户端（Cursor/VSCode/Codex/Hermes/DSH）见 `statlab_mcp/docs/clients.md`。

**第一次调用**（不接客户端也能直接命令行用）：
```powershell
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'.'); from statlab_mcp.tools.data_exploration_describe_statistics import describe_statistics; import json; print(json.dumps(describe_statistics('samples/clean.csv'), ensure_ascii=False, indent=1))"
```

**数据上的三个铁律**：① 只收 `csv/xlsx/tsv/json`，绝对路径随意给（中文/GBK/空值/非法日期全自动处理）；② 真实数据放项目目录之外；③ 每次统计先看 `summary` 的中文人话结论，再翻 `result` 的结构化数字。

## 27 个工具一览

| 组 | 工具 |
|---|---|
| 数据探查 | describe_statistics, correlation_matrix, missing_report, outlier_detect, data_type_check |
| 统计推断 | hypothesis_test, anova_test, chi_square_test, normality_test, confidence_interval, effect_size, nonparametric_test, power_analysis |
| 建模 | linear_regression, logistic_regression, cluster_analysis, pca_analysis, feature_importance |
| 时序 | time_series_forecast, seasonal_decompose, trend_analysis, anomaly_detect |
| 可视化 | plot_scatter, plot_histogram, plot_heatmap, plot_forecast, plot_box |
| 编排层 | auto_analysis（交付物：决策树文档+报告模板+agent 提示词，非 MCP 工具） |

## 核心价值与统一协议

- **数字可追责**：结果确定、可复现、可测试，同一输入两次运行结果一致（全局 seed=42）
- **结构统一**：成功 `{status:"ok", result:{...}, summary:"一句话中文结论"}`；失败 `{status:"error", error_code:"E****", message:"中文原因有效提示"}`（v1.1.0 起带机器可读错误码）
- **图片附件**：含图工具默认在返回 JSON 顶层附加 `__image__`（图片绝对路径，禁止 base64）；`STATLAB_IMAGE_MODE=content` 可切换为标准 ImageContent 内容块（SPEC 第 5 节）

## 环境准备（Windows）

1. 依赖 Python 3.12+（pyproject 声明 `requires-python >=3.12`；锁定依赖 numpy 2.5.2 的最低要求），独立虚拟环境（仅 pip，禁止 uv/poetry/conda）：
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt --timeout 60
   ```
2. 依赖双轨：`requirements.txt` 是**开发/CI 锁定权威**（可复现）；PyPI 安装走 pyproject 的**范围约束**（`pip install statlab-mcp` 会解析范围内最新版；生产建议锁定 requirements 或等价 pin）。
3. **运行前必须设置 UTF-8**（否则 stdio 用 GBK 写中文 JSON，MCP 连接直接挂）：
   ```powershell
   $env:PYTHONUTF8="1"
   ```
   server 入口文件最顶端也已写 `sys.stdout.reconfigure(encoding="utf-8")` 兜底。
4. 数据读取统一走 `read_table()` 封装：utf-8-sig 试读 → csv/tsv 失败自动换 gbk → 再失败中文报错"文件编码无法识别，请另存为 UTF-8"；格式白名单 {csv, xlsx, tsv, json}，xlsx 只读第一个 sheet。

## Docker（可选）

```powershell
docker build -t statlab-mcp:1.0.3 .
docker run --rm -i statlab-mcp:1.0.3        # stdio 走 stdin/stdout，必须有 -i
```

MCP 客户端里把 command 配成 docker 的用法（如 `docker run --rm -i statlab-mcp:1.0.3` + 数据目录挂载 `-v D:\data:/data`）。
> 说明：镜像含科学计算栈约 1-2GB；容器内已装 Noto CJK 中文字体（`ENV PYTHONUTF8=1`），中文 JSON/图表开箱即用。Dockerfile 见仓库根。

## Agent 如何看图

- DeepSeek Harness：用 `read_image` 工具读 `__image__` 返回的绝对路径
- Claude Code：用 `Read` 工具读同一路径
- 所有图片存 `reports/plots/YYYYmmdd/`（按日期归档防堆积），文件名 `工具名_<主列名或all>_YYYYmmdd_HHMMSS_fff.png`，中文字体 Microsoft YaHei/SimHei（缺失时降级英文并图内注明），dpi=150；目录可随时清理（不影响任何计算）

## 安全声明

- 仅分析**你主动提供**的本地数据文件；拒绝 UNC/NUL 路径；无任何网络上传
- **路径信任声明**：工具不校验文件来源（按你给的路径直接读取），请勿传入不受信来源的路径；真实数据请放项目目录之外
- 大数据保护：>50MB 拒绝；5-50MB 先估算行数/内存，超限拒绝；zip 炸弹与日期跨度攻击面也有硬防护

## 测试与验收

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\ -q
```
- 测试数据由 `tests/make_fixtures.py` 固定 seed 生成并入库；关键数字用独立第三方计算对照（statistics.mean / 手算期望值表），禁止循环论证
- 验收流程（2026-08-26 起为 AI 代做模式）：pytest 全绿 + 两套数据实跑核对（真实 stdout 全部留档在验收记录）→ commit + PROGRESS 登记；使用者保留随时抽检权
- 质量基线：全量 pytest 绿（当前 **314 个 pytest**）、工具模块覆盖率 ≥80%（本地实测 ~90% 区间）、ruff 全量通过、stdio 协议冒烟 ALL-STDIO-OK

## 技术注记（mcp 2.x）

依赖锁定 mcp==2.1.0：`mcp.server.fastmcp.FastMCP` 已被 `mcp.server.mcpserver.MCPServer` 取代
（API 兼容 add_tool/`tool` 装饰器，`list_tools`/`call_tool`/`run_stdio_async` 为 async）。

## 文档导航

- `statlab_mcp/docs/clients.md` —— 各客户端接入配置（Claude Code/Cursor/VSCode/Codex/Hermes/DSH）
- `statlab_mcp/docs/SPEC.md` —— 协议与统计口径（返回结构/数值协议/图片协议/行为契约）
- `statlab_mcp/docs/design/` —— 每工具的接口设计（参数表/边界行为表/JSON Schema/验证方法，agent 与二次开发者的使用说明书）
- `statlab_mcp/docs/example_report.md` —— auto_analysis 方案 A 的示例报告（防幻觉铁律示范）

## 目录结构

```
statlab_mcp/          # server.py（只注册工具+to_jsonable）+ tools/<组>_<工具>.py
statlab_mcp/docs/                  # SPEC.md（协议与统计口径）、design/（各工具接口设计文档）、clients.md（接入配置）
samples/               # 入库样例数据 + 生成脚本
tests/                 # pytest + fixtures 生成脚本
data/                  # 使用者亲手造的测试数据（gitignore，不入库）
reports/plots/         # 图片输出（gitignore，按日期归档可随时清理）
```

## License

MIT（Copyright © 2026 周翔宇）。
