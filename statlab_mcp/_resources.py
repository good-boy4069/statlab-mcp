"""statlab-mcp 资源层（v1.1.0 P0-1）：manual/SPEC 静态 resources + description 双轨模式。

职责（SPEC 第 10 节契约）：
1. resources 静态枚举注册：`statlab://spec`（SPEC.md 全文）与每个工具的
   `statlab://tools/<工具名>/manual`（= 该工具模块 docstring 全文 + 其设计文档对应
   小节全文），不用 resource templates；文档经 importlib.resources 从包内
   statlab_mcp/docs 定位（PyPI 安装 / 源码仓 / 任意 cwd 口径一致）。
2. STATLAB_DESC_MODE 环境开关：默认 full（tools/list description = docstring 全文，
   与 v1.0.3 一致）；slim 仅保留一句话功能摘要 + 每个参数的名称/类型/取值约束/
   必填性，只影响 tools/list 的 description，不影响任何工具行为、测试、docstring
   与 manual 内容。非法取值在进程启动时 stderr 中文告警并回退 full（铁律 9）。
"""
from __future__ import annotations

import importlib.resources
import inspect
import os
import re
import sys
from collections.abc import Callable
from types import ModuleType
from typing import Any

import statlab_mcp

DESC_MODE_ENV = "STATLAB_DESC_MODE"
_VALID_DESC_MODES = ("full", "slim")
_DEFAULT_DESC_MODE = "full"


def resolve_desc_mode(raw: str | None = None, stream: Any = None) -> str:
    """解析 description 双轨开关；非法/未设置均落回默认 full，非法时 stderr 中文告警。

    stream 仅测试注入；默认动态取 sys.stderr（保证 capsys/重定向后仍可捕获）。
    """
    value = os.environ.get(DESC_MODE_ENV) if raw is None else raw
    if value is None or value.strip() == "":
        return _DEFAULT_DESC_MODE
    if value not in _VALID_DESC_MODES:
        print(f"[statlab-mcp] 告警：环境变量 {DESC_MODE_ENV}={value!r} 非法"
              f"（仅支持 {'/'.join(_VALID_DESC_MODES)}），已回退默认值 {_DEFAULT_DESC_MODE}",
              file=stream or sys.stderr)
        return _DEFAULT_DESC_MODE
    return value


def read_doc(*parts: str) -> str:
    """包内文档定位（importlib.resources）：不依赖 cwd，wheel/sdist/源码仓同一口径。"""
    ref = importlib.resources.files(statlab_mcp)
    for part in parts:
        ref = ref / part
    return ref.read_text(encoding="utf-8")


def extract_section(doc_text: str, tool_name: str) -> str | None:
    """截取设计文档中「# … 工具名(」一级标题小节的全文（至下一个一级标题）。"""
    lines = doc_text.splitlines()
    start = None
    probe = f"{tool_name}("
    for i, line in enumerate(lines):
        if line.startswith("# ") and probe in line:
            start = i
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("# "):
            end = j
            break
    return "\n".join(lines[start:end]).strip()


# 工具名 -> 设计文档文件名（与 statlab_mcp/docs/design 顶部「工具索引」行同步维护；
# check_readme_claims 扩展项核对本表覆盖全部注册工具）
_TOOL_DOC: dict[str, str] = {
    "describe_statistics": "01_data_exploration_batch1.md",
    "data_type_check": "01_data_exploration_batch1.md",
    "missing_report": "01_data_exploration_batch1.md",
    "impute_missing": "01_data_exploration_batch1.md",
    "correlation_matrix": "02_data_exploration_batch2.md",
    "outlier_detect": "02_data_exploration_batch2.md",
    "hypothesis_test": "03_inference_batch1.md",
    "normality_test": "03_inference_batch1.md",
    "confidence_interval": "03_inference_batch1.md",
    "anova_test": "04_inference_batch2.md",
    "chi_square_test": "04_inference_batch2.md",
    "effect_size": "04_inference_batch2.md",
    "nonparametric_test": "09_inference_batch3.md",
    "power_analysis": "10_power_analysis.md",
    "analysis_plan": "11_analysis_plan.md",
    "linear_regression": "05_modeling.md",
    "logistic_regression": "05_modeling.md",
    "cluster_analysis": "05_modeling.md",
    "pca_analysis": "05_modeling.md",
    "feature_importance": "05_modeling.md",
    "time_series_forecast": "06_timeseries.md",
    "backtest_forecast": "06_timeseries.md",
    "seasonal_decompose": "06_timeseries.md",
    "trend_analysis": "06_timeseries.md",
    "anomaly_detect": "06_timeseries.md",
    "plot_scatter": "07_visualization.md",
    "plot_histogram": "07_visualization.md",
    "plot_heatmap": "07_visualization.md",
    "plot_forecast": "07_visualization.md",
    "plot_box": "07_visualization.md",
}

