# -*- coding: utf-8 -*-
"""里程碑 1 冒烟测试：官方 SDK 最小 client 走 stdio 完整协议调用真实工具（留档用）。

运行：.venv\\Scripts\\python.exe tests\\smoke_stdio.py
覆盖：initialize 握手 → list_tools 枚举 → 五个探查组工具真实调用与 JSON 解析；
不依赖 npx/inspector 交互面板，输出可逐字留档复现。
"""
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcp import ClientSession  # mcp 2.x 顶层导出
from mcp.client.stdio import stdio_client, StdioServerParameters

SERVER = str(ROOT / "statlab_mcp" / "server.py")


async def main() -> None:
    # 必须以 -m statlab_mcp.server + cwd=项目根 启动：sys.path[0] 含项目根，
    # 否则 import statlab_mcp 失败（冒烟实测结论，客户端配置同此写法）
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "statlab_mcp.server"],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"[SMOKE] initialize ok: server={init.server_info.name} {init.server_info.version}")  # 2.x 属性名 server_info
            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            print(f"[SMOKE] tools({len(names)}): {names}")

            calls = [
                ("describe_statistics", str(ROOT / "samples" / "clean.csv")),
                ("data_type_check", str(ROOT / "samples" / "dirty.csv")),
                ("missing_report", str(ROOT / "samples" / "dirty.csv")),
                ("correlation_matrix", str(ROOT / "samples" / "clean.csv")),
                ("outlier_detect", str(ROOT / "samples" / "dirty.csv")),
            ]
            for tname, path in calls:
                res = await session.call_tool(tname, {"file_path": path})
                text = res.content[0].text
                obj = json.loads(text)            # 纯 JSON 往返（无 NaN/Infinity 字面量）
                assert obj["status"] == "ok", text
                img = obj.get("__image__")
                print(f"[SMOKE] {tname}: ok | {obj['summary'][:64]}"
                      + (f" | __image__={img!r}" if img else ""))
            print("[SMOKE] ALL-STDIO-OK")


if __name__ == "__main__":
    asyncio.run(main())