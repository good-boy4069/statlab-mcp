# -*- coding: utf-8 -*-
"""一次性（T3c/B4 收尾）：对基线外的新工具（backtest）与其余三文件做
连锁 optional 化 + inline 签名/分派/返回注入（与 _t3_batch 同规约）。
required 来源 = 现有签名无默认值参数（AST 解析）。跑完自删。"""
import ast
from pathlib import Path

TOOLS = Path(__file__).resolve().parent / "statlab_mcp" / "tools"
DOC_BLOCK = (
    "\ninline 数据:\n"
    "    本工具支持可选 inline_data 参数（v1.2.0 起）：与 file_path 二选一，\n"
    "    支持 records 数组或 {\"header\": [...], \"rows\": [[...], ...]} 对象两种形态；\n"
    "    规模上限/类型域/data_source 来源标注见 statlab_mcp/docs/SPEC.md 第 12 节。\n")


def required_params(src: str) -> tuple[str, list[str]]:
    """返回 (主函数名, 无默认值参数列表)。主函数=非下划线/非 register 且 -> dict。"""
    tree = ast.parse(src)
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef)
              and not n.name.startswith("_") and n.name != "register")
    pos = fn.args.args
    ndef = len(fn.args.defaults)
    reqs = [a.arg for a in pos[:-ndef]] if ndef else [a.arg for a in pos]
    reqs = [r for r in reqs if r != "file_path"]
    return fn.name, reqs


for name in ("timeseries_backtest_forecast", "timeseries_seasonal_decompose",
             "timeseries_trend_analysis", "timeseries_anomaly_detect"):
    fp = TOOLS / (name + ".py")
    src = fp.read_text(encoding="utf-8")
    if "inline_data: list | dict | None = None" in src:
        print("skip", name)
        continue

    fn_name, reqs = required_params(src)
    print(f"{name}: fn={fn_name} required(no-file)={reqs}")

    # 1) required 参数 optional 化（跳过 file_path）
    for pname in reqs:
        pat = ast  # 占位避免 lint;实际用文本级替换（注解文本各行已知简单）
    # 文本级：'param: TYPE,' 或 'param: TYPE)' → '| None = None'
    for pname in reqs:
        import re as _re
        pat = _re.compile(rf"\b{_re.escape(pname)}:\s*([^,\n]+?)(?=[,)])")
        m_p = pat.search(src)
        assert m_p, f"{name}: 未找到 {pname} 注解"
        if "| None =" in m_p.group(0):
            continue
        src = src[:m_p.start()] + f"{pname}: {m_p.group(1)} | None = None" + \
            src[m_p.end():]

    # 2) file_path 可选化
    if "file_path: str | None = None" not in src:
        src = src.replace("file_path: str,", "file_path: str | None = None,", 1)

    # 3) inline_data 形参（闭合括号前）
    m_close = re.search(r"\) -> dict:", src) if False else None
    import re as _re2
    m_close = _re2.search(r"\) -> dict:", src)
    assert m_close, f"{name}: 未找到 ') -> dict:'"
    prev_char = src[:m_close.start()].rstrip()[-1]
    if prev_char == ",":
        src = (src[:m_close.start()] +
               "\n                   inline_data: list | dict | None = None" +
               src[m_close.start():])
    else:
        src = (src[:m_close.start()] +
               ",\n                   inline_data: list | dict | None = None" +
               src[m_close.start():])

    # 4) read_table → resolve_data
    var = _re2.search(r"(\w+) = read_table\(file_path\)", src).group(1)
    src = src.replace(f"{var} = read_table(file_path)",
                      f"{var}, data_source = resolve_data(file_path, inline_data)", 1)

    # 5) 成功返回注入
    m_ret = _re2.search(r"^(\s*)return ok\(([^\n]*)\)\s*$", src, flags=_re2.M)
    m_pl = _re2.search(r"^( *)(\w+) = ok\(([^\n]*)\)\s*$", src, flags=_re2.M)
    if m_ret:
        indent, args = m_ret.group(1), m_ret.group(2)
        src = (src[:m_ret.start()] +
               f"{indent}_payload = ok({args})\n"
               f'{indent}_payload["data_source"] = data_source\n'
               f"{indent}return _payload" + src[m_ret.end():])
    elif m_pl:
        indent, var_name, args = m_pl.group(1), m_pl.group(2), m_pl.group(3)
        src = (src[:m_pl.start()] + f"{indent}{var_name} = ok({args})\n"
               + f'{indent}{var_name}["data_source"] = data_source'
               + src[m_pl.end():])
    else:
        raise SystemExit(f"{name}: 未找到成功返回点")

    # 6) require_non_none 注入（try 前；backtest 无 reqs→跳过）
    if reqs:
        m_try = _re2.search(r"^(\s*)try:", src, flags=_re2.M)
        assert m_try, f"{name}: 未找到 try"
        ind = m_try.group(1)
        call_args = ", ".join(f"{p_}={p_}" for p_ in reqs)
        src = (src[:m_try.start()] +
               f"{ind}# D17 连锁 optional 化的运行期强校验（SPEC §12.6）\n"
               + f"{ind}require_non_none({call_args})\n" + src[m_try.start():])

    # 7) docstring 块
    close_idx = src.find('\n"""')
    assert close_idx != -1
    src = src[:close_idx] + DOC_BLOCK + src[close_idx:]

    # 8) import 注入
    m_single = _re2.search(r"^from statlab_mcp\.tools\._common import ([^\n(]+)$", src, flags=_re2.M)
    m_multi = _re2.search(r"^from statlab_mcp\.tools\._common import \(\n", src, flags=_re2.M)
    need = {"resolve_data", "require_non_none"}
    if m_multi:
        src = src[:m_multi.end()] + "    resolve_data,\n    require_non_none,\n" + src[m_multi.end():]
    elif m_single:
        names = [x.strip() for x in m_single.group(1).split(",")]
        names = sorted(set(names) | need, key=lambda s: s.lower())
        line = "from statlab_mcp.tools._common import " + ", ".join(names)
        src = src[:m_single.start()] + line + src[m_single.end():]
    else:
        raise SystemExit(f"{name}: import 未找到")

    fp.write_text(src, encoding="utf-8")
    print(f"transformed {name}")
print("B4-REST-DONE")
