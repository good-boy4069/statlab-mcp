"""tests/test_resources_desc.py —— v1.1.0 P0-1：resources 能力 + description 双轨验收。

钉死验收项：
1. 默认（STATLAB_DESC_MODE 未设置）tools/list 与 v1.0.3 留档逐字节一致
   （唯一已知差异：description 中设计文档路径由旧版 docs/ 前缀改为包内
    statlab_mcp/docs/ 前缀，
   随打包闭环发生，CHANGELOG 已披露；对比按该归一化规则进行，其余字符零差异）；
2. slim 模式总字节数较 full 下降 ≥50%；
3. slim 下每个工具 description 含其全部参数名（防瘦身过度）；
4. resources/list 数量 = 工具数 + 1；statlab://spec 与任一 manual 可读非空含工具名；
5. STATLAB_DESC_MODE 非法取值 stderr 中文告警并回退 full。
"""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcp.server.mcpserver import MCPServer

from statlab_mcp import _resources as R
from statlab_mcp.server import _TOOL_MODULES, DESC_MODE, StatlabServer, bootstrap

FIXTURE = ROOT / "tests" / "fixtures" / "tools_list_full_v1_0_3.json"
# 已披露的路径前缀差异归一化；字面量拼接写法防"批量路径替换脚本"误伤本行
_OLD_DOC_PREFIX = "docs" + "/"
_NEW_DOC_PREFIX = ("statlab_mcp" + "/") + _OLD_DOC_PREFIX
_NORM = (_NEW_DOC_PREFIX, _OLD_DOC_PREFIX)


def _serialize(server: MCPServer) -> bytes:
    tools = asyncio.run(server.list_tools())
    items = sorted(
        ({"name": t.name, "description": t.description, "inputSchema": t.input_schema}
         for t in tools),
        key=lambda x: x["name"])
    return json.dumps(items, ensure_ascii=False, sort_keys=True).encode("utf-8")


def _fresh_server() -> StatlabServer:
    """新建独立实例并完成注册（module-level mcp 与测试实例隔离）。"""
    server = StatlabServer("statlab-mcp")
    bootstrap(server)
    return server


def test_full_matches_v1_0_3_baseline_after_doc_path_normalization():
    assert DESC_MODE == "full", "测试进程默认必须为 full 模式"
    current = _serialize(_fresh_server())
    baseline = FIXTURE.read_bytes()
    cur_norm = json.loads(current.decode("utf-8"))
    base_norm = json.loads(baseline.decode("utf-8"))
    for item in cur_norm:
        item["description"] = item["description"].replace(*_NORM)
    for item in base_norm:
        item["description"] = item["description"].replace(*_NORM)
    blob_cur = json.dumps(cur_norm, ensure_ascii=False, sort_keys=True).encode("utf-8")
    blob_base = json.dumps(base_norm, ensure_ascii=False, sort_keys=True).encode("utf-8")
    assert len(base_norm) == 26 and len(cur_norm) == 26
    # 差异必须仅限已披露路径词：归一化后逐字节一致
    assert blob_cur == blob_base


def test_slim_reduces_description_bytes_at_least_50pct():
    mods = list(_TOOL_MODULES)
    full_blob = b"".join(
        (mod.__doc__ or "").encode("utf-8") for mod in mods)
    slim_parts = []
    for mod in mods:
        fn = R.tool_public_fn(mod)
        slim_parts.append(R.make_slim_description(fn, mod.__doc__).encode("utf-8"))
    slim_blob = b"".join(slim_parts)
    ratio = len(slim_blob) / len(full_blob)
    assert ratio <= 0.5, f"slim/full = {ratio:.3f}，未达到 ≥50% 削减要求"


def test_slim_keeps_every_parameter_name():
    import inspect
    for mod in _TOOL_MODULES:
        fn = R.tool_public_fn(mod)
        slim = R.make_slim_description(fn, mod.__doc__)
        for pname in inspect.signature(fn).parameters:
            assert pname in slim, f"{fn.__name__}: 参数 {pname} 在 slim description 中丢失"


def test_slim_loses_no_value_constraint_text():
    """取值约束不丢：docstring 参数行的说明文本须原样出现在 slim 版中。"""
    from statlab_mcp.tools import inference_hypothesis_test as ht
    fn = R.tool_public_fn(ht)
    slim = R.make_slim_description(fn, ht.__doc__)
    for kw in ("two_sided / less / greater", "(0,1)"):   # 该工具参数表的枚举与区间原文
        assert kw in slim, f"约束文本 {kw!r} 在 slim 中丢失"


def test_resources_list_and_read():
    server = _fresh_server()
    res = asyncio.run(server.list_resources())
    assert len(res) == len(_TOOL_MODULES) + 1
    uris = sorted(str(r.uri) for r in res)
    assert "statlab://spec" in uris
    manuals = [u for u in uris if u.startswith("statlab://tools/") and u.endswith("/manual")]
    assert len(manuals) == len(_TOOL_MODULES)

    got_spec = asyncio.run(server.read_resource("statlab://spec"))
    spec_obj = got_spec[0]
    assert spec_obj.content.strip()
    assert "统一返回协议" in spec_obj.content and "错误码" in spec_obj.content

    one = manuals[len(manuals) // 2]
    obj = asyncio.run(server.read_resource(one))[0]
    assert obj.content.strip() and obj.mime_type == "text/markdown"
    tool_name = one.split("/")[-2]
    assert tool_name in obj.content


def test_manual_contains_design_section_of_every_tool():
    for mod in _TOOL_MODULES:
        fn = R.tool_public_fn(mod)
        manual = R.build_manual(mod, fn)
        assert fn.__name__ in manual
        assert "设计文档对应小节" in manual
        assert "## " in manual          # 小节的子标题确实被搬入


def test_invalid_desc_mode_warns_and_falls_back(capsys):
    assert R.resolve_desc_mode(raw="bogus") == "full"
    err_out = capsys.readouterr().err
    assert "STATLAB_DESC_MODE" in err_out and "非法" in err_out and "full" in err_out
    assert R.resolve_desc_mode(raw="") == "full"       # 未设置语义：静默回退
    assert capsys.readouterr().err == ""
    assert R.resolve_desc_mode(raw="slim") == "slim"


def test_stdio_env_is_read_at_process_start_not_lazily(monkeypatch):
    """开关在进程启动解析一次（模块级 DESC_MODE），运行期改环境变量不影响行为。"""
    monkeypatch.setenv("STATLAB_DESC_MODE", "slim")
    assert DESC_MODE == "full"                          # 本进程启动时未设置 → 已固定 full


def test_bootstrap_double_register_does_not_duplicate():
    """防手滑契约：重复注册不得产生双份（SDK 覆盖语义即可），资源数保持 工具数+1。"""
    server = _fresh_server()
    n_before = len(asyncio.run(server.list_resources()))
    bootstrap(server)                                   # 重复全量注册
    res_after = asyncio.run(server.list_resources())
    n_after = len(res_after)
    assert n_before == n_after == len(_TOOL_MODULES) + 1
    uris = [str(r.uri) for r in res_after]
    assert len(uris) == len(set(uris))                  # 无重复 URI
