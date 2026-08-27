r"""tests/test_analysis_plan.py —— v1.2.0 T4：工具 30 analysis_plan 验收。

golden 用例的期望 intent/reason_code 由 KW_TABLE 常量程序化导入驱动——词表是
输入规约而非被测库输出，不违反铁律 3（禁循环对照）。问题文案取自 design/11 词表。
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from statlab_mcp.tools.inference_analysis_plan import (
    _LIMITATIONS,
    _REPORT_TEMPLATE,
    KW_TABLE,
    analysis_plan,
)

CSV = str(ROOT / "samples" / "clean.csv")          # 含 score/income/category/date 列

GOLDENS = [
    ("帮我描述一下这批数据的分布情况", "overview", "R_OVERVIEW", "describe_statistics"),
    ("这些列里谁和谁有关系", "correlation", "R_CORR", "correlation_matrix"),
    ("性别和购买类别有关联吗", "cat_association", "R_CAT_ASSOC", "chi_square_test"),
    ("这组数据的均值是不是等于 50", "one_group_mean", "R_ONE_MEAN", "normality_test"),
    ("A 组比 B 组高吗", "two_groups", "R_TWO_GROUPS", "normality_test"),
    ("三个门店分部门对比一下", "multi_groups", "R_MULTI_GROUPS", "anova_test"),
    ("什么因素影响收入，帮我预测一下", "pred_continuous", "R_PRED_CONT", "linear_regression"),
    ("根据这些特征能不能确定用户会不会买", "pred_binary", "R_PRED_BIN", "logistic_regression"),
    ("客户可以分成几类人", "cluster", "R_CLUSTER", "cluster_analysis"),
    ("销量未来趋势如何，下月会怎样", "trend_forecast", "R_TREND", "trend_analysis"),
    ("这串数据里有没有异常点", "anomaly", "R_ANOMALY", "outlier_detect"),
    ("要做 A/B 实验，需要多少样本才能检出差异", "power_sample", "R_POWER", "power_analysis"),
]


def _r(**kw) -> dict:
    r = analysis_plan(**kw)
    assert r["status"] == "ok", r.get("message", r)
    return r


# ---------------- 12 意图 golden（期望程序化导入） ----------------

@pytest.mark.parametrize("question,expect_intent,expect_rc,first_tool", GOLDENS)
def test_golden_intents_from_kw_table(question, expect_intent, expect_rc, first_tool):
    res = _r(question=question)["result"]
    assert res["intent"] == expect_intent
    assert res["chosen_methods"], res
    assert res["chosen_methods"][0]["reason_code"] == expect_rc
    assert res["chosen_methods"][0]["tool"] == first_tool
    assert res["tool_calls_plan"][0]["tool"] == "describe_statistics"   # D8 三件套前缀
    assert res["report_template"] == list(_REPORT_TEMPLATE)
    assert res["limitations"] == list(_LIMITATIONS)


def test_kw_table_matches_design11_doc():
    """词表↔design/11 双向一致性（同 check_readme_claims 的扩展项等价内联版）。"""
    doc = (ROOT / "statlab_mcp" / "docs" / "design" / "11_analysis_plan.md"
           ).read_text(encoding="utf-8")
    for intent, reason_code, keywords, _chain in KW_TABLE:
        assert intent in doc, intent
        assert reason_code in doc, reason_code
        for kw in keywords:
            assert kw in doc, (intent, kw)


# ---------------- fallback / 表序裁决 / 结构感知 ----------------

def test_fallback_no_method_guessing():
    r = _r(question="今天天气怎么样")
    res = r["result"]
    assert res["intent"] == "fallback"
    assert res["chosen_methods"] == []                     # 不猜任何方法
    tools_in_plan = [e["tool"] for e in res["tool_calls_plan"]]
    assert tools_in_plan == ["describe_statistics", "data_type_check", "missing_report"]
    assert res["data_aware"] is False and res["data_source"] is None   # D5 三态
    assert res["tool_calls_plan"][0]["params"].get("__needs__") == "file_path_or_inline"


def test_multi_hit_resolved_by_table_order():
    # "预测"（pred_continuous 表序 7）与"异常"（anomaly 表序 11）同时命中 → 取表序先者
    r = _r(question="预测一下这串数据是不是有异常", inline_data=[{"v": 1.0}, {"v": 2.0}])
    res = r["result"]
    assert res["intent"] == "pred_continuous"
    assert res["chosen_methods"][0]["matched_keywords"]     # 透明度：携带命中词


def test_structural_awareness_real_column_refs():
    p = str(ROOT / "samples" / "clean.csv")
    r = _r(question="A 组比 B 组谁的分数更高", file_path=p,
           column_hints={"score": "数值", "category": "类别"})
    res = r["result"]
    assert res["intent"] == "two_groups" and res["data_aware"] is True
    params = next(e for e in res["tool_calls_plan"]
                  if e["tool"] == "hypothesis_test")["params"]
    assert params["group_col"] == "category" and params["value_col"] == "score"
    assert not any("needs_column" in str(e.get("needs", "")) for e in res["tool_calls_plan"]
                   if e["tool"] == "hypothesis_test")


def test_missing_numeric_column_produces_needs_placeholder():
    """列缺失 → needs 占位（design/11：不编造列名）；数值列缺失走 needs_column。"""
    r = _r(question="A 组比 B 组谁的分数更高",
           inline_data=[{"g": "A"}, {"g": "B"}],
           column_hints={"g": "类别"})
    res = r["result"]
    assert res["intent"] == "two_groups"
    entry = next(e for e in res["tool_calls_plan"] if e["tool"] == "hypothesis_test")
    assert entry["params"].get("group_col") == "g"
    assert entry.get("needs") == "needs_column:value_col"


def test_power_intent_has_no_column_refs():
    res = _r(question="需要多少样本", inline_data=[{"v": 1.0}])["result"]
    pa_steps = [e for e in res["tool_calls_plan"] if e["tool"] == "power_analysis"]
    assert pa_steps and "group_col" not in str(pa_steps[0]["params"])


# ---------------- 错误路径 ----------------

@pytest.mark.parametrize("question", ["", "   ", "bad\x07bell", "\x1f"])
def test_bad_questions_are_e1001(question):
    r = analysis_plan(question=question)
    assert r["error_code"] == "E1001" and r["status"] == "error"


def test_column_hints_invalid_value_and_both_sources():
    r = analysis_plan(question="q", file_path=CSV,
                      column_hints={"score": "文本"})       # 值域非法
    assert r["error_code"] == "E1001"
    r2 = analysis_plan(question="q", file_path=CSV, inline_data=[{"a": 1}])  # 双给
    assert r2["error_code"] == "E1001"
    r3 = _r(question="q", file_path=CSV,
            column_hints={"不存在列": "数值"})               # 未知列忽略
    assert "不存在列已忽略" in r3["summary"]


# ---------------- 确定性与协议 ----------------

def test_deterministic_and_json_safe():
    r1 = _r(question="两组销售额谁更高", inline_data=[
        {"g": "A", "v": 10.0}, {"g": "B", "v": 12.0}])
    r2 = _r(question="两组销售额谁更高", inline_data=[
        {"g": "A", "v": 10.0}, {"g": "B", "v": 12.0}])
    assert json.dumps(r1, ensure_ascii=False, sort_keys=True, allow_nan=False) == \
        json.dumps(r2, ensure_ascii=False, sort_keys=True, allow_nan=False)
    assert r1["result"]["data_source"] == "inline"        # D5
    assert len(_LIMITATIONS) == 4                         # 四条固定局限


def test_inline_data_source_none_when_absent():
    res = _r(question="描述一下数据")["result"]
    assert res["data_source"] is None and res["data_aware"] is False
