# 贡献指南（CONTRIBUTING）

欢迎贡献 statlab-mcp。本指南很短，但**每条都是这个项目的"可追责"底线**——违反会被打回。

## 环境搭建

```powershell
git clone https://github.com/good-boy4069/statlab-mcp.git
cd statlab-mcp
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt --timeout 60
$env:PYTHONUTF8 = "1"   # 每次跑命令前必设
```

依赖双轨：开发/验证一律用 `requirements.txt`（锁定权威）；不要改它来"升级依赖"（升级流程见下）。

## 提交前必过（本地一键自检）

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\ -q               # 全量
& .\.venv\Scripts\python.exe -m ruff check statlab_mcp\ tests\ # 静态
& .\.venv\Scripts\python.exe tests\smoke_stdio.py              # 协议冒烟（应 ALL-STDIO-OK）
& .\.venv\Scripts\python.exe tests\check_readme_claims.py      # README 数字/工具数防漂移
```

CI 与本地同口径（Windows/Ubuntu × 3.12/3.13：pytest + ruff + 覆盖率 ≥80% + 数字自检 + 冒烟）。

## 测试纪律（项目灵魂，不可妥协）

- **手算对照，禁止循环论证**：测试期望值必须来自手算公式 / 独立实现（如 `numpy.linalg.eigh` 对照 PCA）/ 标准库对照（`statistics.mean` 对照 describe），**禁止把被测库自己的输出当期望**。
- 数值断言用 `pytest.approx` + 显式 `abs=` 容差；确定性断言（两次运行 JSON 逐字节一致）必须覆盖随机过程工具。
- JSON 安全断言：`json.dumps(r, allow_nan=False)` 必须在每个工具测试中出现。
- 边界用例至少覆盖：空文件/单行/常量列/中文列名/重复列名/GBK/错误路径；临时文件一律用 `tmp_path` fixture，禁止写仓库目录。
- 新工具必须同步 4 件套：实现 + 测试 + `statlab_mcp/docs/design/NN_*.md`（参数表/口径/边界/验证方法）+ README 工具表与计数。

## 代码规范

- 统一协议：成功 `{status:"ok", result, summary}`；失败 `{status:"error", message}`（中文，error 禁带 result）；含图工具顶层 `__image__`（绝对路径，禁 base64）。
- docstring = agent 使用说明书（参数表/口径/示例），且与 design 文档同步——**两份都改**。
- 参数命名查 `statlab_mcp/docs/SPEC.md` 第 2 节约定表；公共逻辑一律复用 `tools/_common.py`，禁止各工具自造轮子。
- 浮点参数必须拒绝 NaN/Inf（参考 `inference_hypothesis_test.py` 的 mu0 校验）；确定性：全局 seed 42，禁 `n_jobs=-1`。
- ruff 配置见 pyproject（line-length=120），本地 `ruff check` 必须零告警。

## 发布流程（维护者）

1. `CHANGELOG.md` 记版本条目 → bump `pyproject.toml` version（只此一处版本权威）。
2. 全量自检（上文 4 连）+ `python -m build`（先在空 venv 里装 wheel 验证可跑）。
3. commit → push → **等 CI 4 job 全绿**（任何红都要修到绿再发）。
4. `git tag vX.Y.Z` → push tag → 创建 GitHub Release（body 引用 CHANGELOG 本节）。
5. PyPI 发布：`TWINE_USERNAME=__token__` + `TWINE_PASSWORD=<你的 pypi token>`（环境变量，不落盘）→ `python -m twine upload dist/*`。
6. ⚠️ **PyPI 不可删除同名版本**（只能 yank）——发布前必须确认 1-5 全部完成；发布后如发现致命问题：yank 该版本 + 立即发补丁版。
7. 更新 README 发布状态（徽章/安装段）→ 二次 commit → push（不 bump 版本）。

## 升级依赖（锁定版流程）

1. 在锁定环境 `pip install <pkg>==<新版>` 并跑全量 4 连；
2. 全部通过后同步 `requirements.txt`（pip freeze 该包行）与 `pyproject.toml` dependencies 下限；
3. 单独提交，注明升级原因与验证证据（"升级 numpy 2.6：全量 252 绿 + 冒烟过"）。

## AI 协作说明

本项目开发验收采用 **AI 代做模式**（使用者也保留随时抽检权，见 README）。任何提交需留下可复现的验证记录；禁止"补丁式"堆代码——发现既有结构问题时先重构再扩展，保持 `_common.py` 单底座、工具文件 ≤250 行、入口 server.py ≤150 行的纪律。