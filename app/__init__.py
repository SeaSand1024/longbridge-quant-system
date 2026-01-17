# 美股量化交易系统 - 应用模块
"""
项目结构:
app/
├── __init__.py          # 模块入口
├── config/              # 配置模块
│   ├── settings.py      # 全局配置
│   └── database.py      # 数据库连接
├── models/              # 数据模型
│   └── schemas.py       # Pydantic模型
├── auth/                # 认证模块
│   └── utils.py         # 认证工具
├── services/            # 服务层
│   ├── longbridge_sdk.py    # 长桥SDK封装
│   ├── smart_trader.py      # 智能预测交易
│   ├── trading_strategy.py  # 交易策略
│   ├── acceleration.py      # 加速度计算
│   ├── test_mode.py         # 测试模式
│   ├── task_queue.py        # 任务队列
│   └── sse.py               # SSE推送
└── routers/             # 路由模块
    ├── auth.py          # 认证路由
    ├── stocks.py        # 股票路由
    ├── trades.py        # 交易路由
    ├── positions.py     # 持仓路由
    ├── config.py        # 配置路由
    ├── monitoring.py    # 监控路由
    ├── smart_trade.py   # 智能交易路由
    ├── longbridge.py    # 长桥SDK路由
    └── market_data.py   # 市场数据路由
"""
