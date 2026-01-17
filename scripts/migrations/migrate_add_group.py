#!/usr/bin/env python3
"""
为stocks表添加分组字段
"""
import pymysql

# 数据库配置
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': '123456',
    'database': 'quant_system',
    'charset': 'utf8mb4'
}


def main():
    print("=" * 60)
    print("为stocks表添加分组字段")
    print("=" * 60)

    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 添加group_name字段
        cursor.execute("""
            ALTER TABLE stocks
            ADD COLUMN group_name VARCHAR(100) DEFAULT '未分组' AFTER name
        """)
        print("✓ 添加 group_name 字段成功")

        # 添加group_order字段
        cursor.execute("""
            ALTER TABLE stocks
            ADD COLUMN group_order INT DEFAULT 0 AFTER group_name
        """)
        print("✓ 添加 group_order 字段成功")

        conn.commit()

        print("\n" + "=" * 60)
        print("✓ 数据库迁移完成")
        print("=" * 60)

        cursor.close()
        conn.close()

    except Exception as e:
        if "Duplicate column name" in str(e):
            print("\n✓ 字段已存在，跳过迁移")
        else:
            print(f"\n✗ 错误: {e}")


if __name__ == "__main__":
    main()
