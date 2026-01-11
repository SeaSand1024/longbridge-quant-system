#!/usr/bin/env python3
import urllib.request
import json
import time

print('=== 检查NIO价格变化 ===')

for i in range(5):
    try:
        # 使用urllib获取数据
        with urllib.request.urlopen('http://localhost:8000/api/market-data') as response:
            data = json.loads(response.read().decode('utf-8'))
        
        nio_data = None
        for item in data['data']:
            if item['symbol'] == 'NIO':
                nio_data = item
                break
        
        if nio_data:
            print('第{}次获取: NIO价格: ${:.2f}, 涨跌幅: {:.2f}%'.format(
                i+1, nio_data['price'], nio_data['change_pct']))
        else:
            print('第{}次获取: 未找到NIO数据'.format(i+1))
        
        time.sleep(3)
        
    except Exception as e:
        print('第{}次获取出错: {}'.format(i+1, e))
        time.sleep(3)