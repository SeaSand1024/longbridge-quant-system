# 交易策略验证指南

## 策略说明

系统交易策略：
1. **买入条件**：
   - 从所有活跃的正股（排除期权）中选择涨幅加速度最大的股票
   - 使用固定金额（默认20万美元）购买
   - 加速度必须大于0

2. **卖出条件**：
   - 当持仓股票盈利达到系统设置的止盈目标（默认1%）时自动卖出
   - 全部卖出

## 策略配置

策略相关配置在 `system_config` 表中：

- `profit_target`: 止盈目标百分比（默认1.0）
- `buy_amount`: 买入金额（美元，默认200000）

可以通过系统设置页面或API修改这些配置。

## 验证方法

### 方法1：运行测试脚本（推荐）

运行测试脚本可以快速验证策略逻辑：

```bash
cd /Users/chenchen/Downloads/longbridge-quant-system
source venv/bin/activate
python3 test_strategy.py
```

测试脚本会：
- 从数据库获取所有活跃正股
- 模拟市场数据，生成不同的涨幅加速度
- 验证买入逻辑（选择加速度最大的股票，使用固定金额购买）
- 验证卖出逻辑（达到止盈目标后卖出）
- 显示详细的测试结果

**注意**：测试脚本不会实际下单，只是验证逻辑。

### 方法2：查看策略代码

主要策略代码在 `main.py` 的 `TradingStrategy` 类中：

- `check_and_trade()`: 主要交易逻辑
- `_load_config()`: 加载配置（止盈目标、买入金额）
- 买入逻辑：第640-700行
- 卖出逻辑：第706-750行

关键点：
- 只选择正股：`WHERE is_active = 1 AND stock_type = 'STOCK'`
- 固定金额购买：`quantity = int(self.buy_amount / best_stock['price'])`
- 加速度计算：使用最近3个价格点的涨幅变化率

### 方法3：实际运行验证（开盘时）

在美股开盘时间（美东时间9:30-16:00），可以：

1. **启动监控**：
   - 在Web界面点击"启动监控"按钮
   - 系统会每10秒检查一次市场数据

2. **观察日志**：
   ```bash
   # 查看服务日志，观察策略执行情况
   tail -f <日志文件>
   ```

3. **查看交易记录**：
   - 在Web界面"交易记录"标签页查看交易
   - 在"持仓"标签页查看当前持仓

4. **验证要点**：
   - ✅ 是否只从正股中选择（不包含期权）
   - ✅ 买入金额是否接近20万美元
   - ✅ 是否选择加速度最大的股票
   - ✅ 盈利达到1%后是否自动卖出

## 当前配置状态

运行以下命令查看当前配置：

```bash
python3 -c "
from main import get_db_connection
import pymysql
conn = get_db_connection()
cursor = conn.cursor(pymysql.cursors.DictCursor)
cursor.execute('SELECT * FROM system_config WHERE config_key IN (\"profit_target\", \"buy_amount\")')
configs = cursor.fetchall()
for c in configs:
    print(f\"{c['config_key']}: {c['config_value']} ({c['description']})\")
cursor.close()
conn.close()
"
```

## 修改配置

### 通过Web界面

1. 打开系统设置页面
2. 修改"止盈目标"或"买入金额"
3. 保存配置

### 通过API

```bash
# 修改止盈目标为1.5%
curl -X PUT http://localhost:8000/api/config \
  -H "Content-Type: application/json" \
  -d '{"config_key": "profit_target", "config_value": "1.5"}'

# 修改买入金额为15万美元
curl -X PUT http://localhost:8000/api/config \
  -H "Content-Type: application/json" \
  -d '{"config_key": "buy_amount", "config_value": "150000"}'
```

### 通过数据库

```sql
-- 修改止盈目标
UPDATE system_config SET config_value = '1.5' WHERE config_key = 'profit_target';

-- 修改买入金额
UPDATE system_config SET config_value = '150000' WHERE config_key = 'buy_amount';
```

## 注意事项

1. **测试脚本**：`test_strategy.py` 只是逻辑测试，不会实际下单
2. **实际交易**：需要在交易时间内运行，且确保长桥SDK已正确配置
3. **账户余额**：确保账户有足够的资金（至少20万美元可用）
4. **风险提示**：量化交易有风险，建议先在模拟环境充分测试

## 问题排查

如果策略没有按预期执行：

1. **检查配置**：确认 `profit_target` 和 `buy_amount` 配置正确
2. **检查股票列表**：确认有活跃的正股（`is_active=1 AND stock_type='STOCK'`）
3. **检查日志**：查看服务日志中的错误信息
4. **检查SDK连接**：确认长桥SDK已连接且使用真实模式
5. **检查账户余额**：确认账户有足够资金

## 策略优化建议

1. **添加开盘时间判断**：只在开盘时执行买入
2. **添加最大持仓时间**：避免长时间持仓
3. **添加止损机制**：当亏损达到一定比例时止损
4. **优化加速度计算**：可以调整计算周期或权重
5. **添加多股持仓支持**：可以同时持有多个股票
