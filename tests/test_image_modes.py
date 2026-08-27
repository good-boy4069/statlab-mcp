"""tests/test_image_modes.py —— v1.1.0 P0-3：图片双轨（path 默认 / content）验收。

覆盖：
1. content 模式改写为 [ImageContent, TextContent]，TextContent JSON 惟去 __image__ 键，
   structured_content 同构无该键，ImageContent 数据 base64 解码与源 PNG 字节逐字节一致；
2. 大图防护：> 阈值自动回退 path 形态、summary 追加固定文案、stderr INFO 日志；
3. 不满足前提的结果原样透传（默认模式零介入的结构保证）；
4. STATLAB_IMAGE_MODE 非法取值 stderr 中文告警并回退 path；
5. 真实 stdio 双子进程（env 启动语义）：默认 path 返回 __image__ 路径字段；
   content 返回标准 MCP 客户端可解析的 ImageContent + 无键 JSON + structured_content；
6. 确定性：同一输入两次绘图产生字节级一致的 PNG 文件。
"""
import asyncio
import base64
import json
import logging
import os
import sys
from pathlib import Path

from mcp_types import CallToolResult, ImageContent, TextContent

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from statlab_mcp import _imaging

CLEAN = str(ROOT / "samples" / "clean.csv")

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _ok_result_with_image(png: bytes, tmp_path: Path, summary="画好了") -> CallToolResult:
    p = tmp_path / "img.png"
    p.write_bytes(png)
    obj = {"status": "ok", "result": {"n": 5}, "summary": summary,
           "__image__": str(p)}
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(obj, ensure_ascii=False))],
        is_error=False)


def test_content_mode_rewrite_block_structure(tmp_path):
    png = PNG_MAGIC + bytes(range(48))
    result = _ok_result_with_image(png, tmp_path)
    got = _imaging.rewrite_for_content_mode(result)
    assert not got.is_error
    assert len(got.content) == 2
    img, txt = got.content
    assert isinstance(img, ImageContent)
    assert img.mime_type == "image/png"
    assert base64.b64decode(img.data) == png          # 字节级一致（确定性承载）
    assert isinstance(txt, TextContent)
    obj = json.loads(txt.text)
    assert "__image__" not in obj                      # 惟去此键
    assert obj["status"] == "ok" and obj["result"] == {"n": 5}
    assert obj["summary"] == "画好了"
    assert got.structured_content == obj               # structuredContent 同构且无键


def test_large_png_falls_back_to_path_form(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(_imaging, "IMAGE_FALLBACK_BYTES", 8)
    png = PNG_MAGIC + b"x" * 64
    result = _ok_result_with_image(png, tmp_path, summary="画好了")
    with caplog.at_level(logging.INFO, logger="statlab_mcp"):
        got = _imaging.rewrite_for_content_mode(result)
    assert len(got.content) == 1 and isinstance(got.content[0], TextContent)
    obj = json.loads(got.content[0].text)
    assert "__image__" in obj                          # path 形态保留路径键
    assert obj["summary"].endswith(_imaging.FALLBACK_NOTE)
    assert any(r.levelno == logging.INFO and "回退 path" in r.message
               for r in caplog.records)


def test_non_image_results_pass_through_unchanged(tmp_path):
    # 错误结果 / 无图 ok / 参数校验失败形态：一律原样返回（同一对象）
    err_res = CallToolResult(content=[TextContent(type="text",
                                                  text=json.dumps({"status": "error"},
                                                                  ensure_ascii=False))],
                             is_error=True)
    assert _imaging.rewrite_for_content_mode(err_res).content == err_res.content
    ok_no_img = CallToolResult(content=[TextContent(type="text",
                                                    text=json.dumps({"status": "ok",
                                                                     "result": {},
                                                                     "summary": "s"}))])
    assert _imaging.rewrite_for_content_mode(ok_no_img) is ok_no_img


def test_invalid_image_mode_warns_and_falls_back(capsys):
    assert _imaging.resolve_image_mode(raw="base64") == "path"
    err_out = capsys.readouterr().err
    assert "STATLAB_IMAGE_MODE" in err_out and "非法" in err_out and "path" in err_out
    assert _imaging.rewrite_for_content_mode.__doc__     # 实现入口存在
    assert _imaging.resolve_image_mode(raw=None) == "path"


def test_deterministic_png_bytes_same_input():
    """确定性：同输入两次绘图产生字节级一致的 PNG（save_plot 时间戳命名不同文件）。"""
    from statlab_mcp import _resources as R
    from statlab_mcp.tools import visualization_plot_histogram as hist_mod
    fn = R.tool_public_fn(hist_mod)
    a = fn(CLEAN, column="score")
    b = fn(CLEAN, column="score")
    assert a["status"] == "ok" and b["status"] == "ok"
    pa, pb = Path(a["__image__"]), Path(b["__image__"])
    assert pa.read_bytes() == pb.read_bytes()          # 字节级一致断言


def _params() -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "statlab_mcp.server"],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONUTF8": "1"},       # env 在进程启动时读取
    )


def _params_env(extra: dict) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "statlab_mcp.server"],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONUTF8": "1", **extra},
    )


def test_stdio_default_mode_returns_path_field():
    """默认（未设置）子进程：plot_histogram 成功结果带 __image__ 路径字段（v1.0.3 行为）。"""

    async def main():
        async with stdio_client(_params()) as (r, w), ClientSession(r, w) as s:
            await s.initialize()
            res = await s.call_tool("plot_histogram",
                                    {"file_path": CLEAN, "column": "score"})
            assert res.is_error is not True
            obj = json.loads(res.content[0].text)
            assert obj["status"] == "ok" and "__image__" in obj
            assert Path(obj["__image__"]).exists()

    asyncio.run(main())


def test_stdio_content_mode_returns_standard_image_content():
    """content 子进程：ImageContent 标准类型可被官方客户端解析；JSON/SC 惟去 __image__。"""

    async def main():
        async with stdio_client(
                _params_env({"STATLAB_IMAGE_MODE": "content"})) as (r, w), \
                ClientSession(r, w) as s:
            await s.initialize()
            res = await s.call_tool("plot_histogram",
                                    {"file_path": CLEAN, "column": "score"})
            assert res.is_error is not True
            img, txt = res.content[0], res.content[1]
            assert img.type == "image" and img.mime_type == "image/png"
            raw = base64.b64decode(img.data)
            assert raw.startswith(PNG_MAGIC)
            obj = json.loads(txt.text)
            assert "__image__" not in obj and obj["status"] == "ok"
            sc = res.structured_content
            assert sc is not None and "__image__" not in sc
            assert sc["summary"] == obj["summary"]
            # 图形本体两处来源一致：ImageContent 字节 == 磁盘归档文件字节
            archived = list((ROOT / "reports" / "plots").rglob("plot_histogram_score_*.png"))
            assert archived and raw in [p.read_bytes() for p in archived]

    asyncio.run(main())
