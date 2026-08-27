# power_analysis 设计文档（v1.1.0 · 工具 27 · 统计推断组批 3 扩展）

> **工具索引**（v1.1.0 起 statlab://tools/<名>/manual 取本文件对应小节，锚点=一级标题行“# 工具 N：<函数名>(”）：power_analysis（工具27）

# 工具 27：power_analysis(scenario, effect_size=None, n=None, p1=None, p2=None, alpha=0.05, power_target=0.80, alternative="two_sided")

回答「要检出效应量，需要多少样本」与「给定样本量能检出多大效应」，以及
「当前配置的实际功效是多少」三类问题；纯封闭公式计算、零 LLM、确定性输出。

## 定位与范围

- 纯计算功效分析：不做任何猜测性数据修复、不含 LLM；输入参数→封闭公式引擎→结构化输出。
- 引擎选型（statsmodels.stats.power，理由见下）：换库/换实现必须重跑本文档验证节并更新 SPEC。

## 引擎选型（钉死 + 理由）

| scenario | 引擎 | 理由 |
|---|---|---|
| `one_sample_t` | `statsmodels.stats.power.TTestPower` | 单样本/重复测量 t 的非中心 t 精确功效（Cohen dz 口径），与 G*Power"Means: paired/one-sample t-test"模块一致 |
| `two_sample_t` | `statsmodels.stats.power.TTestIndPower` | 独立两样本 Welch-type 非中心 t 精确功效，ratio 固定 1.0（等样本两组），与 G*Power"independent means"一致 |
| `two_proportions` | `statsmodels.stats.power.NormalIndPower` | 以 Cohen's h 为效应量的两独立比例正态近似功效（n.scaled 常规口径），比 χ² 纠偏公式更透明；h 由本工具以 `2·arcsin√p₁ − 2·arcsin√p₂` 手工换算（Arcsine 变换，Cohen 1988 §6.2.1），**不暴露 h 作为入参** |

备选 `ztreat/solve` 家族、Pingouin 等未采用原因：前者与 scipy 版本耦合深，后者引入新依赖（违反依赖纪律）。

## 参数决策表（任务书钉死，消除歧义）

| 输入组合 | 行为 |
|---|---|
| 只给效应侧（effect_size 或 p1+p2） | 求所需样本量 n → `mode="solve_n"` |
| 只给 n | 求可检出效应量（反查）→ `mode="detect_effect"` |
| 效应侧与 n 同给 | 输出实际功效验算 → `mode="verify"`（三侧全返回） |
| 两者都不给（或缺一半，如仅 p1） | 中文报错 + `E1001`（复用，不新增码） |

- `scenario` ∈ {`one_sample_t`, `two_sample_t`, `two_proportions`}，非法 → E1001；
- `alternative` ∈ {`two_sided`, `less`, `greater`}（与既有工具同风格），内部映射
  statsmodels 枚举：two_sided→"two-sided"、less→"smaller"、greater→"larger"；非法 → E1001；
- `alpha ∈ (0,1)`、`power_target ∈ (0,1)`、`effect_size > 0`；NaN/Inf/bool 一律拒绝 → E1001；
- `p1, p2 ∈ (0,1)` 开区间且必须成对出现（仅 p1 或仅 p2 → E1001"成对提供"）；t 系场景给了
  p1/p2、或两比例场景给了 effect_size → E1001（防歧义，不猜测意图）；
- `n`：≥2 整数；两样本场景 n = **每组**样本量（ratio=1，total=2n，result 注明 n_each/n_total）。

## n 取整口径（钉死）

`solve_power` 返回连续解（float，taub 保留 4 位精度足够）；结果同时输出：

- `n_required_exact`：连续最优解原样（float，供下游程序比较）；
- `n_recommended`：`math.ceil(exact)`（整数，向上取整确保不低于目标功效）。

## 换算细节（确定性代码）

- Cohen's h = `2·arcsin(√p₁) − 2·arcsin(√p₂)`（math.asin/math.sqrt 手写，不用
  statsmodels.proportion_effectsize 包装，换取逐字节确定性）；功率侧以 `abs(h)` 进引擎，
  方向语义由 alternative 表达并在 summary 说明。
