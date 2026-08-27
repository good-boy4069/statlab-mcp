r"""tests/test_inline_adoption.py —— v1.2.0 T3d：inline 通道收束验收。

1. adoption 动态签名扫描：28 个文件型工具具备 inline_data+data_source；
   power_analysis（纯参数型）与 analysis_plan（可选源）按各自规则断言；
2. stdio 客户端往返 4 笔：describe/hypothesis × records/split（对应验收清单
   "records/split 两形态各 ≥2 工具"字面底线）+ 错误往返一笔（双给→E1001）；
3. schema 形态快照：inline_data property 为 array/object/null 三粗类型 anyOf，
   零嵌套 $ref（ fixtures/inline_schema_shape.json 集合级比对）。
"""
import asyncio
import inspect
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from statlab_mcp import _resources as R
from statlab_mcp.server import _TOOL_MODULES

CSV = str(ROOT / "samples" / "clean.csv")
SHAPE_FIXTURE = ROOT / "tests" / "fixtures" / "inline_schema_shape.json"

INLINE_DOC_TOOLS = 28          # 26 既有文件型 + impute_missing + backtest_forecast
OPTIONAL_SOURCE_TOOLS = {"analysis_plan"}              # T4 后并入（data_source 三态）
NO_SOURCE_TOOLS = {"power_analysis"}                   # 纯参数型，永不适用


def _tool_fns():
    return {R.tool_public_fn(m).__name__: R.tool_public_fn(m)
            for m in _TOOL_MODULES}


def test_adoption_signature_scan():
    fns = _tool_fns()
    with_inline = {n for n, fn in fns.items()
                   if "inline_data" in inspect.signature(fn).parameters}
    assert len(with_inline) == INLINE_DOC_TOOLS, \
        f"inline 化工具数 {len(with_inline)} != {INLINE_DOC_TOOLS}: {sorted(with_inline)}"
    assert not (with_inline & NO_SOURCE_TOOLS), "纯参数型工具被误 inline 化"
    # 其余注册工具：可选源（analysis_plan）或纯参数（power_analysis）
    others = set(fns) - with_inline
    assert others <= OPTIONAL_SOURCE_TOOLS | NO_SOURCE_TOOLS, \
        f"存在未按规约登记的工具：{sorted(others)}"


def test_adoption_uses_resolve_data_single_point():
    """单点分派纪律：全部 inline 工具经 resolve_data，禁止自行解析。"""
    for n, fn in _tool_fns().items():
        if n in NO_SOURCE_TOOLS:
            continue
        src = Path(inspect.getsourcefile(fn)).read_text(encoding="utf-8")
        assert "resolve_data(" in src, f"{n}: 未通过 resolve_data 单点分派"


def _stdio_params() -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable, args=["-m", "statlab_mcp.server"], cwd=str(ROOT),
        env={**os.environ, "PYTHONUTF8": "1"})


def test_stdio_roundtrip_four_calls():
    """真实 stdio 往返 4 笔：两形态 × 两工具（第六节验收字面底线）。"""

    async def main():
        async with stdio_client(_stdio_params()) as (r, w), ClientSession(r, w) as s:
            await s.initialize()
            records = [{"score": 88.0, "income": 5000.0},
                       {"score": 95.0, "income": 8000.0},
                       {"score": 72.0, "income": 4000.0}]
            split = {"header": ["score", "income"],
                     "rows": [[88.0, 5000.0], [95.0, 8000.0], [72.0, 4000.0]]}
            for tool in ("describe_statistics", "correlation_matrix"):
                for label, payload in (("records", records), ("split", split)):
                    args = {"inline_data": payload}
                    if tool == "correlation_matrix":
                        args.pop("income", None)
                    res = await s.call_tool(tool, args)
                    obj = json.loads(res.content[0].text)
                    assert obj["status"] == "ok", (tool, label, obj)
                    assert obj["data_source"] == "inline", obj          # D5：返回顶层
            # 错误往返：双给 → E1001
            res_err = await s.call_tool(
                "describe_statistics",
                {"file_path": CSV, "inline_data": records})
            err_obj = json.loads(res_err.content[0].text)
            assert err_obj["error_code"] == "E1001"

    asyncio.run(main())


def test_schema_shape_snapshot():
    """tools/list 中 inline_data 的 schema 形态锁定：三粗类型 anyOf、零 $ref。"""
    from tests.test_resources_desc import _fresh_server
    server = _fresh_server()
    tools = asyncio.run(server.list_tools())
    shapes = {}
    for t in tools:
        p = (t.input_schema or {}).get("properties", {}).get("inline_data")
        if p is not None:
            shapes[t.name] = json.dumps(p, sort_keys=True)
    assert shapes, "未发现任何工具携带 inline_data"
    for name, s in shapes.items():
        obj = json.loads(s)
        if "anyOf" in obj:
            kinds = sorted(x.get("type", "?") for x in obj["anyOf"])
            assert kinds == ["array", "null", "object"], (name, kinds)
        else:
            assert obj.get("type") in ("array", "object", "null"), (name, obj)
        assert "$ref" not in s and "definitions" not in s, name
