# 数据探查组 · 接口设计文档（批 1）

> 交付物：describe_statistics / data_type_check / missing_report 三个工具的完整接口定义。
> 批 2（correlation_matrix / outlier_detect）含 p 值校正与图协议，另行交付。
> 统计定义已由红队裁决钉死（docs/SPEC.md 增补 1-2）：分位数=linear 插值（Excel QUARTILE.INC 等价）；
> 偏度=scipy.stats.skew(x, bias=False)；峰度=scipy.stats.kurtosis(x, fisher=True, bias=False)；std=ddof=1（Excel STDEV.S）。

## 全局约定（三工具共用）
- 所有参数第一层校验失败返回 `{"status":"error","message":"中文原因"}`，error 时禁止携带 result 字段
- 所有数值经 to_jsonable() 输出 Python 原生类型；NaN/Infinity 一律输出 null（JSON 中为 None）
- summary 由代码模板拼数字生成，禁止 LLM 生成文字
- 同一文件两次调用结果一致（全局 seed=42；本批工具无随机性）
- 公共边界行（read_table 层）：文件不存在 / 空文件 / 仅表头（无数据行）/ 非白名单格式 / 编码无法识别 / 超过 50MB / 超过 200 万行 —— 已在 tools/_common.py 统一拦截

---

# 工具 1：describe_statistics(file_path)

一句话用途：对数据文件的**每一列**输出描述性统计（n/均值/中位数/标准差/分位数/偏度/峰度/缺失数），是数据探查的第一块敲门砖。

## 参数表（仅 1 个参数）
| 参数名 | 类型 | 默认值 | 校验规则 | 例子 |
|---|---|---|---|---|
| file_path | str | 必填 | 本地 csv/tsv/xlsx/json 绝对或相对路径；空串、非字符串、UNC 开头（\\、//、\\?\、\.\）拒绝 | `"data/clean.csv"` |

## 返回（成功）
```jsonc
{
  "status": "ok",
  "result": {
    "n_rows": 50, "n_columns": 6,
    "numeric_columns": ["id", "age", "score", "income"],   // 参与统计的列
    "non_numeric_columns": ["category", "date"],           // 忽略并在 summary 注明
    "fully_missing_columns": [],                            // 全缺失列名
    "columns": {
      "score": {
        "n": 50, "mean": 71.28, "median": 70.55, "std": 11.93,
        "min": 45.1, "q1": 63.34, "q3": 80.02, "max": 96.4,
        "skew": -0.11, "kurtosis": -0.72, "n_missing": 0
      }
    }
  },
  "summary": "共 50 行 6 列；数值列 4 个，其中 score 均值 71.28（±11.93），缺失 0；非数值列 2 个（category, date）已忽略"
}
```
字段说明（英文固定键名，数值键一律 float|int|null）：
| 键 | 类型 | 说明 |
|---|---|---|
| n_rows / n_columns | int | 表规模 |
| numeric_columns / non_numeric_columns / fully_missing_columns | list[str] | 列角色划分 |
| columns.<列名>.n | int | 非缺失有效值个数（全缺序列 = 0） |
| mean / median / min / max / q1 / q3 | float\|null | 有效值统计；q1/q3 为 linear 插值（=Excel QUARTILE.INC） |
| std | float\|null | ddof=1（=Excel STDEV.S）；n<2 或全缺失 → null |
| skew / kurtosis | float\|null | Fisher 偏度 / 超额峰度（正态=0）；n<3、常数列（std=0）或全缺失 → null |
| n_missing | int | 该列缺失（含空串被 pandas 读为 NaN）个数 |

## 边界行为表（本工具专属 + 全局）
| 场景 | 行为 |
|---|---|
| 全缺失列 | 保留键：n=0、n_missing=总行数、其余统计键全 null；summary 注明"列 xxx 全缺失" |
| 列含空单元格 | 按有效值计算并计入 n_missing（如 50 行缺 2 → n=48, n_missing=2） |
| 无任何数值列（全文本表） | error："未找到数值列，无法计算描述统计" |
| 全缺失数值列 + 其他正常列 | 正常列照常输出，全缺失列按上表处理，不中断 |
| 常数列（std=0） | std=0；skew/kurtosis=null（方差为 0 无法定义），summary 注明"列 xxx 为常数列" |
| n=1（单行文件） | std/q1/q3/skew/kurtosis=null；mean/median/min/max 正常 |
| 重复列名 | pandas 自动改名（a → a, a.1），summary 注明"列名重复已自动改名" |
| 中文列名 / 含空格列名 | JSON 键原样输出（UTF-8），正常计算 |
| 极端值 1e9 | 照常计入统计（不剔除），体现在 max/mean 中，不报错 |
| 非数值字符串列 | 忽略统计，进 non_numeric_columns |
| 文件不存在 / 空文件 / 格式非白名单 | error（全局公共消息） |