- 反查模式输出的 `detectable_effect_size` 一律取正值（|d| 口径）。

## 边界行为表

| 场景 | 行为 |
|---|---|
| effect_size=0 / 负数（t 系） | E1001："effect_size 必须为 >0 的有限数" |
| p1/p2 出界（0、1、负数、>1） | E1001："p1/p2 必须在 (0,1) 之间" |
| p1 仅给一个 | E1001："两比例场景必须成对提供 p1 与 p2" |
| n=1 / 非整数 / bool | E1001："n 必须是 >=2 的整数" |
| power_target=0 或 1 | E1001："power_target 必须在 (0,1) 之间" |
| solution 收敛失败（statsmodels 抛异常） | 兜底 E9999 计算失败中文文案（stderr 留堆栈） |

## 验证方法（可复算，G*Power 锚粒度）

测试文件 tests/test_power_analysis.py；手算/G*Power 对照锚：

1. **two_sample_t 求样本量**：d=0.5、α=0.05 双侧、1−β=0.80 →
   G*Power 3.1.97（Faul, Erdfelder, Lang & Buchner, 2007, Behavior Research Methods;
   Means → Difference between two independent means，其官方手册样例）总 N=128（64/组）。
   断言 ceil(n_required_exact)==64 且 63<n_required_exact<65。
2. **one_sample_t 求样本量**：d=0.5、α=0.05 双侧、1−β=0.80 →
   同一版 G*Power（paired/one-group t 模块同参数）给出 N=34。
   断言 ceil(n_required_exact)==34。
3. **two_sample_t 反查效应量**：每组 n=64、α=0.05 双侧、power=0.80 → 可检出
   d=0.5（与第 1 条互逆）；断言 |detectable − 0.5| ≤ 0.01。
4. **two_proportions 的 h 换算手算**：p1=0.50、p2=0.80 →
   h = 2·arcsin(√0.5) − 2·arcsin(√0.8)
     = 2×0.7853982 − 2×1.1071487
     = 1.5707963 − 2.2142974 = **−0.6435011**
   （arcsin(√0.5)=π/4 是常用精确常数；arcsin(√0.8)=arcsin(0.8944272)=1.1071487 rad，
   任何科学计算器可复核。注意常见的粗心错误是把公式错读成 2·arcsin(p₂)=1.8545904。）
   断言 cohens_h == −0.6435011（approx 1e-6）。
5. **verify 往返**：two_sample_t d=0.5、n=64/组 → power ∈ [0.79, 0.81]
   （实测 0.8015；G*Power 同配置显示 0.8007）。
6. **两比例样本量的封闭公式锚**：正态近似每组 n = 2·(z_{1−α/2}+z_{power})²/h²；
   代入 z=1.959964/0.841621、|h|=0.6435011 → n=37.9086（NormalIndPower 与该公式完全
   同源，实现断言 approx rel=1e-5；比记忆的软件界面数字更硬，可逐位复算）。
7. **内部往返一致**：solve_n 推荐 ceil(n) 再走 verify → 实际功效 ≥ target−0.01。

## 上游限制与方向归一（重要实现事实）

- statsmodels 0.14.6 的 solve_power 对**单侧求根**存在已知缺陷：当效应量符号 × 方向
  组合不匹配时 brentq 失败并伴随 "Failed to converge" 警告、可能返回垃圾值（如恒为 10）。
- 本工具的处置（防幻觉优先）：
  1. 单侧求解统一做「方向归一」——less（检出下降 d）≡ (effect=−d, alternative='larger')、
     greater ≡ (effect=+d, 'larger')，数值上严格等价且实测三引擎稳定；
  2. verify 模式只算 power 不走求根，三个方向全部直接可用；
  3. 求根过程中捕获到未收敛警告或非有限值 → 一律拒绝并返回 E9999 中文报错
     （宁可报错也不输出可疑数字）。

其余：参数决策表四行全覆盖、非法参数逐项 E1001、确定性（同输入两次运行 JSON 逐字节一致）、
中文列名/特殊值安全、JSON allow_nan=False。
