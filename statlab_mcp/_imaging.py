"""statlab-mcp 图片双轨（v1.1.0 P0-3）：STATLAB_IMAGE_MODE = path(默认) | content。

实现位置刻意选在 StatlabServer.call_tool 的成功返回路径上做统一改写——26 个工具
模块零改动、path 模式（默认）逐字段保持 v1.0.3 行为。content 模式规则（SPEC 第 5 节钉死）：
- 返回 [ImageContent(mimeType="image/png", data=<PNG base64>), TextContent(JSON)]，
  TextContent JSON 与 path 模式完全相同、惟去掉 __image__ 键；
- structured_content 同时为去键后的完整 {status, result, summary}；
- 单张 PNG > 2.0MB 自动回退 path 形态，summary 末尾追加"（图片较大已回退路径模式）"，
  并向 stderr 记录一条 INFO 日志；
- 非法取值进程启动时 stderr 中文告警并回退默认 path（铁律 9）。
"""
from __future__ import annotations

import base64
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from mcp_types import CallToolResult, ImageContent, TextContent

IMAGE_MODE_ENV = "STATLAB_IMAGE_MODE"
_VALID_IMAGE_MODES = ("path", "content")
_DEFAULT_IMAGE_MODE = "path"

# 大图防护阈值（钉死 2.0MB）：超过即回退 path 形态，防 base64 撑爆客户端上下文
IMAGE_FALLBACK_BYTES = int(2.0 * 1024 * 1024)

FALLBACK_NOTE = "（图片较大已回退路径模式）"

logger = logging.getLogger("statlab_mcp")


def resolve_image_mode(raw: str | None = None, stream: Any = None) -> str:
    """解析图片双轨开关；非法/未设置均落回默认 path，非法时 stderr 中文告警。"""
    value = os.environ.get(IMAGE_MODE_ENV) if raw is None else raw
    if value is None or value.strip() == "":
        return _DEFAULT_IMAGE_MODE
    if value not in _VALID_IMAGE_MODES:
        print(f"[statlab-mcp] 告警：环境变量 {IMAGE_MODE_ENV}={value!r} 非法"
              f"（仅支持 {'/'.join(_VALID_IMAGE_MODES)}），已回退默认值 {_DEFAULT_IMAGE_MODE}",
              file=stream or sys.stderr)
        return _DEFAULT_IMAGE_MODE
    return value


def _dump_like_sdk(obj: dict[str, Any]) -> str:
    """与 SDK _convert_to_content 同参数序列化（to_json fallback=str, indent=2）。"""
    import pydantic_core

    return pydantic_core.to_json(obj, fallback=str, indent=2).decode("utf-8")


def rewrite_for_content_mode(result: CallToolResult) -> CallToolResult:
    """把带 __image__ 的成功单文本块结果改写为 [ImageContent, TextContent] 内容块列表。

    不满足前提（错误结果、多块、非 JSON、无 __image__、文件缺失）一律原样返回：
    双轨只影响带图工具的成功路径，其余结果零感知。
    """
    if result.is_error or len(result.content) != 1 \
            or not isinstance(result.content[0], TextContent):
        return result
    try:
        obj = json.loads(result.content[0].text)
    except (ValueError, TypeError):
        return result
    if not isinstance(obj, dict) or "__image__" not in obj:
        return result

    img_path = Path(str(obj["__image__"]))
    try:
        png_bytes = img_path.read_bytes()
    except OSError:
        logger.error("content 模式读取图片失败：%s；按原样返回 path 结果", img_path)
        return result

    clean = {k: v for k, v in obj.items() if k != "__image__"}
    if len(png_bytes) > IMAGE_FALLBACK_BYTES:
        # 大图防护：完整回退 path 形态（含 __image__、无 structured_content，
        # 与默认模式输出同构）+ summary 追加 + INFO 日志（钉死行为）
        obj["summary"] = f"{obj.get('summary', '')}{FALLBACK_NOTE}"
        logger.info("图片 %s（%.2fMB）超过 %.1fMB 阈值，已回退 path 模式",
                    img_path.name, len(png_bytes) / 1024 / 1024,
                    IMAGE_FALLBACK_BYTES / 1024 / 1024)
        return CallToolResult(
            content=[TextContent(type="text", text=_dump_like_sdk(obj))],
            is_error=False)

    data = base64.b64encode(png_bytes).decode("ascii")
    return CallToolResult(
        content=[ImageContent(type="image", data=data, mime_type="image/png"),
                 TextContent(type="text", text=_dump_like_sdk(clean))],
        structured_content=clean, is_error=False)