_PARAM_LINE = re.compile(r"^ {4}(\w+)\s*\(([^)]*)\)\s*[:：]\s*(.*)$")


def build_manual(mod: ModuleType, fn: Callable[..., Any]) -> str:
    """manual = 模块 docstring 全文 + 设计文档对应小节全文（任一缺失即启动失败，不降级）。"""
    tool_name = fn.__name__
    doc = inspect.getdoc(mod)
    if not doc:
        raise RuntimeError(f"{tool_name}: 模块 docstring 缺失，无法生成 manual")
    fname = _TOOL_DOC.get(tool_name)
    if fname is None:
        raise RuntimeError(f"{tool_name}: 设计文档映射缺失（_TOOL_DOC），无法生成 manual")
    section = extract_section(read_doc("docs", "design", fname), tool_name)
    if not section:
        raise RuntimeError(
            f"{tool_name}: 在 statlab_mcp/docs/design/{fname} 中找不到对应小节，无法生成 manual")
    return (f"{doc}\n\n---\n\n# 设计文档对应小节"
            f"（statlab_mcp/docs/design/{fname}）\n\n{section}\n")


def tool_public_fn(mod: ModuleType) -> Callable[..., Any]:
    """定位工具模块唯一公开入口函数（项目约定：除 register 与下划线私有外恰一个）。"""
    candidates = [
        obj for obj in vars(mod).values()
        if inspect.isfunction(obj) and obj.__module__ == mod.__name__
        and not obj.__name__.startswith("_") and obj.__name__ != "register"]
    if len(candidates) != 1:
        names = sorted(f.__name__ for f in candidates)
        raise RuntimeError(f"模块 {mod.__name__} 公开函数数={len(candidates)}({names})，"
                           "约定应恰为 1（工具主入口）")
    return candidates[0]


def register_resources(mcp_server: Any, modules: list[ModuleType]) -> int:
    """静态枚举注册：statlab://spec + 每工具 manual；返回资源总数（= 工具数 + 1）。"""
    from mcp.server.mcpserver.resources import TextResource

    spec_text = read_doc("docs", "SPEC.md")
    if not spec_text.strip():
        raise RuntimeError("SPEC.md 为空，statlab://spec 拒绝注册空内容")
    mcp_server.add_resource(TextResource(
        uri="statlab://spec",
        name="SPEC 协议与统计口径全文",
        description=("statlab-mcp 唯一协议权威文档：统一返回结构、错误码表、统计口径、"
                     "图片协议、运行时行为契约"),
        mime_type="text/markdown",
        text=spec_text))
    count = 1
    for mod in modules:
        fn = tool_public_fn(mod)
        tool_name = fn.__name__
        mcp_server.add_resource(TextResource(
            uri=f"statlab://tools/{tool_name}/manual",
            name=f"{tool_name} 使用手册（docstring + 设计文档小节全文）",
            description=f"工具 {tool_name} 的完整使用说明书；description 瘦身(slim 模式)时的完整依据",
            mime_type="text/markdown",
            text=build_manual(mod, fn)))
        count += 1
    return count


def make_slim_description(fn: Callable[..., Any], full_doc: str) -> str:
    """构造 slim 版 description：一句话摘要 + 每参数名称/类型/必填性/取值约束。

    规则（提示词钉死）：不得丢失任何参数签名与取值约束——参数行的中文说明原文保留
    （合法取值/区间都在其中）；仅删除长示例、边界叙述与统计定义等大段文字。
    """
    summary = (inspect.getdoc(fn) or full_doc).splitlines()[0].strip()
    constricted: dict[str, tuple[str, str]] = {}
    in_params_block = False
    for line in full_doc.splitlines():
        if re.match(r"^参数\s*[:：]\s*$", line):
            in_params_block = True
            continue
        if in_params_block and (line and not line.startswith(" ")):
            in_params_block = False          # 进入下一顶级段落（返回:/示例: 等）
        m = _PARAM_LINE.match(line)
        if m:
            constricted[m.group(1)] = (m.group(2).strip(), m.group(3).strip())
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):          # C/内建无签名时兜底只给摘要
        sig = None
    out = [summary, "", "## 参数"]
    if sig:
        for pname, param in sig.parameters.items():
            ptype, pdesc = constricted.get(pname, ("", ""))
            anno = ptype or (str(param.annotation) if param.annotation is not
                             inspect.Parameter.empty else "Any")
            required = param.default is inspect.Parameter.empty
            req_txt = "必填" if required else f"可选，默认 {param.default!r}"
            out.append(f"- {pname} ({anno})｜{req_txt}" + (f"｜{pdesc}" if pdesc else ""))
    out.append("")
    out.append(f"完整说明书见 resource: statlab://tools/{fn.__name__}/manual "
               "（含返回结构与边界语义）")
    return "\n".join(out)
