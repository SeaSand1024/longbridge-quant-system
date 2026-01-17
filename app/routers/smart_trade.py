"""
智能交易路由
"""
from fastapi import APIRouter, HTTPException, Depends
import pymysql

from app.config.database import get_db_connection
from app.auth.utils import get_current_user
from app.services.smart_trader import smart_trader

router = APIRouter(prefix="/api/smart-trade", tags=["智能交易"])


@router.get("/status")
async def get_smart_trade_status(current_user: dict = Depends(get_current_user)):
    """获取智能交易状态"""
    try:
        await smart_trader.load_config()
        status = smart_trader.get_status()
        
        predictions = []
        trade_stats = {'total_trades': 0, 'buy_count': 0, 'sell_count': 0}
        
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        try:
            cursor.execute("""
                SELECT symbol, predicted_return, confidence_score, technical_score, 
                       llm_score, llm_recommendation, llm_analysis, actual_return
                FROM stock_predictions
                WHERE prediction_date = CURDATE()
                ORDER BY technical_score DESC
                LIMIT 10
            """)
            predictions = cursor.fetchall()
        except Exception:
            # stock_predictions 表可能不存在
            pass
        
        try:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN action = 'BUY' THEN 1 ELSE 0 END) as buy_count,
                    SUM(CASE WHEN action = 'SELL' THEN 1 ELSE 0 END) as sell_count
                FROM trades
                WHERE DATE(trade_time) = CURDATE()
            """)
            trade_stats = cursor.fetchone() or trade_stats
        except Exception:
            pass
        
        cursor.close()
        conn.close()
        
        return {
            "code": 0,
            "data": {
                "status": status,
                "today_predictions": predictions,
                "today_stats": trade_stats
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config")
async def update_smart_trade_config(config: dict, current_user: dict = Depends(get_current_user)):
    """更新智能交易配置"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        config_mapping = {
            'enabled': 'smart_trade_enabled',
            'max_daily_trades': 'smart_max_daily_trades',
            'buy_amount': 'smart_buy_amount',
            'min_score': 'smart_min_score',
            'dynamic_stop': 'smart_dynamic_stop',
            'base_profit': 'smart_base_profit',
            'trailing_stop': 'smart_trailing_stop',
            'max_hold_days': 'smart_max_hold_days',
            'llm_enabled': 'llm_enabled',
            'llm_provider': 'llm_provider',
            'llm_api_key': 'llm_api_key',
            'llm_api_base': 'llm_api_base',
            'llm_model': 'llm_model',
            'llm_weight': 'llm_weight'
        }
        
        for key, db_key in config_mapping.items():
            if key in config:
                value = str(config[key]).lower() if isinstance(config[key], bool) else str(config[key])
                cursor.execute("""
                    INSERT INTO system_config (config_key, config_value, description)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)
                """, (db_key, value, f'智能交易配置: {key}'))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        await smart_trader.load_config()
        
        return {"code": 0, "message": "智能交易配置已更新"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run-prediction")
async def run_prediction(current_user: dict = Depends(get_current_user)):
    """运行股票预测"""
    try:
        await smart_trader.load_config()
        predictions = await smart_trader.run_daily_prediction()
        return {"code": 0, "data": predictions[:10], "message": f"预测完成，共{len(predictions)}只股票"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute-buy")
async def execute_smart_buy(current_user: dict = Depends(get_current_user)):
    """手动执行智能买入"""
    from app.services.smart_trader import smart_trader
    from app.services.trading_strategy import trading_strategy
    
    try:
        # 获取智能推荐的股票
        recommendations = await smart_trader.get_top_recommendations(limit=1)
        
        if not recommendations:
            return {"code": 1, "message": "当前没有合适的买入推荐"}
        
        top_pick = recommendations[0]
        symbol = top_pick.get('symbol')
        price = top_pick.get('price', 0)
        
        if not symbol or price <= 0:
            return {"code": 1, "message": "推荐股票数据无效"}
        
        # 执行买入
        result = await trading_strategy.execute_buy(
            symbol=symbol,
            price=price,
            acceleration=top_pick.get('acceleration', 0)
        )
        
        if result.get('success'):
            return {
                "code": 0, 
                "message": f"智能买入已执行: {symbol}",
                "data": result
            }
        else:
            return {"code": 1, "message": result.get('message', '买入失败')}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/predictions")
async def get_predictions(days: int = 7, current_user: dict = Depends(get_current_user)):
    """获取预测历史"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        cursor.execute("""
            SELECT * FROM stock_predictions 
            WHERE prediction_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
            ORDER BY prediction_date DESC, technical_score DESC
            LIMIT 100
        """, (days,))
        predictions = cursor.fetchall()
        return {"code": 0, "data": predictions}
    except Exception:
        # 表可能不存在
        return {"code": 0, "data": []}
    finally:
        cursor.close()
        conn.close()


@router.get("/prediction-accuracy")
async def get_prediction_accuracy(current_user: dict = Depends(get_current_user)):
    """获取预测准确率统计"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN predicted_return > 0 AND actual_return > 0 THEN 1
                         WHEN predicted_return < 0 AND actual_return < 0 THEN 1
                         ELSE 0 END) as correct,
                AVG(predicted_return) as avg_predicted,
                AVG(actual_return) as avg_actual
            FROM stock_predictions
            WHERE actual_return IS NOT NULL
            AND prediction_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
        """)
        stats = cursor.fetchone()
        
        if stats and stats['total'] and stats['total'] > 0:
            accuracy = (stats['correct'] / stats['total'] * 100)
        else:
            accuracy = 0
        
        return {
            "code": 0,
            "data": {
                "total_predictions": stats['total'] if stats else 0,
                "correct_predictions": stats['correct'] if stats else 0,
                "accuracy": round(accuracy, 2),
                "avg_predicted_return": round(stats['avg_predicted'] or 0, 4) if stats else 0,
                "avg_actual_return": round(stats['avg_actual'] or 0, 4) if stats else 0
            }
        }
    except Exception:
        # 表可能不存在
        return {
            "code": 0,
            "data": {
                "total_predictions": 0,
                "correct_predictions": 0,
                "accuracy": 0,
                "avg_predicted_return": 0,
                "avg_actual_return": 0
            }
        }
    finally:
        cursor.close()
        conn.close()