## 错误路径（≥3 种，中文提示）
1. `文件不存在或不可访问: xxx.csv`（read_table 层）
2. `未找到数值列，无法计算描述统计`（全文本表）
3. `仅支持 ['csv', 'json', 'tsv', 'xlsx'] 格式，当前为 md，请转换后重试`
4. `文件为空或无可读数据`（0 字节或仅表头）

## 验证命令与预期值来源（可复算）
```powershell
& .\.venv\Scripts\python.exe -c "from statlab_mcp.tools.data_exploration_describe_statistics import describe_statistics; import json; print(json.dumps(describe_statistics('samples/clean.csv'), ensure_ascii=False, indent=1))"
```
- 复算小例（Excel 可验证）：数据列 [1,2,3,4] 期望 mean=2.5、median=2.5、std=1.290994（STDEV.S）、min=1、max=4、q1=1.75、q3=3.25（QUARTILE.INC）
- skew/kurtosis 以 pytest 断言值为准（Excel SKEW/KURT 公式口径一致，但 n<30 小数位不同，不用于验收）
- 阈值解释：p<0.05 不适用本工具；本工具无假设检验

---

# 工具 2：data_type_check(file_path)

一句话用途：识别每一列的数据类型（数值/整数/日期/类别/文本/混合脏数据），为后续工具选型与数据清洗提供依据。

## 参数表（仅 1 个参数）
| 参数名 | 类型 | 默认值 | 校验规则 | 例子 |
|---|---|---|---|---|
| file_path | str | 必填 | 同全局约定 | `"data/dirty.csv"` |

## 类型判定规则（确定性代码）
1. pandas 数值 dtype → 数值；若该列所有值均为整数 → 整数（如 id）
2. 字符串/object 列：先试 to_datetime（errors="coerce"）→ 成功比例 ≥95% → 日期（并统计无法解析的非法日期个数）
3. 未过日期判定：再试 to_numeric（errors="coerce"）→ 若部分可转数字 → **混合**（注明脏值个数，如 "1,000"、"3kg"、空串）
4. 其余：唯一值数 ≤ min(50, 行数×20%) → 类别（附 top3 取值）；否则 → 文本
5. 全缺失列 → 类型 "missing"，不进以上判定
6. 已知难以解析的日期（如 2024-02-30）→ to_datetime 失败计入非法日期数，该列仍判为日期（若合法部分 ≥95%），或判混合

## 返回（成功）
```jsonc
{
  "status": "ok",
  "result": {
    "n_rows": 20, "n_columns": 5,
    "columns": {
      "value":    {"detected_type": "numeric", "n_valid": 18, "n_missing": 2, "dirty_count": 0, "note": null},
      "empty_col":{"detected_type": "missing", "n_valid": 0,  "n_missing": 20, "dirty_count": 0, "note": "全缺失列"},
      "bad_date": {"detected_type": "date",    "n_valid": 19, "n_missing": 0, "dirty_count": 1, "note": "含 1 个无法解析的日期（如 2024-02-30）"},
      "extreme":  {"detected_type": "numeric", "n_valid": 19, "n_missing": 1, "dirty_count": 0, "note": null}
    },
    "issue_summary": {"dirty_value_columns": ["bad_date"], "fully_missing_columns": ["empty_col"]}
  },
  "summary": "共 20 行 5 列；数值 2 列、日期 1 列（含 1 个非法日期）、全缺失 1 列；建议先处理 empty_col 与 bad_date"
}
```
字段说明：
| 键 | 类型 | 说明 |
|---|---|---|
| columns.<列名>.detected_type | str | numeric / integer / category / date / text / mixed / missing |
| n_valid / n_missing / dirty_count | int | 有效值 / 缺失 / 脏值（无法转换或非法日期）个数 |
| note | str\|null | 一句话说明（如非法日期示例、常见取值 top3） |
| issue_summary | dict | 汇总：mixed_columns / fully_missing_columns / invalid_date_columns |

## 边界行为表
| 场景 | 行为 |
|---|---|
| 中文列名 | 正常识别，键原样输出 |
| 空单元格 | 计入 n_missing；不影响类型判定（如 50 行缺 2 的数值列仍判 numeric） |
| 全缺失列 | detected_type="missing"，不参与任何转换尝试 |
| 数值文本混合列（"1,000"/"3kg"） | detected_type="mixed"，dirty_count=脏值个数，note 给示例 |
| 非法日期 2024-02-30 | 计入 invalid_date_columns；该列仍判 date（合法部分 ≥95%） |
| 重复列名 | 自动改名并在 summary 注明 |
| 单行文件 | 按规则正常判定（类别阈值取 min(50, 1×20%)=1） |
| 极端值 1e9 | 数值列正常识别，不视为脏值 |

