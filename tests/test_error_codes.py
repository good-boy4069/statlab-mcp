"""tests/test_error_codes.py —— P0-2（v1.1.0）：机器可读错误码逐码断言。

SPEC 第 9 节钉死 12 个码；本文件对每个错误码至少给 1 个真实触发路径的断言，
并统一校验失败结构 {status, error_code, message}、无 result 字段、JSON 安全
（allow_nan=False 可序列化）。所有期望值均为协议规范本身，无循环引用。
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from statlab_mcp.tools import _common as C
from statlab_mcp.tools import data_exploration_correlation_matrix as corr_mod
from statlab_mcp.tools import inference_chi_square_test as chi2_mod
from statlab_mcp.tools import inference_confidence_interval as ci_mod
from statlab_mcp.tools import inference_hypothesis_test as ht_mod

FIX = ROOT / "tests" / "fixtures"
CLEAN = str(FIX / "clean.csv")


def _assert_err(r: dict, code: str) -> None:
    """失败结构三断言：状态、机器码、中文消息；且不携带 result、可安全 JSON 化。"""
    assert r["status"] == "error", r
    assert r["error_code"] == code, r
    assert isinstance(r["message"], str) and r["message"], r
    assert "result" not in r, r
    json.dumps(r, ensure_ascii=False, allow_nan=False)   # 禁 NaN/Infinity 字面量


def test_e1001_param_enum():
    _assert_err(ht_mod.hypothesis_test(CLEAN, column="score", alternative="bogus"),
                C.EC.PARAM)


def test_e1002_path_nul_and_unc(tmp_path):
    _assert_err(ht_mod.hypothesis_test("bad\x00path", column="score"), C.EC.PATH)
    _assert_err(ht_mod.hypothesis_test(r"\\\\server\\share\\a.csv", column="score"),
                C.EC.PATH)


def test_e1003_file_missing(tmp_path):
    _assert_err(
        ht_mod.hypothesis_test(str(tmp_path / "nope.csv"), column="score"),
        C.EC.FILE_MISSING)


def test_e1004_empty_and_header_only():
    for name in ("empty.csv", "header_only.csv"):
        try:
            C.read_table(str(FIX / name))
            raised = False
        except C.DataLabError as e:
            raised = True
            assert e.code == C.EC.FILE_EMPTY, (name, e.code)
        assert raised, name


def test_e1005_scale_too_many_cols(tmp_path):
    df = pd.DataFrame({f"c{i:02d}": range(10) for i in range(21)})   # 上限 20 列
    p = tmp_path / "wide.csv"
    df.to_csv(p, index=False)
    _assert_err(corr_mod.correlation_matrix(str(p)), C.EC.SCALE)


def test_e1005_scale_mem_limit(monkeypatch):
    monkeypatch.setattr(C, "MAX_MEM_BYTES", 1)
    try:
        C.read_table(CLEAN)
        raised = False
    except C.DataLabError as e:
        raised = True
        assert e.code == C.EC.SCALE, e.code
    assert raised


def test_e1006_format_not_allowed(tmp_path):
    p = tmp_path / "x.txt"
    p.write_text("a,b\n1,2\n", encoding="utf-8")
    try:
        C.read_table(str(p))
        raised = False
    except C.DataLabError as e:
        raised = True
        assert e.code == C.EC.FORMAT, e.code
    assert raised


def test_e1007_json_encoding_gbk(tmp_path):
    # GBK 字节流（含中文）按 json 契约仅试 UTF-8：必然 UnicodeDecodeError → E1007
    p = tmp_path / "gbk.json"
    p.write_bytes('{"城市": ["北京", "上海"]}'.encode("gbk"))
    try:
        C.read_table(str(p))
        raised = False
    except C.DataLabError as e:
        raised = True
        assert e.code == C.EC.ENCODING, e.code
    assert raised


def test_e1008_column_missing():
    _assert_err(ht_mod.hypothesis_test(CLEAN, column="不存在列"), C.EC.COLUMN_MISSING)


def test_e1009_column_not_numeric():
    _assert_err(ht_mod.hypothesis_test(CLEAN, column="category"), C.EC.COLUMN_TYPE)


def test_e1010_insufficient_n(tmp_path):
    df = pd.DataFrame({"v": [1.0, 2.0]})          # CI 要求 ≥3 个有效值
    p = tmp_path / "tiny.csv"
    df.to_csv(p, index=False)
    _assert_err(ci_mod.confidence_interval(str(p), "v"), C.EC.INSUFFICIENT)


def test_e1011_paired_no_variance(tmp_path):
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0], "y": [1.0, 2.0, 3.0, 4.0]})
    p = tmp_path / "same.csv"
    df.to_csv(p, index=False)
    _assert_err(
        ht_mod.hypothesis_test(str(p), column="x", test="paired", sample2_col="y"),
        C.EC.STRUCTURE)


def test_e1011_single_category(tmp_path):
    df = pd.DataFrame({"a": ["A"] * 6, "b": ["X", "Y"] * 3})
    p = tmp_path / "onecat.csv"
    df.to_csv(p, index=False)
    _assert_err(chi2_mod.chi_square_test(str(p), "a", "b"), C.EC.STRUCTURE)


def test_e9999_fallback_default_code():
    # 单参构造 DataLabError 默认兜底码 E9999；err() 的 EC.CALC 即该码
    assert C.DataLabError("任意").code == C.EC.CALC
    assert C.err(C.EC.CALC, "计算失败")["error_code"] == "E9999"
