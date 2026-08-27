# -*- coding: utf-8 -*-
"""一次性（T3c）：按组批量 inline 化 28 个工具文件。用法：python _t3_batch.py B1
跑完自删。断言失败即整体中止（不落半成品）。"""
from pathlib import Path
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
            src = src[:m_multi.end()] + "    resolve_data,\n" + src[m_multi.end():]
        else:
            names = [x.strip() for x in m_single.group(1).split(",")]
            names.append("resolve_data")
            line = ("from statlab_mcp.tools._common import "
                    + ", ".join(sorted(set(names), key=lambda s: s.lower())))
            src = src[:m_single.start()] + line + src[m_single.end():]

    fp.write_text(src, encoding="utf-8")
    print(f"[{group}] transformed {mod_name}")
print("ALL-DONE", group)
