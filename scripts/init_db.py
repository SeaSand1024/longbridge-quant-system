#!/usr/bin/env python3
"""
初始化数据库脚本
创建表并插入MAG7股票数据
"""
import pymysql
import sys

# 数据库配置
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': 'root123',
    'database': 'quant_system',
    'charset': 'utf8mb4'
}

# MAG7股票
MAG7_STOCKS = [
    ('AAPL', 'Apple Inc.', 1),
    ('MSFT', 'Microsoft Corporation', 1),
    ('GOOGL', 'Alphabet Inc.', 1),
    ('AMZN', 'Amazon.com Inc.', 1),
    ('NVDA', 'NVIDIA Corporation', 1),
    ('META', 'Meta Platforms Inc.', 1),
    ('TSLA', 'Tesla Inc.', 1),
]


def create_tables(cursor):
    """创建数据库表"""
    print("正在创建数据库表...")

    # 股票表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            symbol VARCHAR(10) NOT NULL UNIQUE,
            name VARCHAR(255) NOT NULL,
            is_active TINYINT DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # 交易记录表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INT AUTO_INCREMENT PRIMARY KEY,
            symbol VARCHAR(10) NOT NULL,
            action VARCHAR(10) NOT NULL,
            price DECIMAL(10, 2) NOT NULL,
            quantity INT NOT NULL,
            amount DECIMAL(12, 2) NOT NULL,
            acceleration DECIMAL(10, 4),
            trade_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status VARCHAR(20) DEFAULT 'PENDING',
            message TEXT,
            test_mode TINYINT DEFAULT 0 COMMENT '0=真实环境, 1=测试模式'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # 持仓表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            symbol VARCHAR(10) NOT NULL UNIQUE,
            quantity INT NOT NULL,
            buy_price DECIMAL(10, 2) NOT NULL,
            cost DECIMAL(12, 2) NOT NULL,
            buy_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            buy_acceleration DECIMAL(10, 4),
            status VARCHAR(20) DEFAULT 'HOLDING',
            current_price DECIMAL(10, 2),
            profit_loss DECIMAL(12, 2),
            profit_loss_pct DECIMAL(10, 2),
            test_mode TINYINT DEFAULT 0 COMMENT '0=真实环境, 1=测试模式'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # 系统配置表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            id INT AUTO_INCREMENT PRIMARY KEY,
            config_key VARCHAR(50) NOT NULL UNIQUE,
            config_value VARCHAR(255) NOT NULL,
            description VARCHAR(255),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    print("✓ 数据库表创建完成")


def insert_mag7_stocks(cursor):
    """插入MAG7股票数据"""
    print("\n正在插入MAG7股票数据...")

    for symbol, name, is_active in MAG7_STOCKS:
        try:
            cursor.execute("""
                INSERT INTO stocks (symbol, name, is_active)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                name = VALUES(name),
                is_active = VALUES(is_active)
            """, (symbol, name, is_active))
            print(f"  ✓ {symbol} - {name}")
        except Exception as e:
            print(f"  ✗ {symbol} 插入失败: {e}")


def insert_system_config(cursor):
    """插入系统配置"""
    print("\n正在插入系统配置...")

    configs = [
        ('profit_target', '1.0', '止盈目标百分比'),
        ('monitoring_interval', '10', '监控间隔（秒）'),
        ('test_mode', 'false', '测试模式开关：true=测试模式，false=真实模式'),
    ]

    for key, value, description in configs:
        try:
            cursor.execute("""
                INSERT INTO system_config (config_key, config_value, description)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                config_value = VALUES(config_value),
                description = VALUES(description)
            """, (key, value, description))
            print(f"  ✓ {key} = {value}")
        except Exception as e:
            print(f"  ✗ {key} 插入失败: {e}")


def main():
    print("=" * 60)
    print("初始化美股量化交易系统数据库")
    print("=" * 60)

    try:
        # 连接数据库（添加连接参数解决兼容性问题）
        conn = pymysql.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            charset=DB_CONFIG['charset'],
            autocommit=True
        )
        cursor = conn.cursor()

        print(f"\n成功连接到数据库: {DB_CONFIG['database']}")

        # 创建表
        create_tables(cursor)

        # 插入数据
        insert_mag7_stocks(cursor)
        insert_system_config(cursor)

        # 提交更改
        conn.commit()

        # 显示统计信息
        cursor.execute("SELECT COUNT(*) FROM stocks WHERE is_active = 1")
        active_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM system_config")
        config_count = cursor.fetchone()[0]

        print("\n" + "=" * 60)
        print("✓ 数据库初始化完成")
        print(f"  活跃股票数: {active_count}")
        print(f"  配置项数: {config_count}")
        print("=" * 60)

        cursor.close()
        conn.close()
        return 0

    except Exception as e:
        print(f"\n✗ 错误: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
