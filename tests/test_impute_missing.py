r"""tests/test_impute_missing.py —— v1.2.0 T1：工具 28 impute_missing 验收。

手算锚（可人工复核粒度）：
- [1,2,∅,4] mean → 7/3（有限观测均值=(1+2+4)/3）；
- [1,2,∅,4] median → 2（[1,2,4] 中位数）；
- [1,2,inf] mean → 1.5（±Inf 不算缺失不计入均值，excluded_nonfinite=1——R2-F05 口径）；
- constant=9 对全缺失列生效；
- 时间戳归一化确定性：__output__ 的 \d{8}_\d{6}_\d{3} 段占位化后两次调用 JSON
  逐字节一致 + 反证两次路径字符串确实不同。
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from statlab_mcp.tools._common import read_table
from statlab_mcp.tools.data_exploration_impute_missing import _escape_csv_cell, impute_missing

TS_SEG = re.compile(r"_\d{8}_\d{6}_\d{3}\.csv$")


def _mk(df: pd.DataFrame, tmp_path: Path, name="t.csv") -> str:
    p = tmp_path / name
    df.to_csv(p, index=False)
    return str(p)


def _r(**kw) -> dict:
    r = impute_missing(**kw)
    assert r["status"] == "ok", r.get("message", r)
    return r


def _strip_ts(r: dict) -> dict:
    out = dict(r)
    if "__output__" in out:
        out["__output__"] = TS_SEG.sub("_<TS>.csv", out["__output__"])
    return out


# ---------------- 手算对照 ----------------

def test_mean_hand_computed(tmp_path):
    p = _mk(pd.DataFrame({"v": [1.0, 2.0, np.nan, 4.0]}), tmp_path)
    r = _r(file_path=p)
    assert r["result"]["total_filled"] == 1
    entry = r["result"]["columns_processed"][0]
    assert entry["filled"] == 1 and entry["residual_missing"] == 0
    out = read_table(r["__output__"])
    assert float(out["v"].iloc[2]) == pytest.approx(7 / 3)


def test_median_and_constant_hand_computed(tmp_path):
    p = _mk(pd.DataFrame({"v": [1.0, 2.0, np.nan, 4.0]}), tmp_path)
    rm = _r(file_path=p, strategy="median")
    out_m = read_table(rm["__output__"])
    assert float(out_m["v"].iloc[2]) == 2.0              # [1,2,4] 中位数=2
    rc = _r(file_path=p, strategy="constant", value=9)
    entry = rc["result"]["columns_processed"][0]
    assert entry["filled"] == 1 and entry["value_or_direction"] == 9.0
    out_c = read_table(rc["__output__"])
    assert float(out_c["v"].iloc[2]) == 9.0


def test_ffill_bfill_direction(tmp_path):
    p = _mk(pd.DataFrame({"v": [np.nan, 5.0, np.nan, 7.0, np.nan]}), tmp_path)
    rf = _r(file_path=p, strategy="ffill")
    ef = rf["result"]["columns_processed"][0]
    assert ef["filled"] == 2 and ef["residual_missing"] == 1   # 头部 ∅ 无前值残留
    out_f = read_table(rf["__output__"])
    assert float(out_f["v"].iloc[2]) == 5.0
    rb = _r(file_path=p, strategy="bfill")
    eb = rb["result"]["columns_processed"][0]
    assert eb["filled"] == 2 and eb["residual_missing"] == 1   # 尾部 ∅ 残留


def test_inf_excluded_from_mean_not_missing(tmp_path):
    """±Inf 不算缺失（isna 口径）：Inf-only 无 NaN 缺失 → 归入"全表无缺失"E1012；
    显式点名列时可看到 excluded_nonfinite 报告（见下一用例的组合分支）。"""
    p = _mk(pd.DataFrame({"v": [1.0, 2.0, np.inf]}), tmp_path)
    r = impute_missing(file_path=p, strategy="mean")
    assert r["error_code"] == "E1012" and "数据无任何缺失值" in r["message"], r
    assert not Path(r.get("__output__", "")).exists() if "__output__" in r else True


def test_mean_hand_computed_with_inf_column(tmp_path):
    p = _mk(pd.DataFrame({"v": [1.0, 2.0, np.nan, np.inf]}), tmp_path)
    r = _r(file_path=p, strategy="mean")
    e = r["result"]["columns_processed"][0]
    # NaN 被 fill、Inf 被排除：mean=(1+2)/2=1.5
    assert e["filled"] == 1 and e["excluded_nonfinite"] == 1
    assert read_table(r["__output__"])["v"].iloc[2] == 1.5


def test_constant_on_all_missing_column(tmp_path):
    p = _mk(pd.DataFrame({"a": [np.nan] * 3, "b": [1.0, 2.0, 3.0]}), tmp_path)
    r = _r(file_path=p, columns=["a"], strategy="constant", value=9)
    e = r["result"]["columns_processed"][0]
    assert e["filled"] == 3 and e["value_or_direction"] == 9.0
    # 全缺失列在非 constant 策略下被跳过且不报错
    r2 = _r(file_path=p, columns=["a"], strategy="median")
    assert r2["result"]["skipped_columns"] == ["a"]
    s = read_table(r2["__output__"])
    assert int(s["a"].isna().sum()) == 3                 # 原样保留


# ---------------- E1012 三情形 ----------------

def test_e1012_three_situations(tmp_path):
    clean = _mk(pd.DataFrame({"v": [1.0, 2.0]}), tmp_path, name="clean.csv")
    only_str = _mk(pd.DataFrame({"s": ["a", None], "n": [1.0, 2.0]}),
                   tmp_path, name="str.csv")
    named = _mk(pd.DataFrame({"v": [1.0, 2.0], "w": [3.0, 4.0]}),
                tmp_path, name="named.csv")
    for kwargs in (
            {"file_path": clean},                        # 全表无缺失
            {"file_path": named, "columns": ["v", "w"]},  # 指定列均无缺失
    ):
        r = impute_missing(**kwargs)
        assert r["error_code"] == "E1012" and "无需插补" in r["message"], r
        json.dumps(r, allow_nan=False, ensure_ascii=False)
    rs = impute_missing(file_path=only_str)              # 缺失仅位于非数值列
    assert rs["error_code"] == "E1012" and "非数值列" in rs["message"], rs


# ---------------- 错误路径 ----------------

def test_param_errors_are_typed_codes(tmp_path):
    p = _mk(pd.DataFrame({"v": [np.nan, 1.0], "name": ["x", "y"]}), tmp_path)
    cases = [
        ({"file_path": p, "strategy": "knn"}, ("E1001",)),
        ({"file_path": p, "strategy": False}, ("E1001",)),
        ({"file_path": p, "strategy": "constant"}, ("E1001",)),           # 缺 value
        ({"file_path": p, "strategy": "constant", "value": float("nan")}, ("E1001",)),
        ({"file_path": p, "strategy": "constant", "value": True}, ("E1001",)),
        ({"file_path": p, "strategy": "mean", "value": 3.0}, ("E1001",)),  # value 错位携带
        ({"file_path": p, "columns": []}, ("E1001",)),
        ({"file_path": p, "columns": ["nope"]}, ("E1008", "E1004")),
    ]
    for kw, allowed in cases:
        r = impute_missing(**kw)
        assert r["status"] == "error" and r["error_code"] in allowed, \
            (kw, r.get("error_code"), r.get("message"))
    r_nc = impute_missing(file_path=p, columns=["name"], strategy="mean")
    assert r_nc["error_code"] == "E1009"                 # object 伪数值列拒绝
    assert r_nc["message"].startswith("列 name 不是数值列")


def test_output_file_contract(tmp_path):
    df = pd.DataFrame({"score": [60.0, np.nan, 80.0], "=cmd": [None, "=x", None]})
    p = _mk(df, tmp_path)
    r = _r(file_path=p, strategy="median")
    op = r["__output__"]
    assert Path(op).exists() and Path(op).is_absolute()
    assert TS_SEG.search(op), op                          # 文件名含毫秒时间戳段
    assert re.search(r"impute_missing_t_median_\d{8}_\d{6}_\d{3}\.csv$", op.replace("\\", "/"))
    assert str(tmp_path.name)[:10] and "\\reports\\imputed\\" in op.replace("/", "\\")
    raw = Path(op).read_bytes()
    assert raw[:3] == b"\xef\xbb\xbf"                     # utf-8-sig BOM
    txt = raw.decode("utf-8-sig")
    assert "'=x" in txt                                   # 公式注入转义生效


def test_deterministic_normalized_json_and_distinct_paths(tmp_path):
    df = pd.DataFrame({"v": [1.0, np.nan, 3.0]})
    p = _mk(df, tmp_path)
    a = _strip_ts(_r(file_path=p))
    b = _strip_ts(_r(file_path=p))
    assert json.dumps(a, ensure_ascii=False, sort_keys=True, allow_nan=False) == \
        json.dumps(b, ensure_ascii=False, sort_keys=True, allow_nan=False)
    pa, pb = _r(file_path=p)["__output__"], _r(file_path=p)["__output__"]
    assert pa != pb                                       # 反证：路径确实随时间戳不同


def test_input_file_untouched(tmp_path):
    src = _mk(pd.DataFrame({"v": [1.0, np.nan, 3.0]}), tmp_path, name="src.csv")
    before = Path(src).read_bytes()
    mtime_before = Path(src).stat().st_mtime_ns
    _r(file_path=src, strategy="median")
    assert Path(src).read_bytes() == before
    assert Path(src).stat().st_mtime_ns == mtime_before


def test_gbk_chinese_columns_roundtrip(tmp_path):
    p = tmp_path / "cn_gbk.csv"
    pd.DataFrame({"成绩": [70.0, np.nan, 90.0], "姓名": ["甲", "乙", "丙"]}).to_csv(
        p, index=False, encoding="gbk")
    r = _r(file_path=str(p), strategy="mean")
    assert "__output__" in r
    back = read_table(r["__output__"])
    assert float(back["成绩"].iloc[1]) == pytest.approx(80.0)


def test_escape_csv_cell_unit():
    assert _escape_csv_cell("=cmd|' /C calc") == "'=cmd|' /C calc"
    assert _escape_csv_cell("+1") == "'+1"
    assert _escape_csv_cell("@at") == "'@at"
    assert _escape_csv_cell("-ok") == "'-ok"
    assert _escape_csv_cell("safe") == "safe"
    assert _escape_csv_cell("bad\x07ctl") == "badctl"
    assert _escape_csv_cell(1.5) == 1.5                   # 非字符串原样通过
