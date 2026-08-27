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
EXPECTED_TOOLS = 27                                    # v1.1.0：+ power_analysis


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
    if re.search(r"\b2[56] 个", readme_text) or "25 个工具" in readme_text \
            or "26 个" in readme_text:
        errors.append("README 仍含旧工具计数残留（'25 个…'/'26 个…'；当前应为 27）")
    import statlab_mcp.server as server

    if len(server._TOOL_MODULES) != EXPECTED_TOOLS:
        errors.append(f"server 注册工具数 {len(server._TOOL_MODULES)} != 预期 {EXPECTED_TOOLS}")

    # ---- P2-B ①：README 工具总数声明机制（防旧计数残留与假自洽）----
    # 规则 A：README 中出现的每一处 "N 个工具/个真实统计工具/个确定性工具" 数字
    #         必须全部等于注册数；规则 B：至少存在一处正确声明。
    from statlab_mcp import _resources as R
    tool_names = sorted(R.tool_public_fn(m).__name__ for m in server._TOOL_MODULES)
    count_claims = [int(x) for x in re.findall(
        r"(\d+)\s*个(?:真实统计工具|确定性工具|工具)", readme_text)]
    bad_counts = sorted({n for n in count_claims if n != len(tool_names)})
    if bad_counts:
        errors.append(f"README 存在与实际不符的工具数声明 {bad_counts}"
                      f"（实际 {len(tool_names)}）")
    if len(tool_names) not in count_claims:
        errors.append(f"README 缺少工具总数声明（应含 '{len(tool_names)} 个工具' 字样）")

    # ---- P2-B ②：resources 宣称与实现一致（manual 映射覆盖全部工具，数量=工具数+1）----
    doc_keys = set(R._TOOL_DOC.keys())
    if doc_keys != set(tool_names):
        missing = sorted(set(tool_names) - doc_keys)
        extra = sorted(doc_keys - set(tool_names))
        errors.append(f"manual 映射漂移：缺 {missing}，多 {extra}")
    spec_path = ROOT / "statlab_mcp" / "docs" / "SPEC.md"
    spec_text = spec_path.read_text(encoding="utf-8")
    if "数量恒 = 注册工具数 + 1" not in spec_text:
        errors.append("SPEC 第 10 节 resources 数量口径缺失（'数量恒 = 注册工具数 + 1'）")

    # ---- P2-B ③：SPEC 错误码表 ↔ EC 常量集 双向一致（码只增不减的静态检查）----
    from statlab_mcp.tools import _common as C
    ec_values = sorted({v for k, v in vars(C.EC).items()
                        if not k.startswith("_") and isinstance(v, str)})
    if len(ec_values) != len(set(ec_values)):
        errors.append("EC 常量存在重复码值")
    spec_codes = sorted(set(re.findall(r"^\| (E\d{4}) \|", spec_text, flags=re.M)))
    if spec_codes != ec_values:
        only_spec = sorted(set(spec_codes) - set(ec_values))
        only_ec = sorted(set(ec_values) - set(spec_codes))
        errors.append(f"错误码表与代码不一致：仅 SPEC 有 {only_spec}，仅代码有 {only_ec}"
                      "（码一经发布永久稳定、只增不减；删码/改语义即红）")

    if errors:
        print("[check_readme_claims] 漂移 detected:")
        for e in errors:
            print("  -", e)
        return 1
    print(f"[check_readme_claims] OK: pytest={actual}，README 声明一致，工具数="
          f"{EXPECTED_TOOLS}，resources={len(tool_names) + 1}，错误码 {len(ec_values)} 个双向一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
