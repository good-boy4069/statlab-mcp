# -*- coding: utf-8 -*-
"""一次性（T3c）：按组批量 inline 化 28 个工具文件。用法：python _t3_batch.py B1
跑完自删。断言失败即整体中止（不落半成品）。"""
from pathlib import Path
import json
import re
import sys

GROUPS = {
    "B1": ["data_exploration_describe_statistics", "data_exploration_data_type_check",
           "data_exploration_missing_report", "data_exploration_impute_missing",
           "data_exploration_correlation_matrix", "data_exploration_outlier_detect"],
    "B2": ["inference_hypothesis_test", "inference_anova_test", "inference_chi_square_test",
           "inference_normality_test", "inference_confidence_interval",
           "inference_effect_size", "inference_nonparametric_test"],
    "B3": ["modeling_linear_regression", "modeling_logistic_regression",
           "modeling_cluster_analysis", "modeling_pca_analysis", "modeling_feature_importance"],
    "B4": ["timeseries_time_series_forecast", "timeseries_backtest_forecast",
           "timeseries_seasonal_decompose", "timeseries_trend_analysis",
           "timeseries_anomaly_detect"],
    "B5": ["visualization_plot_scatter", "visualization_plot_histogram",
           "visualization_plot_heatmap", "visualization_plot_forecast", "visualization_plot_box"],
}

# 模块名 -> 工具名（register 函数名，基线快照以工具名为键）
TOOL_NAME = {
    "describe_statistics": "describe_statistics",
    "data_type_check": "data_type_check",
    "missing_report": "missing_report",
    "impute_missing": "impute_missing",
    "correlation_matrix": "correlation_matrix",
    "outlier_detect": "outlier_detect",
    "hypothesis_test": "hypothesis_test",
    "anova_test": "anova_test",
    "chi_square_test": "chi_square_test",
    "normality_test": "normality_test",
    "confidence_interval": "confidence_interval",
    "effect_size": "effect_size",
    "nonparametric_test": "nonparametric_test",
    "linear_regression": "linear_regression",
    "logistic_regression": "logistic_regression",
    "cluster_analysis": "cluster_analysis",
    "pca_analysis": "pca_analysis",
    "feature_importance": "feature_importance",
    "time_series_forecast": "time_series_forecast",
    "backtest_forecast": "backtest_forecast",
    "seasonal_decompose": "seasonal_decompose",
    "trend_analysis": "trend_analysis",
    "anomaly_detect": "anomaly_detect",
    "plot_scatter": "plot_scatter",
    "plot_histogram": "plot_histogram",
    "plot_heatmap": "plot_heatmap",
    "plot_forecast": "plot_forecast",
    "plot_box": "plot_box",
}

DOC_BLOCK = (
    "\ninline 数据:\n"
    "    本工具支持可选 inline_data 参数（v1.2.0 起）：与 file_path 二选一，\n"
    "    支持 records 数组或 {\"header\": [...], \"rows\": [[...], ...]} 对象两种形态；\n"
    "    规模上限/类型域/data_source 来源标注见 statlab_mcp/docs/SPEC.md 第 12 节。\n")

group = sys.argv[1] if len(sys.argv) > 1 else ""
assert group in GROUPS, f"unknown group {group}"
tools_dir = Path(__file__).resolve().parent / "statlab_mcp" / "tools"

