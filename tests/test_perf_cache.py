"""tests/test_perf_cache.py —— v1.1.0 P1-1：延迟导入 + read_table 文件缓存验收。

钉死验收：
1. 同一文件连续调用 2 个不同工具，两次 result 逐字节一致，且与禁用缓存
   （STATLAB_NO_CACHE=1）的输出一致（缓存透明性）；
2. 廉价键 mtime/size 变化触发重新解析；mtime 伪造（内容变、size/mtime 不变）
   被 SHA256 校验拦截；
3. 容量上限 8 条目 LRU 淘汰；STATLAB_NO_CACHE 非法取值 stderr 中文告警并忽略；
4. 并发两线程同时首调同一文件无异常；
5. 冷启动不加载 pmdarima/sklearn/statsmodels（固定清单延迟导入）。
"""
import hashlib
import json
import os
import sys
import threading
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from statlab_mcp.tools import _common as C
from statlab_mcp.tools import data_exploration_describe_statistics as ds_mod
from statlab_mcp.tools import data_exploration_missing_report as mr_mod

CLEAN = str(ROOT / "samples" / "clean.csv")
DIRTY = str(ROOT / "samples" / "dirty.csv")


def _dump(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")


def _clear_cache():
    with C._cache_lock:
        C._cache_cheap.clear()


def test_two_tools_same_file_cache_transparent(tmp_path):
    """同一文件连续调用两个工具，命中与未命中、禁用缓存三方输出逐字节一致。"""
    df = pd.DataFrame({"v": [1.0, 2.0, 3.0, 4.0], "g": ["a", "b", "a", "b"]})
    p = tmp_path / "t.csv"
    df.to_csv(p, index=False)
    _clear_cache()
    a1 = ds_mod.describe_statistics(str(p))
    b1 = mr_mod.missing_report(str(p))
    # 第二轮：两个工具全部走廉价键+SHA 命中路径
    a2 = ds_mod.describe_statistics(str(p))
    b2 = mr_mod.missing_report(str(p))
    assert _dump(a1) == _dump(a2)
    assert _dump(b1) == _dump(b2)
    # 禁用缓存直读对照
    os.environ["STATLAB_NO_CACHE"] = "1"
    try:
        a0 = ds_mod.describe_statistics(str(p))
        b0 = mr_mod.missing_report(str(p))
    finally:
        os.environ.pop("STATLAB_NO_CACHE", None)
    assert _dump(a0) == _dump(a1)
    assert _dump(b0) == _dump(b1)


def test_mtime_or_size_change_reparse(tmp_path):
    df = pd.DataFrame({"v": [1.0, 2.0]})
    p = tmp_path / "m.csv"
    df.to_csv(p, index=False)
    _clear_cache()
    first = C.read_table(str(p))
    assert len(first) == 2
    st = p.stat()
    # 内容变化 + 显式回拨 mtime 与保持 size 不变 → 伪造廉价键，必须被 SHA 拦截
    (p).write_text("v\n9\n8\n7\n", encoding="utf-8")   # size 变了 → 先改造成同尺寸再回拨
    now_bytes = p.read_bytes()
    old_size = st.st_size
    if len(now_bytes) != old_size:                     # 补齐到旧尺寸以强制走 SHA 分支
        pad = ("\n" * max(0, old_size - len(now_bytes)))
        p.write_bytes(now_bytes + pad.encode("ascii"))
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))   # 回拨到旧 mtime
    r2 = C.read_table(str(p))
    assert int(r2["v"].iloc[0]) == 9                   # 读到新内容（SHA 拦截旧条目）


def test_capacity_lru_eviction(tmp_path):
    _clear_cache()
    paths = []
    for i in range(9):
        p = tmp_path / f"f{i}.csv"
        pd.DataFrame({"v": [float(i)]}).to_csv(p, index=False)
        paths.append(str(p))
    for s in paths:
        C.read_table(s)
    with C._cache_lock:
        keys = list(C._cache_cheap.keys())
        assert len(keys) <= C._CACHE_MAX_ENTRIES       # ≤8 条目
        present_first = any(
            k[0] == os.path.normcase(str(Path(paths[0]).resolve())) for k in keys)
    assert not present_first                           # 最老的 f0 已被 LRU 淘汰


def test_no_cache_env_invalid_warns_ignore(capsys):
    os.environ["STATLAB_NO_CACHE"] = "maybe"
    try:
        disabled = C._cache_disabled_by_env()
    finally:
        os.environ.pop("STATLAB_NO_CACHE", None)
    assert disabled is False                            # 非法取值：忽略设置（缓存照常）
    err_out = capsys.readouterr().err
    assert "STATLAB_NO_CACHE" in err_out and "非法" in err_out


def test_concurrent_first_call_same_file():
    _clear_cache()
    results, errors = [], []

    def worker():
        try:
            results.append(C.read_table(CLEAN))
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert len(results) == 2
    assert results[0].shape == results[1].shape


def test_lazy_import_heavy_libs_not_loaded_on_boot():
    """子进程冷启动：import server 并 list_tools 后，三库仍不得出现在 sys.modules。"""
    import subprocess
    code = (
        "import sys, asyncio;"
        "import statlab_mcp.server as s;"
        "asyncio.run(s.mcp.list_tools());"
        "bad = [m for m in ('pmdarima', 'sklearn', 'statsmodels') if m in sys.modules];"
        "print('LAZY-OK') if not bad else print('LOADED:' + ','.join(bad))"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT),
                         capture_output=True, text=True, encoding="utf-8",
                         errors="replace",
                         env={**os.environ, "PYTHONUTF8": "1"})
    assert out.returncode == 0, out.stderr[-800:]
    assert "LAZY-OK" in out.stdout, out.stdout[-400:]


def test_sha_helper_matches_hashlib_reference(tmp_path):
    """手算对照：SHA256 助手与标准库 hashlib 对同一文件结果一致。"""
    p = tmp_path / "h.csv"
    p.write_bytes(b"a,b\n1,2\n")
    assert C._sha256_of_file(str(p)) == \
        hashlib.sha256(p.read_bytes()).hexdigest()
