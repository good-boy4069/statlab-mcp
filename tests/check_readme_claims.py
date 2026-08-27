"""tests/check_readme_claims.py —— README（中英）数字声明与实现的自洽检查。

v1.0.3：pytest 数 / 工具数 / 旧计数残留；v1.1.0：resources 口径、SPEC↔EC 错误码双向一致；
v1.2.0 C1：**英文 README 数字正则防线**（tools/tests/codes patterns，期望值一律动态取自
实现——杜绝静态期望被篡改绕过）；篡改任何数字即 CI 红。
v1.2.0 C11：EXPECTED_TOOLS=30（+backtest_forecast +analysis_plan）。
（历史注记：本文件与 README.en.md 曾在 C1/C2 提交中被写入事故清空致门禁假绿，
C11 从 19b3c2c/f66970b 恢复并重放增量——D19。）

用法：python tests/check_readme_claims.py（退出码 0=自洽；非 0=漂移）
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

README = ROOT / "README.md"
README_EN = ROOT / "README.en.md"
SPEC = ROOT / "statlab_mcp" / "docs" / "SPEC.md"
EXPECTED_TOOLS = 30                                    # v1.2.0 T1+T2+T4：+impute/backtest/analysis_plan
BASELINE_V1_1_0_TOOLS = 27                             # 已发布基线（工具数只增不减的锚）
_ADDED_SINCE_V1_1_0 = {"impute_missing", "backtest_forecast",
                       "analysis_plan"}                # v1.1.0 基线已含 power_analysis


def _collect_test_count() -> int:
    import subprocess

    out = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
        errors="replace",
    ).stdout
    m = re.search(r"(\d+) tests? collected", out)
    if not m:
        raise SystemExit(f"[check_readme_claims] 无法从 pytest 收集输出解析测试数：\n{out[-2000:]}")
    return int(m.group(1))


def main() -> int:
    import statlab_mcp.server as server
    from statlab_mcp.tools import _common as C

    n_tools = len(server._TOOL_MODULES)
    actual = _collect_test_count()
    readme_text = README.read_text(encoding="utf-8")
    en_text = README_EN.read_text(encoding="utf-8") if README_EN.exists() else ""
    spec_text = SPEC.read_text(encoding="utf-8")

    ec_values = sorted({v for k, v in vars(C.EC).items()
                        if not k.startswith("_") and isinstance(v, str)})
    expect = {
        "tools": n_tools,
        "tests": actual,
        "codes": len(ec_values),
        "resources": n_tools + 1,
    }

    errors: list[str] = []

    # ---- 中文 README ----
    count_claims_cn = [int(x) for x in re.findall(
        r"(\d+)\s*个(?:真实统计工具|确定性工具|工具)", readme_text)]
    bad_cn = sorted({n for n in count_claims_cn if n != n_tools})
    if bad_cn:
        errors.append(f"README 存在与实际不符的工具数声明 {bad_cn}（实际 {n_tools}）")
    if n_tools not in count_claims_cn:
        errors.append("中文 README 缺少工具总数声明")
    claims = [int(x) for x in re.findall(r"\*\*(\d+)\s*个 pytest\*\*", readme_text)]
    if not claims:
        errors.append("中文 README 未找到 '**N 个 pytest**' 声明")
    for n in claims:
        if n != actual:
            errors.append(f"README 声明 {n} 个 pytest，实际 {actual} 个")
    legacy = re.findall(r"\b2[5-9]\s*个(?:真实统计工具|确定性工具|工具)",
                        readme_text)
    for m in set(legacy):
        if not m.startswith(str(n_tools)):
            errors.append(f"中文 README 残留旧工具数声明：{m}")

    # ---- 英文 README（v1.2.0 C1 首建；期望值动态，无静态数字）----
    en_dynamic = [
        (r"\*\*(\d+) pytest tests?\*\*", expect["tests"], "pytest tests"),
        (r"currently (\d+) tests", expect["tests"], "currently N tests"),
        (r"(\d+) deterministic tools", expect["tools"], "deterministic tools"),
        (r"(\d+) real statistical tools", expect["tools"], "real statistical tools"),
        (r"(?:all|All) (\d+) (?:first-layer )?tools", expect["tools"], "N tools 总声明"),
        (r"(\d+) permanent codes? once released", expect["codes"], "permanent codes"),
        (r"expected: (\d+) tools", expect["tools"], "smoke-style expected tools"),
    ]
    for pat, want, label in en_dynamic:
        found = [int(x) for x in re.findall(pat, en_text)]
        bad = [f for f in found if f != want]
        if bad:
            errors.append(f"README.en 数字与实现不符[{label}]：{bad} ≠ {want}")
    # 工具总数至少一处正确声明（防整段删除式篡改）
    en_tool_decls = [int(x) for x in re.findall(
        r"\b(\d+) (?:deterministic |real statistical )?tools\b", en_text)]
    if en_text and n_tools not in en_tool_decls:
        errors.append("README.en 缺少正确的工具总数声明")

    # ---- server 注册数 vs 预期（含只增不减锚）----
    if n_tools != EXPECTED_TOOLS:
        errors.append(f"server 注册工具数 {n_tools} != 预期 {EXPECTED_TOOLS}")
    baseline_kept = n_tools - len(_ADDED_SINCE_V1_1_0)
    if baseline_kept != BASELINE_V1_1_0_TOOLS:
        errors.append(f"v1.1.0 基线工具应保留 {BASELINE_V1_1_0_TOOLS} 个，实得 {baseline_kept}"
                      f"（新增集合 {_ADDED_SINCE_V1_1_0}）")

    # ---- SPEC ↔ EC 双向一致（码只增不减）----
    spec_codes = sorted(set(re.findall(r"^\| (E\d{4}) \|", spec_text, flags=re.M)))
    if spec_codes != ec_values:
        only_spec = sorted(set(spec_codes) - set(ec_values))
        only_ec = sorted(set(ec_values) - set(spec_codes))
        errors.append(f"错误码表与代码不一致：仅 SPEC 有 {only_spec}，仅代码有 {only_ec}")

    if "数量恒 = 注册工具数 + 1" not in spec_text:
        errors.append("SPEC 第 10 节 resources 数量口径缺失")

    if errors:
        print("[check_readme_claims] 漂移 detected:")
        for e in errors:
            print("  -", e)
        return 1
    print(f"[check_readme_claims] OK: pytest={actual}，中英 README 声明一致，"
          f"工具数={expect['tools']}，资源数={expect['resources']}，错误码 {len(ec_values)} 个双向一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
