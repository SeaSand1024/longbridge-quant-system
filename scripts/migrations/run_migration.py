"""
数据库迁移脚本 - 修复 positions 表结构
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pymysql
from app.config.database import get_db_connection

def run_migration():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print("开始执行数据库迁移...")
    
    # 添加缺失的列
    columns_to_add = [
        ('buy_price', 'DECIMAL(10,2) DEFAULT 0.00'),
        ('cost', 'DECIMAL(12,2) DEFAULT 0.00'),
        ('buy_time', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
        ('buy_acceleration', 'DECIMAL(10,4)'),
        ('status', 'VARCHAR(20) DEFAULT "HOLDING"'),
    ]
    
    for col_name, col_def in columns_to_add:
        try:
            cursor.execute(f'ALTER TABLE positions ADD COLUMN {col_name} {col_def}')
            print(f'✅ 添加列: {col_name}')
        except Exception as e:
            if 'Duplicate column' in str(e):
                print(f'⏭️ 列已存在: {col_name}')
            else:
                print(f'❌ 错误: {e}')
    
    conn.commit()
    
    # 修复唯一约束
    try:
        cursor.execute('ALTER TABLE positions DROP INDEX symbol')
        print('✅ 删除旧的 symbol 唯一约束')
    except Exception as e:
        print(f'⏭️ 约束操作: {e}')
    
    try:
        cursor.execute('ALTER TABLE positions ADD UNIQUE KEY unique_symbol_mode (symbol, test_mode)')
        print('✅ 添加新的 (symbol, test_mode) 组合唯一约束')
    except Exception as e:
        if 'Duplicate' in str(e):
            print('⏭️ 约束已存在')
        else:
            print(f'⏭️ 约束操作: {e}')
    
    conn.commit()
    cursor.close()
    conn.close()
    print('\n数据库迁移完成!')

if __name__ == '__main__':
    run_migration()
