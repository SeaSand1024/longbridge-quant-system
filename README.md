# 美股量化交易系统

基于长桥SDK的美股量化交易系统，实现MAG7股票的自动化交易策略。

## 项目结构

```
longbridge-quant-system/
├── main.py                 # 主程序：FastAPI应用入口
├── static/                 # 前端静态文件
│   ├── index.html         # 主页面
│   ├── app.js             # 前端逻辑
│   └── style.css          # 样式文件
├── scripts/               # 工具脚本
│   ├── init_db.py         # 数据库初始化
│   ├── test_real_order.py # 真实下单测试
│   ├── test_strategy.py   # 策略测试脚本
│   ├── test_data_isolation.py # 数据隔离测试
│   └── ...                # 其他辅助脚本
├── docs/                  # 文档
│   ├── STRATEGY_TEST.md   # 策略测试文档
│   └── nio_price_analysis.md # 价格分析文档
├── requirements.txt       # Python依赖
├── Dockerfile             # Docker镜像构建文件
└── README.md              # 项目说明
```

## 功能特性

- **股票管理**：支持添加、删除和启用/停用股票
- **实时监控**：WebSocket实时推送行情（生产模式）/ 1秒轮询（测试模式）
- **涨幅加速度计算**：自动计算股票涨幅加速度
- **自动交易**：
  - 开盘时自动买入涨幅加速度最快的股票
  - 涨幅达到止盈目标时自动卖出
- **双模式支持**：测试模式（模拟数据）和真实模式（真实交易）
- **交易记录**：完整的交易历史记录
- **可视化界面**：现代化的Web管理界面

## 技术栈

- **后端**：Python 3.9+ + FastAPI + AsyncIO
- **前端**：HTML + JavaScript + Tailwind CSS + ECharts
- **数据库**：MySQL 5.7+
- **SDK**：长桥证券OpenAPI
- **实时通信**：WebSocket（行情推送）+ SSE（事件通知）

## 安装部署

### 环境要求

- Python 3.9+
- MySQL 5.7+
- 长桥证券账户（真实交易需要）

### 1. 安装依赖

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 数据库初始化

```bash
cd scripts
python init_db.py
```

### 3. 配置环境变量

创建 `.env` 文件或设置环境变量：

```bash
# MySQL数据库配置
export MYSQL_HOST=127.0.0.1
export MYSQL_PORT=3306
export MYSQL_USER=root
export MYSQL_PASSWORD=your_password
export MYSQL_DB=quant_system

# 长桥SDK配置（真实交易需要）
export LONGBRIDGE_APP_KEY=your_app_key
export LONGBRIDGE_APP_SECRET=your_app_secret
export LONGBRIDGE_ACCESS_TOKEN=your_access_token
```

### 4. 启动服务

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

访问：http://localhost:8000

## 使用说明

### 1. 股票管理

- 系统默认包含MAG7股票（AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA）
- 可以添加或删除股票（美股代码需加 .US 后缀，如 AAPL.US）
- 可以启用或停用股票（只有启用的股票才会参与交易）

### 2. 模式切换

在"系统设置"中切换交易模式：
- **测试模式**：使用模拟价格和模拟下单，适合策略测试
- **真实模式**：使用真实行情和真实交易，请谨慎使用

### 3. 启动监控

点击右上角的"启动监控"按钮，系统将：
- 生产模式：使用WebSocket实时接收行情推送（毫秒级）
- 测试模式：每1秒轮询获取行情（高频）
- 计算各股票的涨幅加速度
- 自动执行买入/卖出操作

### 4. 交易策略

**买入条件**：
- 当前持仓数小于最大并发数
- 选择涨幅加速度最大的股票
- 加速度必须大于0
- 使用配置的单笔买入金额

**卖出条件**：
- 持仓股票涨幅达到止盈目标（可配置，范围0.1%-100%）
- 全部卖出

### 5. 系统设置

在"系统设置"标签页可以配置：
- 测试模式开关
- 止盈目标百分比（0.1%-100%）
- 单笔买入金额（1000-1000000 USD）
- 最大并发持仓数
- 长桥SDK凭证

## 工具脚本

位于 `scripts/` 目录下：

- `init_db.py` - 初始化数据库结构和默认数据
- `test_real_order.py` - 测试真实下单功能（需输入YES确认）
- `test_strategy.py` - 测试交易策略逻辑
- `test_data_isolation.py` - 验证测试模式和真实模式的数据隔离
- `migrate_add_*.py` - 数据库迁移脚本
- `add_test_mode_fields.py` - 为现有表添加测试模式字段

## 注意事项

⚠️ **重要提示**：

1. 首次使用请先在**测试模式**下充分测试
2. 真实模式会执行真实交易，涉及资金风险
3. 美股代码格式：`股票代码.US`（如 NVDA.US, AAPL.US）
4. 港股代码格式：`股票代码.HK`（如 700.HK, 9988.HK）
5. 建议设置合理的止盈目标和买入金额
6. 非交易时间无法执行真实交易

## 数据库结构

### stocks（股票表）
- id, symbol, name, stock_type, is_active
- test_mode: 0=真实环境, 1=测试模式

### trades（交易记录表）
- id, symbol, action, price, quantity, amount, status, message
- acceleration, trade_time, test_mode

### positions（持仓表）
- id, symbol, quantity, avg_cost, current_price
- profit_loss, profit_loss_pct, test_mode

### system_config（系统配置表）
- config_key, config_value, description

## API接口

### 股票管理
- `GET /api/stocks` - 获取股票列表
- `POST /api/stocks` - 添加股票
- `DELETE /api/stocks/{id}` - 删除股票
- `PUT /api/stocks/{id}/toggle` - 切换股票状态

### 市场数据
- `GET /api/market-data` - 获取实时行情
- `GET /api/stock/history/{symbol}` - 获取股票历史K线
- `GET /api/account/overview` - 获取账户总览

### 交易相关
- `GET /api/trades` - 获取交易记录
- `POST /api/monitoring/start` - 启动监控
- `POST /api/monitoring/stop` - 停止监控
- `GET /api/monitoring/status` - 获取监控状态
- `GET /api/positions` - 获取当前持仓

### 配置管理
- `GET /api/config` - 获取系统配置
- `PUT /api/config` - 更新系统配置

## 许可证

MIT License
