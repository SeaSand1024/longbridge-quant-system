#!/usr/bin/env python3
import sys
import os
sys.path.append('.')

from main import test_mode_price_manager
import pymysql

# 数据库配置
db_config = {
    'host': os.getenv('MYSQL_HOST', '127.0.0.1'),
    'port': int(os.getenv('MYSQL_PORT', 3306)),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', '123456'),
    'database': os.getenv('MYSQL_DB', 'quant_system'),
    'charset': 'utf8mb4'
}

print('=== NIO价格问题诊断 ===')

# 1. 检查TestModePriceManager中NIO的状态
print('\\n1. TestModePriceManager状态:')
print('   base_prices:', test_mode_price_manager.base_prices.get('NIO'))
print('   current_prices:', test_mode_price_manager.current_prices.get('NIO'))
print('   price_trends:', test_mode_price_manager.price_trends.get('NIO'))

# 2. 检查持仓状态
try:
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    cursor.execute('SELECT * FROM positions WHERE symbol = "NIO" AND quantity > 0')
    position = cursor.fetchone()
    
    if position:
        print('\\n2. NIO持仓状态:')
        print('   数量:', position['quantity'])
        print('   平均成本:', position['avg_cost'])
    else:
        print('\\n2. NIO无持仓')
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print('\\n2. 数据库查询错误:', e)

# 3. 模拟获取NIO价格变化
print('\\n3. 模拟获取NIO价格变化（10次）:')
for i in range(10):
    price, change_pct = test_mode_price_manager.get_price('NIO')
    print('   第{}次: 价格=${:.2f}, 涨跌幅={:.2f}%'.format(i+1, price, change_pct))

# 4. 检查系统配置
try:
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    cursor.execute('SELECT * FROM system_config WHERE config_key IN ("test_mode", "profit_target")')
    configs = cursor.fetchall()
    
    print('\\n4. 系统配置:')
    for config in configs:
        print('   {}: {}'.format(config['config_key'], config['config_value']))
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print('\\n4. 配置查询错误:', e)

print('\\n=== 诊断完成 ===')