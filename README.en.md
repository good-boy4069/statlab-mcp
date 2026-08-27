# statlab-mcp — Statistical Analysis MCP Server

[English](README.en.md) | [简体中文](README.md)

> **Independent project, not affiliated with any vendor's official plugins**
> (historical disclaimer: unrelated to DeepSeek Harness).
> Gives AI agents (Claude Code / Cursor / DeepSeek Harness / Codex / …) **real statistical capability**:
> an LLM computing statistics on its own will fabricate numbers; every statistical result in this project
> comes from real computation (numpy / scipy / statsmodels / scikit-learn / pmdarima). The AI only calls
> tools and interprets output — **no LLM participates in any of the 30 first-layer tools' computations.**
>
> **Install**: `pip install statlab-mcp` or `uvx --refresh statlab-mcp` (see [Quick Start](#quick-start)).

## What's new in v1.1.0 (protocol hardening + performance + power analysis)

| Capability | Description |
|---|---|
| **Machine-readable error codes** | Failures return `{status:"error", error_code:"E****", message}`; 12 codes, permanent once released (SPEC §9). Agents branch by code: "fix params and retry / shrink data / switch method" |
| **MCP resources** | `statlab://spec` (full protocol text) + 30 per-tool manuals (module docstring + full design-doc section; grows with tool count), shipped inside the PyPI package, cwd-independent |
| **Description dual mode** | `STATLAB_DESC_MODE=slim` slims `tools/list` descriptions to parameter digests (-53.8%); default `full` is byte-for-byte unchanged; full manuals remain available via resources |
| **Image dual mode** | `STATLAB_IMAGE_MODE=content` returns standard ImageContent blocks; default `path` (`__image__` file path) unchanged; single PNG >2MB auto-falls back to path to protect the context window |
| **Power analysis tool** | New `power_analysis`: solve_n / detect_effect / verify modes for t-based scenarios and two proportions (Cohen's h), validated against G*Power reference values |
| **Performance pass** | Lazy imports of the three heavy libs: cold start **≈ -26%**; two-tier-key LRU cache in `read_table` (SHA256 anti-spoofing, 8 entries/500MB budget, thread-safe); hits never change any output |

All environment variables default to exact v1.0.3 behavior (see [SPEC §10 and §5](statlab_mcp/docs/SPEC.md),
the [upgrade guide](CHANGELOG.md)).

| CI | Docs | PyPI |
|---|---|---|
| [![CI](https://github.com/good-boy4069/statlab-mcp/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/good-boy4069/statlab-mcp/actions/workflows/ci.yml) | [Contributing](CONTRIBUTING.md) · [Roadmap](ROADMAP.md) · [Changelog](CHANGELOG.md) · [SPEC](statlab_mcp/docs/SPEC.md) | [![PyPI version](https://img.shields.io/pypi/v/statlab-mcp)](https://pypi.org/project/statlab-mcp/) |

---

## What it does

Once installed, when you ask your AI "**analyze this sales data for me**", it stops hand-waving and calls
30 real statistical tools instead: descriptive statistics, correlation, hypothesis tests, power analysis,
regression, clustering, time-series forecasting, charts with Chinese labels — **every number comes from a
battle-tested statistics library and is reproducible and accountable**. The `summary` field carries a
one-sentence conclusion and `result` carries the complete structured data, e.g.:

```json
{"status": "ok", "result": {"p_value": 0.0241, "mean_diff": 5.5, "effect_size": 0.65},
 "summary": "Welch t-test: mean difference 5.5 (95% CI [0.74, 10.26]), p=0.0241 <0.05 → reject H0 … correlation ≠ causation"}
```

(Summaries are emitted in Chinese by design; see [Chinese-first pipeline](#highlights) below.)

## Who it's for

| Audience | How | Benefit |
|---|---|---|
| **People doing analysis with AI** (analysts, ops, PMs) | Let Claude Code / Cursor call tools as needed | Conclusions are backed by real computation — no more invented numbers |
| **AI agent developers** | Plug it in as the statistics backend of your agent/workflow | 30 deterministic tools + one uniform protocol; easy to integrate and test |
| **Statistics-literate users who don't want to write code** | Ask in natural language, the AI drives the tools | Hypothesis tests / regression / time series selected automatically with step-by-step reasoning |
| **Anyone who must produce auditable reports** | With the auto_analysis recipe (decision tree + template + prompts) | Every number in the report is tagged with its source tool — anti-hallucination by construction |
| Quick charting | The plot_* family | Charts render Chinese labels; key statistics annotated on the plot itself |

## Problems it solves

| Your question | Corresponding capability |
|---|---|
| "What does this data look like? How dirty is it?" | describe_statistics / data_type_check / missing_report: health check, type census, missing-value audit |
| "Which columns are related — really?" | correlation_matrix (with fdr_bh multiple-comparison correction) + heatmap |
| "Is group A really different from group B?" | normality_test → hypothesis_test (Welch t) → effect_size chain; for non-normal data use nonparametric_test (Wilcoxon/Mann-Whitney) |
| "Do several distributions differ (non-normal)?" | nonparametric_test: Kruskal-Wallis + ε² effect size |
| "How much of the sales gap between stores is real?" | anova_test: automatic Levene → Welch ANOVA → Tukey HSD / Games-Howell post-hoc |
| "What drives income? Can we predict it?" | linear_regression (R²/VIF/residual diagnostics) + feature_importance |
| "Will this new customer convert (yes/no)?" | logistic_regression: odds ratios + AUC + confusion matrix + separation warnings |
| "How many customer segments are there?" | cluster_analysis (centroids back-transformed to original units + silhouette comparison across k±1) |
| "Roughly what will next month's sales be?" | trend_analysis → time_series_forecast (auto-ARIMA order selection) |
| "Which day in this date series looks wrong?" | anomaly_detect (STL / differenced IQR / rolling z-score; reports only, never deletes data) |
| "Skip tables — give me charts and a report" | Five plot_* tools + the auto_analysis report template |

## Highlights

1. **Determinism first**: all randomness is seeded (42); running twice on the same file yields
   **byte-identical results** (the foundation of accountability, asserted explicitly in tests)
2. **Anti-hallucination design**: zero LLM in the 30 first-layer tools; conclusion sentences are assembled
   from code templates with real numbers; p<0.001 is uniformly displayed as "<0.001"; every conclusion
   carries fixed limitation notes (correlation ≠ causation, correction status, sample size)
3. **Pinned, recomputable conventions**: q1/q3 = linear interpolation (same convention as Excel
   QUARTILE.INC), skew/kurtosis = scipy Fisher definitions, std = ddof=1 (Excel STDEV.S) — documented,
   then verified against hand-computed formulas and independent standard-library references
   (**390 pytest tests**; CI re-checks that number automatically — drift turns the build red)
4. **Chinese-first pipeline**: Chinese column names, automatic GBK encoding fallback, Chinese-font charts
   (graceful English fallback + explicit note when fonts are missing), Chinese error messages with fixes
5. **Hardened safety**: local files only; UNC/NUL paths rejected; no network uploads; triple guard at
   >50MB files / >2M rows / >500MB memory; zip-bomb and date-span protections; anomaly outputs capped
   so malicious input can't hang the server
6. **Uniform calling experience**: every tool has the same shape (`validate params → Chinese error or
   result+summary`); MCP tool descriptions are the full docstrings (parameter table / return structure /
   examples) — **a model reading the tool list is reading the manual**; parameter names follow
   scenario-consistent conventions (column = single numeric column, value_col = grouped/time-series value
   column, group_col, x_col·y_col, col_a·col_b, target·features — see SPEC)
7. **Engineering completeness**: 13 design documents (per-tool parameter tables / boundary behavior /
   JSON Schema / verification methods) + client integration guides + GitHub Actions CI (Windows/Ubuntu ×
   Python 3.12/3.13: pytest + ruff + coverage gate + README number self-check + stdio smoke) +
   ~90% coverage on tool modules + stdio protocol smoke test + PyPI release

## Quick Start

### Option A: install from PyPI (recommended)

```bash
# One command (Python 3.12+)
pip install statlab-mcp
# Or run without installing (uvx provisions an isolated env automatically)
uvx statlab-mcp
# Or via pipx
pipx install statlab-mcp
```

After installation the `statlab-mcp` command (= stdio server) is available. MCP client configuration:

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

> pip resolves dependencies to "newest within range"; to reproduce the development stack exactly in
> production use Option B's locked requirements.txt.
>
> uvx note: refresh cached builds after upgrades with `uvx --refresh statlab-mcp`.

### Option B: from source (locked dev stack)

```powershell
# 1. Install (Python 3.12+, pip only)
git clone https://github.com/good-boy4069/statlab-mcp.git
cd statlab-mcp
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt --timeout 60

# 2. Verify (should print ALL-STDIO-OK)
$env:PYTHONUTF8="1"
.\.venv\Scripts\python.exe tests\smoke_stdio.py
```

**Wire up Claude Code** (`.mcp.json` in the repo root):
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
> Three requirements: `-m statlab_mcp.server` (not a path to server.py), `cwd` pointing at the project
> root, and `PYTHONUTF8=1`. Other clients (Cursor/VSCode/Codex/Hermes/DSH):
> [statlab_mcp/docs/clients.md](statlab_mcp/docs/clients.md).

**First call** (works from the CLI without any MCP client):
```powershell
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'.'); from statlab_mcp.tools.data_exploration_describe_statistics import describe_statistics; import json; print(json.dumps(describe_statistics('samples/clean.csv'), ensure_ascii=False, indent=1))"
```

**Three ground rules about data**: ① only `csv/xlsx/tsv/json`; absolute paths are fine (Chinese names /
GBK encodings / nulls / invalid dates handled automatically); ② keep real datasets outside the project
directory; ③ read the human-language Chinese `summary` first, then drill into the structured numbers in
`result`.

## All 30 tools

| Group | Tools |
|---|---|
| Data exploration | describe_statistics, correlation_matrix, missing_report, outlier_detect, data_type_check, impute_missing |
| Statistical inference | hypothesis_test, anova_test, chi_square_test, normality_test, confidence_interval, effect_size, nonparametric_test, power_analysis, analysis_plan |
| Modeling | linear_regression, logistic_regression, cluster_analysis, pca_analysis, feature_importance |
| Time series | time_series_forecast, seasonal_decompose, trend_analysis, anomaly_detect, backtest_forecast |
| Visualization | plot_scatter, plot_histogram, plot_heatmap, plot_forecast, plot_box |
| Orchestration layer | auto_analysis (deliverable: decision-tree doc + report template + agent prompts; not an MCP tool) |

## Core values & unified protocol

- **Accountable numbers**: deterministic, reproducible, testable — same input, same bytes every time
  (global seed=42)
- **Uniform structure**: success `{status:"ok", result:{...}, summary:"one-sentence conclusion"}`;
  failure `{status:"error", error_code:"E****", message:"actionable message"}`
  (machine-readable codes since v1.1.0)
- **Chart attachments**: image tools attach `__image__` (absolute path; base64 forbidden by default) at
  the top level of the returned JSON; `STATLAB_IMAGE_MODE=content` switches to standard ImageContent
  blocks (SPEC §5)

## Environment setup (Windows)

1. Requires Python 3.12+ (`requires-python >=3.12`, driven by locked numpy 2.5.2), dedicated virtualenv
   (pip only; no uv/poetry/conda):
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt --timeout 60
   ```
2. Dual-track dependency policy: `requirements.txt` is the **locked source of truth for development/CI**
   (reproducibility); PyPI installs use pyproject **range constraints** (`pip install statlab-mcp`
   resolves newest-in-range; production should pin against requirements.txt or equivalent).
3. **Set UTF-8 before running** (otherwise stdio writes Chinese JSON in GBK and the MCP connection dies):
   ```powershell
   $env:PYTHONUTF8="1"
   ```
   The server entry also calls `sys.stdout.reconfigure(encoding="utf-8")` as a belt-and-braces measure.
4. All reads go through the `read_table()` wrapper: try utf-8-sig → fall back to gbk for csv/tsv →
   fail with a Chinese error advising UTF-8 conversion; format whitelist {csv, xlsx, tsv, json};
   xlsx reads the first sheet only.

## Docker (optional)

```bash
docker build -t statlab-mcp:1.2.0 .
docker run --rm -i statlab-mcp:1.2.0        # stdio uses stdin/stdout: -i is required
```

In an MCP client configure the command as e.g. `docker run --rm -i statlab-mcp:1.2.0` plus a data mount
like `-v D:\data:/data`.
> Note: the image carries the scientific stack (~1–2GB); Noto CJK fonts are preinstalled with
> `ENV PYTHONUTF8=1`, so Chinese JSON/charts work out of the box. Dockerfile lives at the repo root.

## How agents view charts

- DeepSeek Harness: use the `read_image` tool on the absolute path returned in `__image__`
- Claude Code: use the `Read` tool on the same path
- All images are stored under `reports/plots/YYYYmmdd/` (daily buckets prevent pile-up), named
  `<tool>_<column-or-all>_YYYYmmdd_HHMMSS_fff.png`, rendered with Microsoft YaHei/SimHei
  (English fallback + on-chart note if fonts are missing) at dpi=150; the directory can be cleaned any
  time — no computation depends on it

## Security statement

- Only analyzes local data files you deliberately provide; UNC/NUL paths rejected; zero network upload
- **Path trust**: tools do not verify file provenance (they read whatever path you pass) — never point
  them at untrusted sources; keep real datasets outside the project directory
- Big-data protection: >50MB rejected outright; 5–50MB gets row/memory estimation with rejection above
  limits; zip bombs and date-span blowups have their own hard guards

## Tests & acceptance

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\ -q
```
- Test fixtures are generated deterministically by `tests/make_fixtures.py` and committed; key numbers
  are checked against independent references (statistics.mean / hand-computed expectation tables) —
  circular self-validation is banned
- Quality bar: full pytest green (**currently 390 tests**), tool-module coverage ≥80% (~90% locally
  measured), ruff clean on tool & test dirs (CI scope), stdio protocol smoke ALL-STDIO-OK

## Technical notes (mcp 2.x)

Pins mcp==2.1.0: `mcp.server.fastmcp.FastMCP` has been superseded by `mcp.server.mcpserver.MCPServer`
(API-compatible add_tool/`tool` decorators; `list_tools`/`call_tool`/`run_stdio_async` are async).

## Documentation map

- `statlab_mcp/docs/clients.md` — client integration configs (Claude Code/Cursor/VSCode/Codex/Hermes/DSH)
- `statlab_mcp/docs/SPEC.md` — protocol & statistical conventions (return structures, numeric protocol,
  error-code table, image protocol, runtime contract)
- `statlab_mcp/docs/design/` — per-tool interface design (parameter tables, boundary behavior, JSON
  Schema, verification methods; the manual for agents and secondary developers)
- `statlab_mcp/docs/example_report.md` — sample auto_analysis (Plan A) report demonstrating the
  anti-hallucination rules

## Repository layout

```
statlab_mcp/           # server.py (registers tools only) + tools/<group>_<tool>.py
statlab_mcp/docs/      # SPEC.md (protocol), design/ (per-tool design docs), clients.md (client configs)
samples/               # committed sample data + generator script
tests/                 # pytest suites + fixture generators
data/                  # your own test data (gitignored)
reports/plots/         # chart output (gitignored; daily buckets, safe to clean)
```

> Language note: user-facing summaries and error messages are intentionally Chinese-first (this project
> targets Chinese data workflows); the protocol itself (`status`/`result` keys, tool names, error codes)
> is fully machine-readable and language-neutral.

## License

MIT (Copyright © 2026 周翔宇 / Zhou Xiangyu).
