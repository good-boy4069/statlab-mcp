"""tests/check_readme_claims.py —— README 数字声明与实现的自洽检查（v1.0.3 起 CI 强制）。

背景：README 中"测试数量""工具数量"曾因手工维护在一日内漂移（223→233→240）。
本脚本在 CI 中运行：任何漂移都让流水线变红，根治文档-实现脱节。

检查点：
1. README 中"**N 个 pytest**"（N 为数字）必须等于 pytest --collect-only 实际计数；
2. README 不得再出现"25 个"字样（工具数 25→26 后禁止旧计数残留，
   覆盖"25 个真实统计工具/25 个确定性工具/第一层 25 个工具/25 个工具一览"等全部写法）；
3. 注册工具数 = 26（以 server 的 _TOOL_MODULES 为准），并在 docstring 头注明。

用法：python tests/check_readme_claims.py（退出码 0=自洽；非 0=漂移）
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

README = ROOT / "README.md"
EXPECTED_TOOLS = 26


def _collect_test_count() -> int:
    import subprocess

    out = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
        errors="replace",
    ).stdout
    # 形如 "240 tests collected"（中英文环境均如此）；失败时（含收集错误）计数缺失
    m = re.search(r"(\d+) tests? collected", out)
    if not m:
        raise SystemExit(f"[check_readme_claims] 无法从 pytest 收集输出解析测试数：\n{out[-2000:]}")
    return int(m.group(1))


def _readme_test_claims() -> list[int]:
    text = README.read_text(encoding="utf-8")
    return [int(x) for x in re.findall(r"\*\*(\d+)\s*个 pytest\*\*", text)]


def main() -> int:
    actual = _collect_test_count()
    claims = _readme_test_claims()
    errors: list[str] = []
    if not claims:
        errors.append("README 未找到 '**N 个 pytest**' 声明（请补回，格式 `**240 个 pytest**`）")
    for n in claims:
        if n != actual:
            errors.append(f"README 声明 {n} 个 pytest，实际 {actual} 个")
    readme_text = README.read_text(encoding="utf-8")
    if "25 个" in readme_text:
        errors.append("README 仍含旧工具计数 '25 个'（工具数已为 26，请全量更新）")
    import statlab_mcp.server as server

    if len(server._TOOL_MODULES) != EXPECTED_TOOLS:
        errors.append(f"server 注册工具数 {len(server._TOOL_MODULES)} != 预期 {EXPECTED_TOOLS}")
    if errors:
        print("[check_readme_claims] 漂移 detected:")
        for e in errors:
            print("  -", e)
        return 1
    print(f"[check_readme_claims] OK: pytest={actual}，README 声明一致，工具数={EXPECTED_TOOLS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
