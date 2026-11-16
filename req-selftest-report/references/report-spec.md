# report.json 结构契约（req-selftest-report reference）

`report.json` 是 `build_report.py` 的**唯一输入**，也是每次迭代的配置留档。改版时只改它、重跑脚本，不碰代码。

## 顶层

```json
{
  "header": { ... },
  "sections": [ ... ]
}
```

## header

| 字段 | 类型 | 说明 | 默认 |
|------|------|------|------|
| `req_title` | string | 需求编号+名称，写入表格首行 | 空 |
| `tester` | string | 测试人；**默认留空由人工填** | 空 |
| `submit_date` | string | `auto` 或缺省 = 当天；也可写 `2026/09/18` | `auto` |
| `modules` | string | 表头"模块"单元格；**留空**由人工补 | `""` |
| `verdict` | string | 测试结论（模板固定值，渲染为绿色） | `测试通过` |
| `env` | string | 测试环境（模板固定值） | `DEV测试环境 localhost:8080` |

> `tester` / `modules` 不要从同目录 SIT 测试报告里抄真实值；`verdict` / `env` 不要替换成 SIT 真实环境地址。

## sections[]

| 字段 | 类型 | 说明 |
|------|------|------|
| `title` | string | 节标题，如 `1.1新福利配置页调整`（首节会替换模板里的 `1.1` 占位段落） |
| `intro` | string | 功能说明段落（可空） |
| `cases[]` | array | 案例列表 |

### cases[]

| 字段 | 类型 | 说明 |
|------|------|------|
| `label` | string | 加粗案例标签，以`：`结尾；**不要带 `RCP-xxx-xx` 编号**（带了也会被剥离） |
| `desc` | string | 案例描述（来自案例原始字段：步骤/输出/实际输出，可含保单号/案件号） |
| `image` | string? | 截图相对/绝对路径；缺省表示无图 |
| `note` | string? | 附加说明；若 `desc` 里没有该文本会自动追加（如 `（执行截图待补充）`） |

## 行为约定

1. **编号剥离**：`label` 开头匹配 `^RCP-\d+-\d+\s*` 会被删除。
2. **共用截图**：同一张图被两个案例引用时，第二个案例不要给 `image`，在 `desc` 末尾写 `（执行截图同上）`。
3. **无图模块**：不给 `image`，在 `desc`/`note` 里写明 `（执行截图待补充）`，或用"实际输出"数据写纯文字。
4. **图片缺失**：`image` 路径不存在时脚本跳过该图并打印 `WARNING missing images`，构建不中断。
5. **幂等**：每次运行都从模板重建，输出文件可放心覆盖。

## 完整示例

见 `assets/report_spec.example.json`。
