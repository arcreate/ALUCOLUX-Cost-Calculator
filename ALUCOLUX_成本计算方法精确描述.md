# ALUCOLUX® 成本计算方法精确描述（v2026.04 变量驱动版）

## 1. 核心原则（高中生也能看懂）
把生产ALUCOLUX铝板比作“做一大锅菜”。  
所有数值都设计为**可配置变量**，程序必须允许用户随时修改默认值。

## 2. 可调核心变量（程序必须实现为输入参数或配置文件）
程序读取以下变量表，支持用户在界面上修改：

| 变量名                  | 默认值     | 单位          | 说明                              |
|-------------------------|------------|---------------|-----------------------------------|
| AL_DENSITY             | 2.73      | kg/m²/mm     | ALUCOLUX密度                      |
| BAD_RATE               | 0.08      | -            | 不良品率                          |
| TRIAL_LENGTH           | 18        | 米/次        | 每次试机长度                      |
| MAX_ROLL_WEIGHT        | 10000     | kg           | 单卷最大重量                      |
| HEAD_TAIL_LENGTH       | 22        | 米/卷        | 每个卷的头尾损耗长度              |
| AL_PRICE               | 27.5      | 元/kg        | 铝材单价（铝锭+加工费）           |
| PRE_TREATMENT_PER_TON  | 500       | 元/吨        | 铝卷前处理费                      |
| BASE_PAINT_PRICE       | 43.5      | 元/kg        | 底漆单价                          |
| BACK_PAINT_PRICE       | 43        | 元/kg        | 背漆单价                          |
| FACE_PAINT_PRICE       | 140       | 元/kg        | 面漆单价（素色，默认已修正）      |
| CLEAR_PAINT_PRICE      | 160       | 元/kg        | 清漆单价                          |
| PRINT_PAINT_PRICE      | 140       | 元/kg        | 印花漆单价                        |
| BASE_PAINT_COVERAGE    | 25        | ㎡/kg        | 底漆上漆率                        |
| BACK_PAINT_COVERAGE    | 30        | ㎡/kg        | 背漆上漆率                        |
| FACE_PAINT_COVERAGE    | 8         | ㎡/kg        | 面漆上漆率                        |
| CLEAR_PAINT_COVERAGE   | 18        | ㎡/kg        | 清漆上漆率                        |
| PRINT_PAINT_COVERAGE   | 240       | ㎡/kg        | 印花漆上漆率                      |
| PAINT_DISK_COST        | 10500     | 元/盘        | 面漆漆盘固定费                    |
| PROTECT_FILM_PRICE     | 1.48      | 元/㎡        | 保护膜单价                        |
| TON_BASE_COST          | 3250      | 元/吨        | 吨基费用合计（人工+水电气+接头+稀释剂） |
| OPEN_MACHINE_FEE       | 50000     | 元           | 开机固定费（小单收取）            |
| OPEN_MACHINE_THRESHOLD | 3000      | ㎡            | 开机费收取阈值（低于此值收费）    |
| FLY_CUT_PRICE          | 1.5       | 元/㎡        | 飞剪加工费                        |
| PACKAGING_PER_TON      | 500       | 元/吨        | 包装费                            |
| EXCHANGE_RATE          | 6.85      | -            | 人民币转USD汇率                  |

**印花辊变量**（仅印花订单使用）：
- LAB_SMALL_ROLL_COST = 1800 元/根
- PROD_BIG_ROLL_COST = 6000 元/根

## 3. 精确计算步骤（全部使用上面变量）

### 步骤1：计算最终总生产面积
1. 初步总面积 = 合同面积 / (1 - BAD_RATE) + 试机面积  
   试机面积 = 试机次数 × TRIAL_LENGTH × 宽度(m)  
   （试机次数：PVDF2=2，PVDF3/1花/2花默认=3~4，可调）

2. 初步铝重 = 初步总面积 × 板厚 × AL_DENSITY

3. 实际卷数 = ceil(初步铝重 / MAX_ROLL_WEIGHT)

4. 料头料尾面积 = 实际卷数 × HEAD_TAIL_LENGTH × 宽度(m)

5. **最终总生产面积** = 初步总面积 + 料头料尾面积

### 步骤2：铝材成本
总铝重 = 最终总生产面积 × 板厚 × AL_DENSITY  
铝材成本 = 总铝重 × AL_PRICE  
前处理费 = (总铝重 / 1000) × PRE_TREATMENT_PER_TON

### 步骤3：油漆成本（含漆盘）
每层用量(kg) = 最终总生产面积 / 上漆率（使用对应变量）  
油漆成本 = 用量 × 对应单价  
漆盘费 = PAINT_DISK_COST（仅面漆）

### 步骤4：其他直接成本
- 保护膜 = 最终总生产面积 × PROTECT_FILM_PRICE
- 印花辊（仅印花）：
  - 1花：小辊2根 + 大辊1根
  - 2花：小辊2根 + 大辊2根
- 吨基费用 = (总铝重 / 1000) × TON_BASE_COST
- 开机固定费 = 如果合同面积 < OPEN_MACHINE_THRESHOLD 则 OPEN_MACHINE_FEE，否则 0
- 飞剪 = 合同面积 × FLY_CUT_PRICE
- 包装 = (总铝重 / 1000) × PACKAGING_PER_TON

### 步骤5：总成本与单价
总直接成本 = 以上所有相加  
单位保本价(元/㎡) = 总直接成本 / 合同面积  
USD单价 = 单位保本价 / EXCHANGE_RATE

## 4. 输出要求
程序必须按“超级简单版”风格输出（白话+公式+数字+加粗）。