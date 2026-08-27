r"""scripts/gen_lower_constraints.py —— 从 pyproject [project].dependencies 生成下限约束文件。

用途：dep_matrix CI 用 `pip install . -c constraints-lower.txt` 验证
「依赖下限组合仍可安装、可运行」（直接依赖下限矩阵，如实命名，不夸大为全传递矩阵）。

规则：
- 每条 `pkg>=lower,<upper` 形态的规约输出一行 `pkg==lower`（下限即当前锁定版本的值）；
- 无唯一 `>=` 下限的条目一律 fail-loud（SystemExit 2，拒绝猜测）；
- 输出按 pyproject 声明顺序写入仓库根 constraints-lower.txt（.gitignore 不入库，D13）。

依赖：packaging（pip 环境自带，非项目三方依赖，不触碰 requirements.txt，铁律 8）。
用法：python scripts/gen_lower_constraints.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "constraints-lower.txt"


def load_dependencies(pyproject: Path | None = None) -> list[str]:
    """读取 [project].dependencies；缺失/为空即 fail-loud。"""
    import tomllib

    path = pyproject or (ROOT / "pyproject.toml")
    with path.open("rb") as f:
        data = tomllib.load(f)
    deps = data.get("project", {}).get("dependencies")
    if not deps or not isinstance(deps, list):
        print("[gen-lower] pyproject 未声明 [project].dependencies（fail-loud）",
              file=sys.stderr)
        raise SystemExit(2)
    return [str(d) for d in deps]


def extract_lower(spec: str) -> tuple[str, str]:
    """从单条 requirement 提取 (name, lower)；无唯一 `>=` 下限时 fail-loud。"""
    from packaging.requirements import Requirement
    from packaging.version import Version

    try:
        req = Requirement(spec)
    except Exception as e:  # InvalidRequirement 等：逐字报错，不吞
        print(f"[gen-lower] 无法解析规约 {spec!r}：{e}", file=sys.stderr)
        raise SystemExit(2) from e
    # packaging 新版迭代产生 Specifier 对象（.operator/.version），兼容旧版元组形态
    lowers = [getattr(s, "version", None) or s[1]
              for s in req.specifier
              if (getattr(s, "operator", None) or s[0]) == ">="]
    if len(lowers) != 1:
        print(f"[gen-lower] {spec!r} 缺少唯一 >= 下限（拒绝猜测）", file=sys.stderr)
        raise SystemExit(2)
    name = req.name.lower().replace("_", "-")
    return name, str(Version(lowers[0]))


def generate(out_path: Path | None = None, pyproject: Path | None = None) -> list[str]:
    """生成约束文件并返回行列表（`name==lower`，按 pyproject 顺序）。"""
    lines = [f"{n}=={v}" for n, v in
             (extract_lower(s) for s in load_dependencies(pyproject))]
    (out_path or OUT).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return lines


def main() -> int:
    lines = generate()
    print(f"[gen-lower] 写入 {OUT.name}：{len(lines)} 条直接依赖下限")
    for line in lines:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
