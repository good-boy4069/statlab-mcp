r"""tests/test_gen_lower_constraints.py —— v1.2.0 T5：下限约束生成器验收。

期望值动态取自 pyproject（tomllib 重读），不硬编码数字——生成器只是
「声明→约束文件」的忠实转换器，测它没自作主张即可。
"""
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.gen_lower_constraints import extract_lower, generate


def _pyproject_deps() -> dict[str, str]:
    with (ROOT / "pyproject.toml").open("rb") as f:
        deps = tomllib.load(f)["project"]["dependencies"]
    return {extract_lower(str(d))[0]: extract_lower(str(d))[1] for d in deps}


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
    out = tmp_path / "constraints-lower.txt"
    lines = generate(out_path=out)
    assert lines, "生成结果为空"
    expect = _pyproject_deps()
    assert len(lines) == len(expect)                      # 一条不落
    for line in lines:
        name, _, ver = line.partition("==")
        assert name in expect and ver == expect[name], line   # 下限逐条等于声明
    text = out.read_text(encoding="utf-8")
    assert text.endswith("\n") and " " not in text.replace("\n", "")


def test_script_runnable_as_module():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "gen_lower_constraints.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "直接依赖下限" in r.stdout
