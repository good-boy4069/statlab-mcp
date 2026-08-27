"""tests/test_resources_desc.py —— resources 能力 + description 双轨验收（v1.2.0 C0 起基线换锚）。

钉死验收项：
1. 默认（STATLAB_DESC_MODE 未设置）tools/list 与 **v1.1.0 基线**对比，差异仅允许四类白名单：
   ① description 的 inline 说明段（变化行须含 "inline_data" 字样）
   ② schema 新增可选 `inline_data` 属性（禁止删除/改动既有属性定义）
   ③ `file_path` required 移除（且不得新增其它 required、类型定义不变）
   ④ 新增工具单向白名单（_ADDED_SINCE_V1_1_0；基线内工具不得消失）；
   未登记的任何差异一律红（机器判定，逐工具逐属性枚举，禁止人眼比对）。
   [历史档案] tests/fixtures/tools_list_full_v1_0_3.json 为 v1.0.3 时代基线，
   自本守护换锚起退役为存档；其内容涉及的 docs/→statlab_mcp/docs/ 路径词与
   correlation_matrix 参数段差异已随基线切换失去维护意义，文件保留仅为追溯。
2. slim 模式总字节数较 full 下降 ≥50%；
3. slim 下每个工具 description 含其全部参数名（防瘦身过度）；
4. resources/list 数量 = 工具数 + 1；statlab://spec 与任一 manual 可读非空含工具名；
5. STATLAB_DESC_MODE 非法取值 stderr 中文告警并回退 full。
捕获条件（meta 文件 tools_list_full_v1_1_0.meta.txt）：STATLAB_DESC_MODE 未设、
captured_commit=f66970b、tool_count=27。
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

FIXTURE = ROOT / "tests" / "fixtures" / "tools_list_full_v1_1_0.json"
# 第④类：v1.1.0 基线之后新增的工具（单向白名单——C1/C2/C11 各加一名；
# 成员在其所属批次 inline 化完成后，schema/docstring 差异须落入①②③类）
_ADDED_SINCE_V1_1_0: set[str] = set()


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


def _allowed_schema_diff(base_schema: dict, cur_schema: dict) -> bool:
    """第②③类机判：properties 只允许新增 inline_data 且既有定义逐字不变；
    required 只允许移除 file_path。其余任何 schema 变化非法。"""
    bp = base_schema.get("properties", {})
    cp = cur_schema.get("properties", {})
    if not set(cp) >= set(bp):
        return False                                  # 禁止删除既有属性
    if set(cp) - set(bp) - {"inline_data"}:
        return False                                  # 只允许新增 inline_data
    for k in bp:
        if cp.get(k) != bp[k]:
            return False                              # 既有属性定义禁止漂移
    br = set(base_schema.get("required", []))
    cr = set(cur_schema.get("required", []))
    return (br - cr) <= {"file_path"} and not (cr - br)


def test_full_matches_v1_1_0_baseline_four_category_whitelist():
    """默认 tools/list 对 v1.1.0 基线的机械审计：四类白名单逐工具逐属性枚举。"""
    assert DESC_MODE == "full", "测试进程默认必须为 full 模式"
    current = _serialize(_fresh_server())
    base_map = {d["name"]: d for d in json.loads(FIXTURE.read_text(encoding="utf-8"))}
    cur_map = {d["name"]: d for d in json.loads(current.decode("utf-8"))}

    # 第④类：新增工具=注册集−基线集，必须与登记集合完全一致（双向核对防漂移）
    added_now = set(cur_map) - set(base_map)
    assert added_now == _ADDED_SINCE_V1_1_0, \
        f"新增工具与登记集合不符：实际 {sorted(added_now)} vs 登记 {sorted(_ADDED_SINCE_V1_1_0)}"
    assert not (set(base_map) - set(cur_map)), "基线内工具不得消失"

    problems: list[str] = []
    for name in sorted(base_map):
        base = base_map[name]
        cur = cur_map[name]
        if base["inputSchema"] != cur["inputSchema"] and \
                not _allowed_schema_diff(base["inputSchema"], cur["inputSchema"]):
            problems.append(f"{name}: inputSchema 存在④类之外的变化")
        # 第①类：description 行级 diff，每条增删行必须提及 inline_data；
        # 变化行数上限 24 防整段重写混过行级检查
        old_lines = set(base["description"].splitlines())
        new_lines = set(cur["description"].splitlines())
        changed = old_lines ^ new_lines
        bad = [ln for ln in changed if "inline_data" not in ln]
        if changed and bad:
            problems.append(f"{name}: description 变化行缺少 inline_data 说明特征：{bad[:3]}")
        elif len(changed) > 24:
            problems.append(f"{name}: description 变化行数 {len(changed)} 过大，疑似整段重写")
    assert not problems, "\n".join(problems)


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
