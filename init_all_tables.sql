-- 完整的数据库表初始化脚本
-- 适配 MySQL 5.6 / MariaDB

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    email VARCHAR(100) UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

-- 刷新令牌表
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    token VARCHAR(191) UNIQUE NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at TIMESTAMP DEFAULT 0,
    INDEX idx_token (token),
    INDEX idx_user_id (user_id),
    INDEX idx_expires_at (expires_at),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

-- 用户配置表
CREATE TABLE IF NOT EXISTS user_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    config_key VARCHAR(100) NOT NULL,
    config_value TEXT,
    description VARCHAR(255),
    created_at TIMESTAMP DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_user_config (user_id, config_key),
    INDEX idx_user_id (user_id),
    INDEX idx_config_key (config_key),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

-- 股票表
CREATE TABLE IF NOT EXISTS stocks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(30) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    is_active TINYINT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    stock_type VARCHAR(20) DEFAULT 'STOCK',
    group_name VARCHAR(100),
    group_order INT DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

-- 交易记录表
CREATE TABLE IF NOT EXISTS trades (
    id INT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(30) NOT NULL,
    action VARCHAR(10) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    quantity INT NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    acceleration DECIMAL(10, 4),
    trade_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'PENDING',
    message TEXT,
    test_mode TINYINT DEFAULT 0 COMMENT '0=真实环境, 1=测试模式',
    INDEX idx_symbol (symbol),
    INDEX idx_test_mode (test_mode)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

-- 持仓表 (symbol + test_mode 组合唯一)
CREATE TABLE IF NOT EXISTS positions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(30) NOT NULL,
    quantity INT NOT NULL,
    avg_cost DECIMAL(10, 2) DEFAULT 0.00,
    buy_price DECIMAL(10, 2) NOT NULL,
    cost DECIMAL(12, 2) NOT NULL,
    buy_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    buy_acceleration DECIMAL(10, 4),
    status VARCHAR(20) DEFAULT 'HOLDING',
    current_price DECIMAL(10, 2),
    profit_loss DECIMAL(12, 2),
    profit_loss_pct DECIMAL(10, 2),
    test_mode TINYINT DEFAULT 0 COMMENT '0=真实环境, 1=测试模式',
    UNIQUE KEY unique_symbol_mode (symbol, test_mode),
    INDEX idx_test_mode (test_mode)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

-- 系统配置表
CREATE TABLE IF NOT EXISTS system_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(50) NOT NULL UNIQUE,
    config_value VARCHAR(255) NOT NULL,
    description VARCHAR(255),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

-- 股票预测记录表
CREATE TABLE IF NOT EXISTS stock_predictions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    prediction_date DATE NOT NULL,
    predicted_return DECIMAL(10, 4) COMMENT '预测收益率(%)',
    confidence_score DECIMAL(5, 4) COMMENT '置信度(0-1)',
    technical_score DECIMAL(5, 2) COMMENT '技术指标得分',
    momentum_score DECIMAL(5, 2) COMMENT '动量得分',
    volatility_score DECIMAL(5, 2) COMMENT '波动率得分',
    llm_score DECIMAL(5, 2) COMMENT 'LLM预测得分',
    llm_recommendation VARCHAR(20) COMMENT 'LLM建议(buy/hold/sell)',
    llm_analysis TEXT COMMENT 'LLM分析内容',
    actual_return DECIMAL(10, 4) COMMENT '实际收益率(%)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_prediction (symbol, prediction_date),
    INDEX idx_date (prediction_date),
    INDEX idx_predicted_return (predicted_return)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

-- 自动交易任务表
CREATE TABLE IF NOT EXISTS auto_trade_tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_type VARCHAR(20) NOT NULL COMMENT 'OPEN_BUY=开盘买入, SMART_SELL=智能卖出',
    symbol VARCHAR(10),
    status VARCHAR(20) DEFAULT 'PENDING' COMMENT 'PENDING/RUNNING/COMPLETED/FAILED',
    scheduled_time DATETIME NOT NULL,
    executed_time DATETIME,
    result TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_status (status),
    INDEX idx_scheduled_time (scheduled_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

-- 历史K线数据缓存表
CREATE TABLE IF NOT EXISTS stock_kline_cache (
    id INT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    trade_date DATE NOT NULL,
    open_price DECIMAL(10, 2),
    high_price DECIMAL(10, 2),
    low_price DECIMAL(10, 2),
    close_price DECIMAL(10, 2),
    volume BIGINT,
    turnover DECIMAL(20, 2),
    change_pct DECIMAL(10, 4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_kline (symbol, trade_date),
    INDEX idx_symbol (symbol),
    INDEX idx_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
