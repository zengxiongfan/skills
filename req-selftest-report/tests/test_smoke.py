# -*- coding: utf-8 -*-
"""冒烟测试：用两份结构不同的样例 xlsx 验证 自适应解析 → 选案抽图 → 组版。

运行（须用装依赖的 Python 3.10）：
  python tests/test_smoke.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile

from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'scripts')


def make_png(path, size=(320, 120), color=(70, 120, 200)):
    Image.new('RGB', size, color).save(path)


def make_case_a(path, png):
    """结构A：标准列名 + 截图表名"截图" + 引用 '截图!A9'（锚点 B10，验证 n+1 规则）。"""
    wb = Workbook()
    ws = wb.active
    ws.title = 'NHB保单福利配置'
    ws.append(['路径', '测试案例编号', '模块', '测试项', '测试案例标题', '重要级别',
               '操作步骤', '输出', '实际输出', '测试状态', '截图对应行数'])
    ws.append(['', 'T-01', '模块A', '测试项A1', '方案层配置要素', '高',
               '1、【配置】\n2、方案层配置成功', '设置成功', '保单：P001', '测试通过', '截图!A9'])
    ws.append(['', 'T-02', '模块A', '', '险种层配置要素', '高',
               '1、【配置】\n2、险种层配置成功', '设置成功', '保单：P001', '测试通过', '截图!A9'])
    ws2 = wb.create_sheet('截图')
    ws2.add_image(XLImage(png), 'B10')
    wb.save(path)


def make_case_b(path, png):
    """结构B：非标准列序/别名/引用写法 'A9' + 表头不在首行 + 工作表名不同。"""
    wb = Workbook()
    ws = wb.active
    ws.title = 'TestCases'
    ws.append(['RCP-00000 测试案例（标题横幅行）'])
    ws.append(['模块', '测试案例标题', '优先级', '执行步骤', '预期结果', '实际结果',
               '执行结果', '截图链接'])
    ws.append(['模块B', '查询条件校验', '高', '1、点击查询', '查询成功',
               '案件号：G001', '测试通过', 'A9'])
    ws2 = wb.create_sheet('图1')
    ws2.add_image(XLImage(png), 'B10')
    wb.save(path)


def run(cmd):
    print('>', ' '.join(os.path.basename(c) if os.path.isabs(c) else c for c in cmd))
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        raise SystemExit(f'命令失败: {cmd[1]}')
    return r.stdout


def main():
    tmp = tempfile.mkdtemp(prefix='selftest_report_')
    png = os.path.join(tmp, 'shot.png')
    make_png(png)
    xa = os.path.join(tmp, '案例A.xlsx')
    xb = os.path.join(tmp, '案例B.xlsx')
    make_case_a(xa, png)
    make_case_b(xb, png)

    # ---- 阶段0 解析 ----
    data_path = os.path.join(tmp, 'iter_data.json')
    run([sys.executable, os.path.join(SCRIPTS, 'parse_cases.py'),
         '--xlsx', xa, xb, '--out', data_path])
    data = json.load(open(data_path, encoding='utf-8'))
    assert len(data['cases']) == 3, f"案例数应为3，实际{len(data['cases'])}"
    mods = {c['module'] for c in data['cases']}
    assert mods == {'模块A', '模块B'}, mods
    assert data['files'][1]['header_row'] == 2, 'B文件表头应在第2行'
    with_img = [c for c in data['cases'] if c['images']]
    assert len(with_img) == 3, f'带图案例应为3，实际{len(with_img)}'
    assert all(c['item'] for c in data['cases'] if c['module'] == '模块A'), '测试项应前向填充'
    assert all(not c['item'] for c in data['cases'] if c['module'] == '模块B'), '无测试项列时应降级为空'
    print(f'[OK] 解析: 3案例/2模块/3图; 表头行={[f["header_row"] for f in data["files"]]}')

    # ---- 阶段2 选案抽图 ----
    picks = [{'module': '模块A', 'rows': [2, 3]}, {'module': '模块B', 'rows': [3]}]
    picks_path = os.path.join(tmp, 'picks.json')
    json.dump(picks, open(picks_path, 'w', encoding='utf-8'), ensure_ascii=False)
    assets = os.path.join(tmp, 'report_assets')
    selected_path = os.path.join(tmp, 'selected.json')
    run([sys.executable, os.path.join(SCRIPTS, 'pick_cases.py'),
         '--data', data_path, '--picks', picks_path,
         '--outdir', assets, '--out', selected_path])
    selected = json.load(open(selected_path, encoding='utf-8'))
    assert len(selected) == 3, len(selected)
    assert all(c['exported'] for c in selected), '每个选中案例应有导出图'
    assert selected[0]['dup_of_prev'] is False and selected[1]['dup_of_prev'] is True, \
        '共用同一图应标记 dup_of_prev'
    print(f'[OK] 选案: 3案例全部出图, 共用图标记={[c["dup_of_prev"] for c in selected]}')

    # ---- 阶段4 组版 ----
    spec = {
        'header': {'req_title': 'RCP-99999--测试需求', 'tester': '张三', 'submit_date': 'auto'},
        'sections': [
            {'title': '1.1模块A',
             'intro': '模块A功能说明。',
             'cases': [
                 {'label': 'RCP-99999-01 方案层配置要素：', 'desc': '配置成功（保单号：P001）。',
                  'image': selected[0]['exported'][0]},
                 {'label': '险种层配置要素：', 'desc': '配置成功（执行截图同上）。'},
             ]},
            {'title': '1.2模块B',
             'intro': '模块B功能说明。',
             'cases': [
                 {'label': '查询条件校验：', 'desc': '查询成功（案件号：G001）。',
                  'image': selected[2]['exported'][0]},
                 {'label': '无图案例：', 'desc': '字段展示正确。', 'note': '（执行截图待补充）'},
             ]},
        ],
    }
    spec_path = os.path.join(tmp, 'report.json')
    json.dump(spec, open(spec_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    out_docx = os.path.join(tmp, '报告-已填写.docx')
    run([sys.executable, os.path.join(SCRIPTS, 'build_report.py'),
         '--spec', spec_path, '--out', out_docx])

    from docx import Document
    doc = Document(out_docx)
    texts = [p.text for p in doc.paragraphs]
    assert any('1.1模块A' in t for t in texts), '缺少 1.1 节标题'
    assert any('1.2模块B' in t for t in texts), '缺少 1.2 节标题'
    bad = [t for t in texts if re.search(r'RCP-\d+-\d+', t)]
    assert not bad, f'正文不应出现案例编号: {bad[:2]}'
    assert any('（执行截图待补充）' in t for t in texts), '缺少待补充标注'
    assert len(doc.inline_shapes) == 2, f'应有2张图，实际{len(doc.inline_shapes)}'
    header_cell = doc.tables[0].cell(0, 0).text
    assert 'RCP-99999--测试需求' in header_cell, header_cell
    assert doc.tables[0].cell(2, 3).text == '测试通过', '测试结论默认值错误'
    print('[OK] 组版: 表头填充/正文编号剥离/待补充标注/图片数量全部通过')

    print('\nSMOKE TEST PASSED ->', tmp)


if __name__ == '__main__':
    main()
