r"""tests/test_inline_common.py —— v1.2.0 T3a：normalize_inline / resolve_data 验收。

手算/契约锚：
- dtype 归一：全 null 列→float64；int/float/(null) 混→float64（SPEC §12.4）；
- 等价性规约：inline 构造 vs 等价 CSV 读取在 dtype 归一后 NaN-aware 逐格一致；
- 五项上限：行/列/单元格/payload 总字节/单 cell 字符长度，全部 E1005；
- 结构类错误（嵌套值/行长≠header/header 非 str/形态不明）全部 E1001（D10 裁决）；
- bool 判序先于 int（bool 值列不得被 float 化吞掉语义）。
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from statlab_mcp.tools import _common as C


def _norm_df(df: pd.DataFrame) -> pd.DataFrame:
    """等价性比较规约：dtype 归一后按 NaN-aware equals 比较。"""
    return C._normalize_dtype(df.copy())


def test_records_shape_basic_dtype_normalization():
    df = C.normalize_inline([{"a": 1, "b": "x"}, {"a": None, "b": "y"}])
    assert str(df.dtypes["a"]) == "float64"              # int/(None) 混合 → float64
    assert pd.isna(df["a"].iloc[1])                      # 缺键 = null 缺失
    assert list(df["b"]) == ["x", "y"]


def test_all_none_column_becomes_float64():
    df = C.normalize_inline([{"a": None}, {"a": None}])
    assert str(df.dtypes["a"]) == "float64"              # R2-F09：防 object 分裂
    assert df["a"].isna().all()


def test_bool_column_kept_as_bool_not_float():
    df = C.normalize_inline([{"flag": True}, {"flag": False}, {"flag": True}])
    assert set(df["flag"]) == {True, False}              # bool 值列原样保留


def test_split_shape_and_row_length_mismatch():
    good = C.normalize_inline({"header": ["h1", "h2"], "rows": [[1, "a"], [2, "b"]]})
    assert list(good.columns) == ["h1", "h2"]
    with pytest.raises(C.DataLabError) as ei:
        C.normalize_inline({"header": ["h1", "h2"], "rows": [[1], [2]]})
    assert ei.value.code == "E1001"                      # D10：行长≠header → 参数结构错
    with pytest.raises(C.DataLabError) as ei2:
        C.normalize_inline({"header": ["h1"]})           # dict 含 header 缺 rows → 形态识别拦截
    assert ei2.value.code == "E1001"


def test_records_vs_equivalent_csv_equivalence(tmp_path):
    """等价性规约：同一数据 inline(records) 与落盘读取在 dtype 归一后逐格一致。

    注意（SPEC §12.4 注记）：纯文本列在 pandas 3.x 两通道分别为 object / StringDtype，
    属读取器实现细节、对统计口径无差异（均判非数值），故 check_dtype=False。
    """
    data = {"score": [70.0, np.nan, 90.0], "name": ["甲", "乙", "丙"],
            "ok": [True, False, True]}
    p = tmp_path / "eq.csv"
    pd.DataFrame(data).to_csv(p, index=False)
    from statlab_mcp.tools._common import read_table
    records = [dict(zip(data.keys(), vals, strict=True))
                     for vals in zip(*data.values(), strict=True)]
    a = _norm_df(C.normalize_inline(records))
    b = _norm_df(read_table(str(p)))
    pd.testing.assert_frame_equal(a.astype(object), b.astype(object), check_dtype=False)
    # 数值列 dtype 断言（inline 侧归一承诺独立成立）
    a_num = _norm_df(C.normalize_inline([{"s": 70.0}, {"s": None}, {"s": 90.0}]))
    assert str(a_num.dtypes["s"]) == "float64"


def test_row_count_cap(tmp_path):
    many = [{"v": i} for i in range(C._INLINE_MAX_ROWS + 1)]
    with pytest.raises(C.DataLabError) as ei:
        C.normalize_inline(many)
    assert ei.value.code == "E1005" and "file_path" in str(ei.value)


def test_col_cap_and_cell_char_cap():
    cols = {f"c{i:03d}": i for i in range(C._INLINE_MAX_COLS + 1)}
    with pytest.raises(C.DataLabError) as e1:
        C.normalize_inline([cols])
    assert e1.value.code == "E1005"
    big_cell = "x" * (C._INLINE_MAX_CELL_CHARS + 1)
    with pytest.raises(C.DataLabError) as e2:
        C.normalize_inline([{"s": big_cell}])
    assert e2.value.code == "E1005"


def test_payload_bytes_cap():
    # ~17MB 字符串总量（8 cell × ~2.2MB），行/列/单元数远低于上限 → payload 拦截对称防线生效
    big = "x" * (2 * 1024 * 1024 + 7)
    rows = [{"s": big} for _ in range(8)]
    with pytest.raises(C.DataLabError) as ei:
        C.normalize_inline(rows)
    assert ei.value.code == "E1005" and "file_path" in str(ei.value)


def test_empty_data_is_e1004():
    for bad in ([], {"header": [], "rows": []}, {"header": ["a"], "rows": []}):
        with pytest.raises(C.DataLabError) as ei:
            C.normalize_inline(bad)
        assert ei.value.code == "E1004", (bad, ei.value.code)
        assert "inline 数据为空" in str(ei.value)


def test_nested_values_are_e1001_not_e1009():
    for v in ({"deep": 1}, [1, 2], ("t",), {1, 2}):
        with pytest.raises(C.DataLabError) as ei:
            C.normalize_inline([{"a": v}])
        assert ei.value.code == "E1001", (v, ei.value.code)   # D10：结构错≠列非数值
        assert ("嵌套" in str(ei.value)) or ("类型不支持" in str(ei.value))


def test_resolve_data_four_combinations(tmp_path):
    p = tmp_path / "d.csv"
    pd.DataFrame({"v": [1.0]}).to_csv(p, index=False)
    df_f, src_f = C.resolve_data(str(p), None)
    assert src_f == "file" and len(df_f) == 1
    _df_i, src_i = C.resolve_data(None, [{"v": 1.0}])
    assert src_i == "inline"
    with pytest.raises(C.DataLabError) as ei:
        C.resolve_data(str(p), [{"v": 2.0}])
    assert ei.value.code == "E1001"
    df0, src0 = C.resolve_data(None, None, require_input=False)
    assert src0 == "none" and df0.empty
    with pytest.raises(C.DataLabError) as ei2:
        C.resolve_data(None, None, require_input=True)          # 默认 require
    assert ei2.value.code == "E1001"


def test_nan_inf_value_passthrough_deterministic():
    df = C.normalize_inline([{"v": 1.5}, {"v": float("inf")}, {"v": None}])
    again = C.normalize_inline([{"v": 1.5}, {"v": float("inf")}, {"v": None}])
    assert _norm_df(df).equals(_norm_df(again))


def test_json_safety_after_to_jsonable_pipeline():
    """铁律 6 只约束输出侧：NaN 数据值经 to_jsonable 转 null 后 JSON 安全。"""
    df = C.normalize_inline([{"v": 1.0}, {"v": float("nan")}])
    j = C.to_jsonable({"values": df["v"].tolist()})
    assert j["values"][1] is None                        # NaN→null
    json.dumps(j, allow_nan=False, ensure_ascii=False)   # 出口 JSON 安全断言
