# -*- coding: utf-8 -*-
"""statlab-mcp MCP Server 入口（规范 9：只注册工具 + to_jsonable，保持 ≤150 行）。

Windows 硬性要求 1：stdio 用 UTF-8 编码输出中文 JSON（配合 $env:PYTHONUTF8="1"，
双保险：stdout 流重配置为 utf-8）。
注册机制（红队裁决 I4）：每个工具模块提供一个 register(mcp) 回调，本文件仅逐模块
收集注册，每工具一行；任何统计计算都发生在 tools/ 下各工具模块，本文件不含逻辑。
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")

from mcp.server.mcpserver import MCPServer  # mcp 2.x：FastMCP 重构后的高层服务器类

from statlab_mcp.tools import _common  # noqa: F401  导入即执行 seed(42)/Agg/字体/日志配置
from statlab_mcp.tools import data_exploration_describe_statistics as _t1  # 工具 1
from statlab_mcp.tools import data_exploration_data_type_check as _t2  # 工具 2
from statlab_mcp.tools import data_exploration_missing_report as _t3  # 工具 3
from statlab_mcp.tools import data_exploration_correlation_matrix as _t4  # 工具 4
from statlab_mcp.tools import data_exploration_outlier_detect as _t5  # 工具 5
from statlab_mcp.tools import inference_hypothesis_test as _t6  # 工具 6
from statlab_mcp.tools import inference_normality_test as _t9  # 工具 9
from statlab_mcp.tools import inference_confidence_interval as _t10  # 工具 10
from statlab_mcp.tools import inference_anova_test as _t7  # 工具 7

# 工具模块注册表：随实现推进逐个加入（每工具一行）
_TOOL_MODULES: list = [_t1, _t2, _t3, _t4, _t5, _t6, _t9, _t10, _t7]

mcp = MCPServer("statlab-mcp")


def _register_all() -> None:
    """调用各工具模块的 register(mcp) 完成工具注册。"""
    for mod in _TOOL_MODULES:
        mod.register(mcp)


if __name__ == "__main__":
    _register_all()
    mcp.run()