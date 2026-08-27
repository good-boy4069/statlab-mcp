r"""scripts/gen_lower_constraints.py —— 从 pyproject [project].dependencies 生成下限约束文件。

用途：dep_matrix CI 用 `pip install . -c constraints-lower.txt` 验证
「依赖下限组合仍可安装、可运行」（直接依赖下限矩阵，如实命名，不夸大为全传递矩阵）。

规则：
- 每条 `pkg>=lower,<upper` 形态的规约输出一行 `pkg==lower`（下限即当前锁定版本的值）；
- 无唯一 `>=` 下限的条目一律 fail-loud（SystemExit 2，拒绝猜测）；
- 输出按 pyproject 声明顺序写入仓库根 constraints-lower.txt（.gitignore 不入库，D13）。

依赖：仅标准库（tomllib + re；CI 修复——packaging 在干净 setup-python 环境
不可用，见 extract_lower 注记）。
用法：python scripts/gen_lower_constraints.py [输出路径]
      （亦可用环境变量 STATLAB_CONSTRAINTS_OUT 覆盖输出位置；默认仓库根）
"""
from __future__ import annotations

import os
import re
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


_REQ_PAT = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)\s*"
    r"(?P<extras>\[[^\]]*\])?\s*"
    r">=\s*(?P<lower>[A-Za-z0-9.!+]+)\s*"
    r"(?P<rest>,.*)?$")


def extract_lower(spec: str) -> tuple[str, str]:
    """从单条 requirement 提取 (name, lower)；无唯一 `>=` 下限时 fail-loud。

    标准库实现（CI 修复：packaging 并非 pip 环境必然可用——干净 setup-python
    环境只有 pip 本体，其 vendored packaging 不对外暴露，首跑即 ModuleNotFoundError）。
    只支持本项目声明格式 `name[extras]?>=lower(,<op>ver)*`，其余形态一律拒绝猜测。
    """
    m = _REQ_PAT.match(spec)
    if not m:
        print(f"[gen-lower] {spec!r} 缺少 'name>=下限' 形态（拒绝猜测）",
              file=sys.stderr)
        raise SystemExit(2)
    name = m.group("name").lower().replace("_", "-")
    return name, m.group("lower")


def generate(out_path: Path | None = None, pyproject: Path | None = None) -> list[str]:
    """生成约束文件并返回行列表（`name==lower`，按 pyproject 顺序）。"""
    lines = [f"{n}=={v}" for n, v in
             (extract_lower(s) for s in load_dependencies(pyproject))]
    (out_path or OUT).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return lines


def main() -> int:
    # 输出路径可用环境变量覆盖（测试隔离用；默认仓库根，CI 直接消费）
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        Path(os.environ.get("STATLAB_CONSTRAINTS_OUT") or OUT)
    lines = generate(out_path=out)
    print(f"[gen-lower] 写入 {out.name}：{len(lines)} 条直接依赖下限")
    for line in lines:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
