-- 修复 positions 表唯一约束问题
-- Bug 7: 将 symbol 唯一约束改为 (symbol, test_mode) 组合唯一

-- 1. 删除旧的唯一约束
ALTER TABLE positions DROP INDEX symbol;

-- 2. 添加新的组合唯一约束
ALTER TABLE positions ADD UNIQUE KEY unique_symbol_mode (symbol, test_mode);

-- 3. 添加索引提高查询性能
ALTER TABLE positions ADD INDEX idx_test_mode (test_mode);

-- 4. 扩展 symbol 字段长度以支持期权代码
ALTER TABLE stocks MODIFY COLUMN symbol VARCHAR(30) NOT NULL;
ALTER TABLE trades MODIFY COLUMN symbol VARCHAR(30) NOT NULL;
ALTER TABLE positions MODIFY COLUMN symbol VARCHAR(30) NOT NULL;
ALTER TABLE stock_predictions MODIFY COLUMN symbol VARCHAR(30) NOT NULL;
ALTER TABLE auto_trade_tasks MODIFY COLUMN symbol VARCHAR(30);
ALTER TABLE stock_kline_cache MODIFY COLUMN symbol VARCHAR(30) NOT NULL;