for mod_name in GROUPS[group]:
    fp = tools_dir / f"{mod_name}.py"
    src = fp.read_text(encoding="utf-8")
    # 防重复执行
    if "inline_data: list | dict | None = None" in src:
        print(f"[{group}] skip {mod_name} (already transformed)")
        continue
    assert "resolve_data" not in src.split("def ")[0], \
        f"{mod_name}: 已含 resolve_data 引用，拒绝重复"

    # ---- 新逻辑（D17 连锁 optional 化）：required 权威来源=v1.1.0 基线快照 ----
    import importlib
    import statlab_mcp.server as _srv_mod          # noqa: F401 触发注册（自带依赖）
    from statlab_mcp import _resources as _R

    baseline = json.loads((tools_dir.parent.parent / "tests" / "fixtures" /
                           "tools_list_full_v1_1_0.json").read_text(encoding="utf-8"))
    mod_obj = importlib.import_module(f"statlab_mcp.tools.{mod_name}")
    tool_name = _R.tool_public_fn(mod_obj).__name__
    base_entry = next(e for e in baseline if e["name"] == tool_name)
    req_params = [p for p in base_entry["inputSchema"].get("required", [])
                  if p != "file_path"]
    for pname in req_params:
        pat = re.compile(rf"\b{re.escape(pname)}:\s*([^,\n]+?)(?=[,)])")
        m_p = pat.search(src)
        assert m_p, f"{mod_name}: 找不到参数 {pname} 注解"
        if "| None =" in m_p.group(0):
            continue                                    # 已 optional 化
        src = src[:m_p.start()] + f"{pname}: {m_p.group(1)} | None = None" + \
            src[m_p.end():]

    n_fp = len(re.findall(r"file_path: str(?=[,)])", src))
    assert n_fp == 1, f"{mod_name}: file_path: str 出现 {n_fp} 次"
    # file_path 必填→可选（保持 type 定义 string，仅默认值变化=白名单③机械组成）
    src = re.sub(r"file_path: str(?=[,)])",
                 lambda mo, tail_char="": f"file_path: str | None = None", src, count=1)
    # inline_data 注入到主函数签名**闭合括号前**（避开后续必填参数的位置非法问题）
    close_pat = ") -> dict:"
    m_close = re.search(r"\) -> dict:", src)
    assert m_close and src.count(close_pat) == 1, \
        f"{mod_name}: 主函数 ') -> dict:' 闭合点不唯一"
    prev_char = src[:m_close.start()].rstrip()[-1]
    if prev_char == ",":                                  # 多行签名：前一参以逗号结尾
        insert_text = "\n                   inline_data: list | dict | None = None"
        src = (src[:m_close.start()] + insert_text + src[m_close.start():])
    else:                                                 # 单行签名：最后参数无尾逗号
        insert_pos = m_close.start()
        # 回退到最后参数名末尾：在 ')' 前补 ', inline_data...'
        src = (src[:insert_pos] + ",\n                   inline_data: list | dict | "
               "None = None" + src[insert_pos:])

    m = re.search(r"^(\s*)return ok\(([^\n]*)\)\s*$", src, flags=re.M)
    m_payload = re.search(r"^( *)(payload = ok\([^\n]*)$", src, flags=re.M)
    n_rt = len(re.findall(r"= read_table\(file_path\)", src))
    assert n_rt == 1, f"{mod_name}: read_table(file_path) 出现 {n_rt} 次"
    var = re.search(r"(\w+) = read_table\(file_path\)", src).group(1)

    injected_return = False
    m_return_var = re.search(r"^( *)(\w+) = ok\(([^\n]*)\)\s*$", src, flags=re.M)
    if m:
        indent, args = m.group(1), m.group(2)
        repl = (f"{indent}_payload = ok({args})\n"
                f'{indent}_payload["data_source"] = data_source\n'
                f"{indent}return _payload")
        src = src[:m.start()] + repl + src[m.end():]
        injected_return = True
    elif m_return_var:
        indent, var_name, args = m_return_var.group(1), m_return_var.group(2), m_return_var.group(3)
        src = (src[:m_return_var.start()]
               + f"{indent}{var_name} = ok({args})\n"
                 f"{indent}{var_name}[\"data_source\"] = data_source"
               + src[m_return_var.end():])
        injected_return = True
    assert injected_return, f"{mod_name}: 未找到可注入的成功返回点"

    src = src.replace(f"{var} = read_table(file_path)",
                      f"{var}, data_source = resolve_data(file_path, inline_data)", 1)

    # docstring 注入（首个关闭三引号前）
    close_idx = src.find('\n"""')
    assert close_idx != -1, f"{mod_name}: 未找到模块 docstring 结束标记"
    src = src[:close_idx] + DOC_BLOCK + src[close_idx:]

    # require_non_none 运行期强校验注入（D17：try 块前；主函数唯一入口）
    if req_params:
        m_try = re.search(r"^(\s*)try:", src, flags=re.M)
        assert m_try, f"{mod_name}: 未找到 try 入口"
        ind = m_try.group(1)
        call_args = ", ".join(f"{p}={p}" for p in req_params)
        inject = (f"{ind}# D17 连锁 optional 化的运行期强校验（SPEC §12.6）\n"
                  f"{ind}require_non_none({call_args})\n")
        src = (src[:m_try.start()] + inject + src[m_try.start():])

    # import 注入（ruff --fix 后续统一排序）
    def _add_resolve(mo):
        inner = mo.group("body")
        if "resolve_data" in inner:
            return mo.group(0)
        if mo.group("paren"):
            return mo.group(0).replace("(", "( EC,\n    resolve_data,", 1) \
                if inner.startswith("EC") or "EC" in inner.split(",")[0] \
                else mo.group(0)
        return mo.group(0)
    if re.search(r"import \(EC,\n\s+resolve_data|_common import .*resolve_data", src) is None:
        src = re.sub(
            r"(from statlab_mcp\.tools\._common import )(?P<paren>\()?",
            lambda mo: mo.group(1) + ("(" if mo.group("paren") else ""),
            src, count=0) if False else src
        # 直接文本级补丁：向两种形态稳妥注入
        m_single = re.search(r"^from statlab_mcp\.tools\._common import ([^\n(]+)$", src, flags=re.M)
        m_multi = re.search(r"^from statlab_mcp\.tools\._common import \(\n", src, flags=re.M)
        assert m_single or m_multi, f"{mod_name}: 找不到 _common import"
        if m_multi:
            src = src[:m_multi.end()] + "    resolve_data,\n    require_non_none,\n" + src[m_multi.end():]
        else:
            names = [x.strip() for x in m_single.group(1).split(",")]
            names.extend(["resolve_data", "require_non_none"])
            line = ("from statlab_mcp.tools._common import "
                    + ", ".join(sorted(set(names), key=lambda s: s.lower())))
            src = src[:m_single.start()] + line + src[m_single.end():]

    fp.write_text(src, encoding="utf-8")
    print(f"[{group}] transformed {mod_name}")
print("ALL-DONE", group)
