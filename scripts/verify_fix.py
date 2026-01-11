#!/usr/bin/env python3
import sys
sys.path.append('.')
from main import is_test_mode, longbridge_sdk

print('=== 配置验证 ===')
print('1. is_test_mode():', is_test_mode())
print('2. longbridge_sdk.use_real_sdk:', longbridge_sdk.use_real_sdk)
print('3. longbridge_sdk.is_connected:', longbridge_sdk.is_connected)

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
        
        # 连续获取几次看价格是否变化
        print('\\n=== 价格变化测试 ===')
        prices = []
        for i in range(3):
            with urllib.request.urlopen('http://localhost:8000/api/market-data') as response:
                data = json.loads(response.read().decode('utf-8'))
            
            for item in data['data']:
                if item['symbol'] == 'NIO':
                    prices.append(item['price'])
                    print('  第{}次: ${:.2f}'.format(i+1, item['price']))
                    break
            
            import time
            time.sleep(2)
        
        # 检查价格是否变化
        if len(set(prices)) > 1:
            print('\\n✓ 价格开始变化了！')
        else:
            print('\\n✗ 价格仍然没有变化')
    else:
        print('API未返回NIO数据')
        
except Exception as e:
    print('API调用失败:', e)

# 检查是否需要重启服务
print('\\n=== 服务状态检查 ===')
if longbridge_sdk.use_real_sdk and not longbridge_sdk.is_connected:
    print('⚠️ 需要重启服务使配置生效')
    print('请停止并重新启动FastAPI服务')
else:
    print('✓ 配置已生效')