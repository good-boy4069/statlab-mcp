# 客户端接入配置备忘（statlab-mcp）

> 冒烟测试已验证的**唯一正确启动方式**（tests/smoke_stdio.py 实测结论，2026-08-26）：
> 必须以 `-m statlab_mcp.server` 且工作目录 = 项目根启动，否则 `import statlab_mcp` 失败。

## 通用启动参数（所有客户端共用）
- command：`<PROJECT_ROOT>\.venv\Scripts\python.exe`（venv 解释器绝对路径）
- args：`["-m", "statlab_mcp.server"]`
- cwd（工作目录）：`<PROJECT_ROOT>`
- env（环境变量）：`PYTHONUTF8=1`（server 入口另有 sys.stdout.reconfigure 兜底）

## Claude Code（格式可直接用）
项目根放 `.mcp.json`：
```json
{
  "mcpServers": {
    "statlab-mcp": {
      "command": "<PROJECT_ROOT>\\.venv\\Scripts\\python.exe",
      "args": ["-m", "statlab_mcp.server"],
      "env": {"PYTHONUTF8": "1"}
    }
  }
}
```
Claude Code 工作目录即项目根，不需要 cwd 字段（如不在项目根启动，按官方文档补 cwd）。

## Cursor（格式可直接用）
全局或项目 `.cursor/mcp.json`（同 Claude 格式，cursor 支持 cwd 字段）：
```json
{
  "mcpServers": {
    "statlab-mcp": {
      "command": "<PROJECT_ROOT>\\.venv\\Scripts\\python.exe",
      "args": ["-m", "statlab_mcp.server"],
      "cwd": "<PROJECT_ROOT>",
      "env": {"PYTHONUTF8": "1"}
    }
  }
}
```

## VSCode（原生 MCP 支持；字段以官方文档为准）
项目 `.vscode/mcp.json`：
```json
{
  "servers": {
    "statlab-mcp": {
      "type": "stdio",
      "command": "<PROJECT_ROOT>\\.venv\\Scripts\\python.exe",
      "args": ["-m", "statlab_mcp.server"],
      "env": {"PYTHONUTF8": "1"}
    }
  }
}
```
> ⚠️ VSCode 的 MCP 配置字段（servers/type/cwd 位置）随版本演进，若面板不识别请查阅
> VSCode 官方 MCP 文档，不要照抄本文件盲试。

## Codex / Hermes
- 配置格式**未核实**：请查阅各自官方文档（MCP server 支持与配置文件字段），
  启动参数一律用上面的「通用启动参数」，不要凭记忆编造格式。
- Codex 参考方向：config.toml 中 mcp 相关配置；Hermes：查阅其 MCP 文档。

## DeepSeek Harness（DSH）
- 本项目使用者即 DSH 插件开发者，**配置由使用者本人提供**（本项目 README 已声明与 DSH 无关，
  server 本身是标准 MCP stdio server，任何客户端按同一协议接入）。

## Agent 看图方式（README 约定）
- DeepSeek Harness：`read_image` 工具读 `__image__` 返回的绝对路径
- Claude Code：`Read` 工具读同一路径
- 其余客户端：用各自的文件读取/图片查看能力读 `__image__` 路径

## v1.1.0 客户端接入面变更（升级必读）

1. **机器可读错误码**：失败返回新增 `error_code` 字段
   （`{status:"error", error_code:"E****", message:"..."}`，码表见 SPEC 第 9 节）。
   agent 可按码分支：E1001/E1008/E1009 → 改参数重试；E1005 → 缩减数据；
   E1010/E1011 → 换方法或补数据。纯增量字段，旧客户端零影响。
2. **resources 能力**：server 静态枚举 `statlab://spec`（协议全文）与
   `statlab://tools/<工具名>/manual`（完整说明书），共 28 项。支持 resources 的客户端
   直接读取；不支持的客户端行为不变（工具 docstring 仍是完整说明书）。
3. **description 双轨开关**：环境变量 `STATLAB_DESC_MODE=full|slim`，默认 full 与
   v1.0.3 一致；slim 时 tools/list 的 description 仅保留参数签名摘要，
   完整说明书经 manual 资源获取。
4. **图片双轨**：环境变量 `STATLAB_IMAGE_MODE=path|content`，默认 path（`__image__`
   路径字段，与此前一致）；content 返回标准 MCP ImageContent 内容块（base64），
   有上下文膨胀风险，仅建议支持图片渲染的交互式客户端启用（SPEC 第 5 节强制披露）。

> 提示：<PROJECT_ROOT> 请替换为你的项目根绝对路径（本文件已脱敏，勿提交本机路径）。

