#!/usr/bin/env python3
import sys
sys.path.append('.')
from main import is_test_mode, longbridge_sdk

print('=== 最终诊断 ===')
print('1. is_test_mode():', is_test_mode())
print('2. longbridge_sdk.use_real_sdk:', longbridge_sdk.use_real_sdk)
print('3. longbridge_sdk.is_connected:', longbridge_sdk.is_connected)

# 测试get_realtime_quote方法
print('\\n=== 测试价格获取逻辑 ===')
if is_test_mode():
    print('系统处于测试模式，应该返回模拟数据')
    # 测试获取模拟数据
    from main import test_mode_price_manager
    price, change_pct = test_mode_price_manager.get_price('NIO')
    print('TestModePriceManager返回: 价格=${:.2f}, 涨跌幅={:.2f}%'.format(price, change_pct))
else:
    print('系统处于真实模式，应该返回真实数据')

# 测试API返回的数据
print('\\n=== 测试API返回数据 ===')
import urllib.request
import json

try:
    with urllib.request.urlopen('http://localhost:8000/api/market-data') as response:
        data = json.loads(response.read().decode('utf-8'))
    
    nio_data = None
    for item in data['data']:
        if item['symbol'] == 'NIO':
            nio_data = item
            break
    
    if nio_data:
        print('API返回NIO数据:')
        print('  价格: ${:.2f}'.format(nio_data['price']))
        print('  涨跌幅: {:.2f}%'.format(nio_data['change_pct']))
        print('  加速度: {:.4f}'.format(nio_data['acceleration']))
    else:
        print('API未返回NIO数据')
        
except Exception as e:
    print('API调用失败:', e)