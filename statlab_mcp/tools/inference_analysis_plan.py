"""analysis_plan —— 编排层 · 分析计划生成（工具 30，v1.2.0 方案 B 落地）。

把 design/08 决策树变成 100% 确定性规则工具：显式关键词表 + 列类型规则 + 表序优先级，
零 LLM、零模糊匹配；只出计划不执行（执行由外层 agent 逐步调用第一层工具）。

docstring = agent 使用说明书，与 statlab_mcp/docs/design/11_analysis_plan.md 同步维护。

参数:
    question (str): 必填，非空自然语言问题（空白/控制字符 → E1001）
    file_path (str|None): 可选数据源（与 inline_data 二选一，用于结构感知；
        双缺合法 → data_aware=false、data_source=null；双给 → E1001）
    inline_data (list|dict|None): 内联小数据（同 file_path 二选一规则）
    column_hints (dict[str,str]|None): {"列名": "数值|类别|日期"} 显式类型覆盖；
        值域非法 → E1001；引用不存在列 → 忽略并在 summary 注明

意图表（12 个，忠实转录 design/08 表格 11 行+头部功效路由；完整词表见 design/11）:
    概览/相关/类别关联/单组均值/两组比较/多组比较/预测连续/预测是否/分群/
    趋势预测/异常检测/样本量功效。多意图命中 → 按 08 表格行序取先者；
    全部未命中 → fallback 计划（数据概览三件套+如实告知），不猜测任何方法。

返回: result = {intent, data_aware, data_source, chosen_methods:[{tool, reason_code,
    matched_keywords}], tool_calls_plan:[{step, tool, params, depends_on, needs?}],
    report_template:[五章], limitations:[四条]}。
summary 模板："已生成分析计划：N 步，首选方法 X；计划由确定性规则生成，
执行请逐步调用对应工具"。

示例:
    analysis_plan("这两个门店的销量差多少是真实的", file_path="sales.csv")
    analysis_plan("帮我看看这堆数据长什么样", inline_data={"header":["v"],"rows":[[1]]})
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

from statlab_mcp.tools._common import (
    EC,
    DataLabError,
    err,
    ok,
    resolve_data,
)

# ---- 意图关键词表（忠实转录 design/08 决策树"判定线索"列+头部功效路由；
#      与 design/11 词表表格由 check_readme_claims 双向一致性检查核对）----
# (intent, reason_code, keywords, tool_chain)
KW_TABLE: list[tuple[str, str, tuple[str, ...], tuple[str, ...]]] = [
    ("overview", "R_OVERVIEW",
     ("分布", "概况", "描述", "长什么样"),
     ("describe_statistics", "data_type_check", "missing_report", "plot_histogram")),
    ("correlation", "R_CORR",
     ("相关", "关系", "一起变"),
     ("correlation_matrix", "plot_heatmap", "plot_scatter")),
    ("cat_association", "R_CAT_ASSOC",
     ("关联", "类别有没有关系"),
     ("chi_square_test",)),
    ("one_group_mean", "R_ONE_MEAN",
     ("均值是不是", "是否等于", "均值等于"),
     ("normality_test", "hypothesis_test", "effect_size")),
    ("two_groups", "R_TWO_GROUPS",
     ("谁高", "更高", "两组", "A 组比 B 组"),
     ("normality_test", "hypothesis_test", "effect_size")),
    ("multi_groups", "R_MULTI_GROUPS",
     ("三组", "分部门", "多组"),
     ("anova_test",)),
    ("pred_continuous", "R_PRED_CONT",
     ("预测", "影响收入", "影响"),
     ("linear_regression", "feature_importance")),
    ("pred_binary", "R_PRED_BIN",
     ("能不能确定", "会不会买", "会不会"),
     ("logistic_regression",)),
    ("cluster", "R_CLUSTER",
     ("分成几类", "分群", "聚类"),
     ("cluster_analysis", "pca_analysis")),
    ("trend_forecast", "R_TREND",
     ("下月", "趋势", "未来"),
     ("trend_analysis", "seasonal_decompose", "time_series_forecast")),
    ("anomaly", "R_ANOMALY",
     ("异常", "突变", "离群"),
     ("outlier_detect", "anomaly_detect")),
    ("power_sample", "R_POWER",
     ("需要多少样本", "功效", "检出"),
     ("power_analysis",)),
]

_REPORT_TEMPLATE = ("数据概览", "方法选择理由", "结果", "结论", "局限")
_LIMITATIONS = (
    "样本量以工具输出为准（<30 注明功效弱）",
    "p 值是否经多重比较校正以工具输出为准",
    "相关≠因果",
    "未做外部验证",
)
_DATE_PAT = re.compile(r"date|时间|日期|day|month|year", re.I)


def _classify_columns(df: pd.DataFrame, hints: dict[str, str] | None
                      ) -> tuple[list[str], list[str], list[str]]:
    """列类型划分（结构感知，不读内容分布）：D18 白名单语义——提供 hints 时
    以其为全量划分（未标注列不参与选列，调用方未声明的角色不猜测）；
    未提供 hints 时按 dtype/列名自动判定。"""
    numeric: list[str] = []
    categorical: list[str] = []
    dates: list[str] = []
    if hints:
        for col in df.columns:
            kind = hints.get(col)
            if kind == "数值":
                numeric.append(col)
            elif kind == "类别":
                categorical.append(col)
            elif kind == "日期":
                dates.append(col)
        return numeric, categorical, dates
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            numeric.append(col)
        elif _DATE_PAT.search(col) or pd.api.types.is_datetime64_any_dtype(df[col]):
            dates.append(col)
        else:
            categorical.append(col)
    return numeric, categorical, dates


def analysis_plan(question: str, file_path: str | None = None,
                  inline_data: list | dict | None = None,
                  column_hints: dict[str, str] | None = None) -> dict:
    """分析计划生成主入口（方案 B，确定性规则引擎）。"""
    try:
        # ---- 参数校验 ----
        if not isinstance(question, str) or question.strip() == "" or \
                re.search(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", question):
            raise DataLabError(
                "question 必须为非空的自然语言问题（拒绝空白/控制字符）", EC.PARAM)
        if column_hints is not None:
            if not isinstance(column_hints, dict):
                raise DataLabError("column_hints 必须为 {'列名': '数值|类别|日期'} 对象",
                                   EC.PARAM)
            for k, v in column_hints.items():
                if v not in ("数值", "类别", "日期"):
                    raise DataLabError(
                        f"column_hints[{k!r}] 的值仅支持 数值/类别/日期，当前为 {v!r}",
                        EC.PARAM)

        # ---- 数据源（可选；D5/D6）----
        df, data_source = resolve_data(file_path, inline_data, require_input=False)
        if data_source == "none":
            data_source = None                           # D5 三态：file/inline/null
        data_aware = data_source is not None
        if data_aware and column_hints:
            unknown = [k for k in column_hints if k not in df.columns]
            hints_note = (f"；column_hints 引用的不存在列已忽略：{unknown}" if unknown
                          else "")
        else:
            hints_note = ""

        # ---- 结构感知（仅给源时；复用 data_type_check 判定口径）----
        numeric, categorical, _dates = (None, None, None)
        if data_aware:
            numeric, categorical, _dates = _classify_columns(df, column_hints)

        # ---- 意图匹配（子串包含；多命中按表序取先）----
        q = question
        hits = [(row_idx, intent, reason_code, keywords, chain)
                for row_idx, (intent, reason_code, keywords, chain) in enumerate(KW_TABLE)
                for kw in keywords if kw in q]
        if hits:
            hits.sort(key=lambda x: x[0])
            _row_idx, intent, reason_code, _keywords, chain = hits[0]
            matched = []  # 收集所有命中行中实际命中的关键词（透明度字段）
            for _ri, _it, _rc, _kws, _ch in hits:
                for kw in _kws:
                    if kw in q:
                        matched.append(kw)
        else:
            intent, reason_code, chain = "fallback", "R_FALLBACK", ()
            matched = []

        # ---- 计划装配（D8：三件套恒为前缀；无源时用伪键占位）----
        step = 0
        plan: list[dict[str, Any]] = []

        def _add(tool: str, params: dict[str, Any], depends_on: list[int] | None = None,
                 needs: str | None = None) -> None:
            nonlocal step
            step += 1
            entry = {"step": step, "tool": tool, "params": dict(params),
                     "depends_on": depends_on or []}
            if needs:
                entry["needs"] = needs
            plan.append(entry)

        if data_aware:
            src = {"file_path": file_path} if file_path else \
                {"inline_data": "由调用方注入"}
        else:
            src = {"__needs__": "file_path_or_inline"}
        _add("describe_statistics", dict(src))
        _add("data_type_check", dict(src), depends_on=[1])
        _add("missing_report", dict(src), depends_on=[1, 2])
        base_dep = [1, 2, 3]

        chosen_methods: list[dict[str, Any]] = []
        if intent != "fallback":
            for rank, tool in enumerate(chain, start=1):
                params: dict[str, Any] = {}
                needs_note = None
                if data_aware:
                    if intent in ("two_groups", "one_group_mean") and tool == "hypothesis_test":
                        params["test"] = "independent" if intent == "two_groups" \
                            else "one_sample"
                    if intent == "two_groups" and tool in ("hypothesis_test",
                                                           "effect_size"):
                        if categorical:
                            params["group_col"] = categorical[0]
                        else:
                            needs_note = "needs_column:group_col"
                    if intent in ("two_groups", "one_group_mean", "pred_continuous") \
                            and tool in ("hypothesis_test", "effect_size",
                                         "linear_regression", "feature_importance"):
                        if numeric:
                            params.setdefault("value_col" if tool != "linear_regression"
                                              else "target", numeric[0])
                            if tool == "linear_regression":
                                params["features"] = numeric[:3]
                        else:
                            needs_note = "needs_column:value_col"
                    if intent == "pred_binary" and tool == "logistic_regression":
                        if numeric:
                            params["features"] = numeric[:3]
                        else:
                            needs_note = "needs_column:features"
                else:
                    needs_note = "file_path_or_inline"
                # needs 占位接入计划条目（design/11：类型缺失 → needs_column，不编造列名）
                _add(tool, params, depends_on=[step] if step else [],
                     needs=needs_note)
                chosen_methods.append({
                    "tool": tool, "reason_code": reason_code,
                    "matched_keywords": sorted(set(matched))[:4],
                    "rank": rank})
                if rank == 1:
                    first_tool = tool
            # 修正 depends_on：链式依赖（每个选型步骤依赖其前一个选型步骤）
            sel_entries = [e for e in plan
                           if e["tool"] in chain and e["step"] > max(base_dep, default=0)]
            for i, e in enumerate(sel_entries):
                e["depends_on"] = [base_dep[-1]] if (i == 0 and base_dep) else \
                    [sel_entries[i - 1]["step"]]
        else:
            first_tool = None
            chosen_methods = []

        result = {
            "intent": intent,
            "data_aware": data_aware,
            "data_source": data_source,
            "chosen_methods": chosen_methods,
            "tool_calls_plan": plan,
            "report_template": list(_REPORT_TEMPLATE),
            "limitations": list(_LIMITATIONS),
        }
        first_desc = f"首选方法 {first_tool}" if first_tool else "未命中方法（数据概览兜底）"
        summary = (f"已生成分析计划：{len(plan)} 步，{first_desc}；"
                   f"计划由确定性规则生成，执行请逐步调用对应工具"
                   + ("" if data_aware else "；未提供数据，纯意图路由") + hints_note)
        return ok(result, summary)
    except DataLabError as e:
        return err(e.code, str(e))
    except Exception:
        return err(EC.CALC, "计算失败，请检查数据内容与参数设置（详见服务端日志）")


def register(mcp) -> None:
    """注册到 MCPServer（mcp 2.x，工具名 = 函数名）。"""
    mcp.add_tool(analysis_plan, description=__import__("sys").modules[__name__].__doc__)