## 错误路径（≥3 种）
1. `文件不存在或不可访问: xxx.csv`
2. `仅支持 ['csv', 'json', 'tsv', 'xlsx'] 格式...`
3. `文件为空或无可读数据`
4. `文件解析失败: ...`（文件损坏等，read_table 层兜底）

## 验证命令与预期值来源
```powershell
& .\.venv\Scripts\python.exe -c "from statlab_mcp.tools.data_exploration_data_type_check import data_type_check; import json; print(json.dumps(data_type_check('samples/dirty.csv'), ensure_ascii=False, indent=1))"
```
- 预期：dirty.csv 中 value→numeric、empty_col→missing、bad_date→date（含 1 个非法日期）、extreme→numeric
- Excel 验证方式：手动查看列内容即可复核（本工具输出的是类型判定，无统计数字）

---

# 工具 3：missing_report(file_path)

一句话用途：输出每一列的缺失数量/缺失率，并给出缺失模式（哪几列经常一起缺失、是否存在全缺失列），判断数据缺失是否值得警惕。

## 参数表（仅 1 个参数）
| 参数名 | 类型 | 默认值 | 校验规则 | 例子 |
|---|---|---|---|---|
| file_path | str | 必填 | 同全局约定 | `"data/dirty.csv"` |

## 返回（成功）
```jsonc
{
  "status": "ok",
  "result": {
    "n_rows": 20, "n_columns": 5,
    "total_missing": 23, "overall_missing_rate": 0.23,   // 缺少数/总单元格数
    "columns": {
      "value":     {"n_missing": 2,  "missing_rate": 0.10},
      "empty_col": {"n_missing": 20, "missing_rate": 1.00}
    },
    "complete_rows": 17, "rows_with_missing": 3,
    "patterns": [
      {"columns": ["empty_col"], "rows": 20, "note": "全缺失列"},
      {"columns": ["value"], "rows": 2, "note": null},
      {"columns": ["extreme"], "rows": 1, "note": null}
    ]
  },
  "summary": "共 20 行 5 列，总缺失 23 个（缺失率 23%）；empty_col 为全缺失列；无缺失模式疑似成对出现"
}
```
| 键 | 类型 | 说明 |
|---|---|---|
| total_missing / overall_missing_rate | int / float | 全局缺失概况（空串计入缺失） |
| columns.<列名>.n_missing / missing_rate | int / float | 单列缺失概况 |
| complete_rows / rows_with_missing | int | 完整行 / 含缺失行 |
| patterns | list | 缺失模式：columns=同时缺失的列组合、rows=该组合出现行数；全缺失列 note="全缺失列"；按 rows 降序，最多 10 条 |

## 边界行为表
| 场景 | 行为 |
|---|---|
| 无任何缺失 | total_missing=0、overall_missing_rate=0、patterns=[]；summary 注明"数据完整无缺失" |
| 全缺失列 | n_missing=总行数、missing_rate=1.0、pattern 注记"全缺失列" |
| 空单元格（含空串） | 计入缺失（pandas 默认将空串读为 NaN） |
| 两列成对缺失 | patterns 中出现该组合（如同时缺 value 与 extreme 的行数） |
| 中文列名 | 键原样输出 |
| 单行文件 | 按公式正常计算（缺失率 0 或 1） |

## 错误路径（≥3 种）
1. `文件不存在或不可访问: xxx.csv`
2. `仅支持 ['csv', 'json', 'tsv', 'xlsx'] 格式...`
3. `文件为空或无可读数据`
4. `缺少必需列: ...`（本工具无列参数，不适用；保留说明：单文件列长天然一致，无"两列长度不一致"）

## 验证命令与预期值来源
```powershell
& .\.venv\Scripts\python.exe -c "from statlab_mcp.tools.data_exploration_missing_report import missing_report; import json; print(json.dumps(missing_report('samples/dirty.csv'), ensure_ascii=False, indent=1))"
```
- 手工可复算：dirty.csv 20 行：value 缺 2（0.10）、empty_col 缺 20（1.00）、extreme 缺 1（0.05）→ total_missing=23、总体缺失率 23/100=0.23
- Excel 验证方式：用 COUNTBLANK 对每列计数对比

---

# 附录：批 1 自查（附录 C 组内 3 问）
- ⑦ 参数风格一致：三个工具均只收 file_path，命名与批 2 对齐（correlation_matrix/outlier_detect 亦只收文件+方法参数），组内一致
- ⑧ 功能无重叠：describe=分布数字、type_check=类型判定、missing=缺失概况，互不重复；与推断组 hypothesis_test 等无重叠
- ⑨ 统计方法使用条件：已写明分位数插值、偏度/峰度定义、std 的 ddof、常数列与 n<3 的处理；无假设检验类方法（不涉及正太性前提）
