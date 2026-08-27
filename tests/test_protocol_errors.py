"""tests/test_protocol_errors.py —— Qoder 锐评 #1：参数校验失败必须走统一中文错误协议。

场景：NaN/Inf/类型错误等被 pydantic schema 层拦截的参数，SDK 默认返回英文
"Error executing tool ... validation error" 文本；StatlabServer 子类将其转换为
{status:"error", message:中文} JSON，与工具内错误格式闭环（v1.0.2 修复）。
通过官方 stdio 客户端真实调用验证（子进程启动，约 6s）。
"""
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

CSV = str(ROOT / "samples" / "clean.csv")


def _params() -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "statlab_mcp.server"],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONUTF8": "1"},
    )


async def _call(session, name: str, args: dict) -> str:
    res = await session.call_tool(name, args)
    return res.content[0].text


def _run(coro):
    return asyncio.run(coro)


def test_nan_alpha_maps_to_chinese_error():
    """锐评 FAIL 场景复现：alpha=NaN 被 schema 层拦截时必须返回中文统一错误 JSON。"""

    async def main():
        async with stdio_client(_params()) as (read, write), \
                ClientSession(read, write) as session:
            await session.initialize()
            text = await _call(session, "anova_test", {
                "file_path": CSV, "group_col": "category",
                "value_col": "score", "alpha": float("nan")})
            obj = json.loads(text)
            assert obj["status"] == "error", text
            assert "参数校验失败" in obj["message"]
            assert "NaN" in obj["message"]
            assert obj["error_code"] == "E1001", text   # v1.1.0：pydantic 转换通路注入机器码

    _run(main())


def test_bad_type_maps_to_chinese_error():
    """类型错误（字符串当浮点）同样走中文协议。"""

    async def main():
        async with stdio_client(_params()) as (read, write), \
                ClientSession(read, write) as session:
            await session.initialize()
            text = await _call(session, "confidence_interval", {
                "file_path": CSV, "column": "income", "confidence": "abc"})
            obj = json.loads(text)
            assert obj["status"] == "error", text
            assert obj["message"]

    _run(main())


def test_normal_call_unaffected():
    """正常调用不受协议包装影响，仍返回 ok JSON。"""

    async def main():
        async with stdio_client(_params()) as (read, write), \
                ClientSession(read, write) as session:
            await session.initialize()
            text = await _call(session, "describe_statistics", {"file_path": CSV})
            obj = json.loads(text)
            assert obj["status"] == "ok", text

    _run(main())


def test_missing_required_param_maps_to_e1001():
    """C13b 红队 P0-1 守护：D17 optional 化后漏传必填参数必须走 E1001 中文协议。

    require_non_none 现位于 try: 内（工具统一错误包装生效）；此用例经完整
    stdio 链路断言返回体（此前守护全部直接函数调用，恰好绕过该路径）。
    """

    async def main():
        async with stdio_client(_params()) as (read, write), \
                ClientSession(read, write) as session:
            await session.initialize()
            # hypothesis_test 漏传 column（原 schema required，D17 后运行期强校验）
            text = await _call(session, "hypothesis_test", {"alpha": 0.05})
            obj = json.loads(text)
            assert obj["status"] == "error", text
            assert obj["error_code"] == "E1001", text
            assert "缺少必需参数" in obj["message"] and "column" in obj["message"], text

    _run(main())
