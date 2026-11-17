# 截图处理规则（screenshot-rules）

## 一、来源判定（决定是否执行 S2）

```
有测试案例 xlsx           → figures.source = testcase      （必须执行取图）
无测试案例，需求文档有界面图 → figures.source = requirement-doc（可用图示，注明"需求文档示意"）
两者都没有                → figures.source = none          （全部占位）
```

注意：req-doc2md 对 xlsx 中**漂浮截图**常报"图片 0"。判定前必须解压检查：

```bash
unzip -l "案例.xlsx" | grep -E "xl/media|xl/drawings"
```

## 二、取图与锚点映射

```bash
python scripts/manual.py extract "案例.xlsx" --out work/extract
```

产出：
- `case_rows.txt`：各 sheet 的用例行（含"截图对应行数"列）
- `imgs/imageN.png`：全部内嵌图片
- `anchors_<sheet>_<drawing>.csv`：`ref,excel_row,col,img`
- `ref_image_map.csv`：按 sheet 区分（`sheet,ref,img`）与逐 sheet 的 `refmap_<sheet>.csv`
- `contact/sheet_XX.png`：缩略图拼版（带文件名），用于目视挑图

映射规则：测试案例中的 `截图!A{n}` 对应 `ref=A{n}`；Excel 实际行号 = n+1（锚点 0 基与 1 基的偏移）。**不同 sheet 的 A1 是不同图**，必须按 sheet 限定。

## 三、选图流程（人工/模型目视）

1. 打开 contact 拼版，按需求点找对应界面（按模块/页面标题识别）；
2. 每个需求点挑 1~3 张：入口、关键配置、校验提示/结果；
3. 不看用例文字盲信引用——截断/错位常见，**以图片内容为准**；
4. 把选择写入 `figures.json`：

```json
[
  {"src": "work/extract/imgs/image9.png",  "dst": "fig2_1_hosp_group.png"},
  {"src": "work/extract/imgs/image151.png","dst": "fig7_2_supp_hosp.png", "crop_top": 90}
]
```

5. 执行裁剪/重命名：

```bash
python scripts/manual.py prep --map figures.json --out <手册目录>/assets
```

裁剪约定：
- 浏览器截图 `crop_top≈90` 去掉标签页/地址栏；
- 只截关键区域时用 `crop_box:[x0,y0,x1,y1]`；
- 长图可 `max_width` 限制宽度，避免 docx 溢出。

## 四、占位规则

未取到图的需求点写：

```python
placeholder(doc, '建议补充：<具体场景>截图（测试案例中未提供）。')
```

- 渲染为红色虚线框【截图待补充】；
- 一个需求点可有多条占位；
- 汇总到附录（manifest.appendix 或 merge 自动汇总）。

## 五、合规提醒

- 截图可能含水印/测试环境地址/客户信息：正式发布前需脱敏或替换；
- 需求文档中的红框批注图可作为"需求文档示意"，但图注需注明来源；
- 同一张图不要跨需求点重复使用（确需复用时在图注说明）。
