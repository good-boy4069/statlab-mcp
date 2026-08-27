r"""tests/test_gen_lower_constraints.py —— v1.2.0 T5：下限约束生成器验收。

期望锚：硬编码样例（test_extract_lower_basic）+ pyproject 独立解析口径
（不经被测函数，防同源循环弱断言——红队 P2-7(a) 收紧）。
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.gen_lower_constraints import extract_lower, generate


def test_extract_lower_basic():
    assert extract_lower("numpy>=2.5.2,<3") == ("numpy", "2.5.2")
    assert extract_lower("statsmodels>=0.14.6,<1") == ("statsmodels", "0.14.6")
    assert extract_lower("PyDantic>=2.13.4,<3")[0] == "pydantic"  # 名称归一小写


def test_extract_lower_fails_loud_without_lower():
    try:
        extract_lower("numpy<3")            # 只有上限，无 >= 下限
    except SystemExit as e:
        assert e.code == 2
    else:
        raise AssertionError("无下限规约未 fail-loud")


def test_extract_lower_fails_loud_on_garbage():
    try:
        extract_lower("not a requirement ~!!")
    except SystemExit as e:
        assert e.code == 2
    else:
        raise AssertionError("畸形规约未 fail-loud")


def test_generate_matches_pyproject(tmp_path):
    """红队 P2-7(a) 收紧：期望锚用独立硬编码口径（tomllib 直接解析 >= 语义），
    不再经由被测函数 extract_lower 构造期望（同源循环弱断言）。"""
    import tomllib as _tl
    out = tmp_path / "constraints-lower.txt"
    lines = generate(out_path=out)
    assert lines, "生成结果为空"
    with (ROOT / "pyproject.toml").open("rb") as f:
        raw = _tl.load(f)["project"]["dependencies"]
    expect = {}
    for d in raw:
        name, rest = str(d).split(">=", 1)
        expect[name.strip().lower().replace("_", "-")] = rest.split(",")[0].split(";")[0].strip()
    assert len(lines) == len(expect)                      # 一条不落
    for line in lines:
        name, _, ver = line.partition("==")
        assert name in expect and ver == expect[name], line   # 下限逐条等于声明
    text = out.read_text(encoding="utf-8")
    assert text.endswith("\n") and " " not in text.replace("\n", "")


def test_script_runnable_as_module(tmp_path):
    """红队 P2-7(b/c)：显式注入 PYTHONUTF8=1（Windows 默认 GBK 会让中文断言
    假红，与 test_inline_adoption 同口径）；产物输出到 tmp_path 不落仓库根。"""
    env = {**os.environ, "PYTHONUTF8": "1",
           "STATLAB_CONSTRAINTS_OUT": str(tmp_path / "constraints-lower.txt")}
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "gen_lower_constraints.py")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, cwd=str(tmp_path))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "直接依赖下限" in r.stdout
    assert (tmp_path / "constraints-lower.txt").exists()   # 产物落在指定位置
