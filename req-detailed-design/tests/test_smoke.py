"""Dependency-free smoke tests for extract_context.py.

Run with: python tests/test_smoke.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'scripts'))

import extract_context as ec  # noqa: E402


def _write(path: Path, text: str, encoding: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode(encoding))


def test_gbk_java():
    """GBK 编码 Java：中文注释不乱码，行号范围正确。"""
    lines = [f'\t// 中文注释 第{i}行' if i % 3 == 0 else f'\tint v{i} = {i};'
             for i in range(1, 21)]
    lines[11] = '\tcaseinfo += "&enterpriseFlag=" + enterpriseFlag;'  # 第12行
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / 'Demo.java'
        _write(f, '\n'.join(lines), 'gbk')
        out, err = ec.run_one({'file': str(f), 'anchor': 'enterpriseFlag'})
        assert out, err
        # 定位行：:7-17（第12行前后各5行）
        assert ':7-17' in out, out
        # 中文正常（GBK 回退解码成功）
        assert '中文注释' in out, out
        # 行号前缀存在且覆盖 7..17
        for n in (7, 12, 17):
            assert f'{n}\t' in out, out
        # 行数 = before + 1 + after
        body = [ln for ln in out.splitlines() if ln and ln[0].isdigit()]
        assert len(body) == 11, body


def test_utf8_xml():
    """UTF-8 XML：不误判编码，原文完整。"""
    lines = [f'\t<!-- 注释{i} --><a id="{i}"/>' for i in range(1, 11)]
    lines[4] = '\t<result column="ISSPECIAL" jdbcType="VARCHAR" property="ISSPECIAL" />'
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / 'Mapper.xml'
        _write(f, '\n'.join(lines), 'utf-8')
        out, err = ec.run_one({'file': str(f), 'anchor': 'ISSPECIAL'})
        assert out, err
        assert '<!-- 注释' in out, out
        assert 'ISSPECIAL' in out, out
        assert 'UTF-8' not in out.split('\n')[0]  # utf-8 不触发转码告警
        assert ':1-10' in out, out


def test_path_with_spaces():
    """路径含空格/中文：能正常读取。"""
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / '目录 带空格' / '文件 名.js'
        _write(f, 'var a = 1;\nvar target = 2;\nvar c = 3;\n', 'utf-8')
        out, err = ec.run_one({'file': str(f), 'anchor': 'target'})
        assert out, err
        assert 'target' in out, out
        assert '目录 带空格' in out, out


def test_anchor_by_line_number():
    """锚点 :N 直接按行号定位。"""
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / 'a.sql'
        _write(f, '\n'.join(f'select {i} from dual;' for i in range(1, 8)), 'utf-8')
        out, err = ec.run_one({'file': str(f), 'anchor': ':4', 'before': 1, 'after': 1})
        assert out, err
        assert ':3-5' in out, out
        assert 'select 4 from dual;' in out, out


def test_anchor_not_found():
    """锚点未找到：返回错误而不是空块。"""
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / 'b.txt'
        _write(f, 'hello\nworld\n', 'utf-8')
        out, err = ec.run_one({'file': str(f), 'anchor': '不存在的内容'})
        assert out is None
        assert '锚点未找到' in err, err


def test_multiple_hits_note():
    """多处命中：输出提示并取第一处。"""
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / 'c.java'
        _write(f, 'x\nTARGET\ny\nTARGET\nz\n', 'utf-8')
        out, err = ec.run_one({'file': str(f), 'anchor': 'TARGET'})
        assert out, err
        assert '命中 2 处' in out, out


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t()
            print(f'PASS {t.__name__}')
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f'FAIL {t.__name__}: {e}')
    print(f'\n{len(tests) - failed}/{len(tests)} passed')
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
