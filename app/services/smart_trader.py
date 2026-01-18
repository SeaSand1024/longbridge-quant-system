"""
智能预测交易系统
"""
import json
import logging
import re
import asyncio
import httpx
import pymysql
from datetime import datetime
from typing import List

from app.config.database import get_db_connection
from app.auth.utils import is_test_mode

logger = logging.getLogger(__name__)


class SmartPredictionTrader:
    """
    智能预测交易系统
    - 每天开盘前预测收益最好的股票
    - 开盘时自动买入预测收益最高的股票
    - 实时监控，在收益最高点自动卖出
    - 支持大模型辅助预测
    """
    
    def __init__(self):
        self.is_enabled = False
        self.max_daily_trades = 3
        self.buy_amount = 200000.0
        self.min_prediction_score = 60
        self.dynamic_stop_profit = True
        self.base_profit_target = 1.0
        self.trailing_stop = 0.5
        self.max_hold_days = 5
        self.peak_prices = {}
        
        # LLM配置
        self.llm_enabled = False
        self.llm_provider = 'openai'
        self.llm_api_key = ''
        self.llm_api_base = 'https://api.openai.com/v1'
        self.llm_model = 'gpt-4o-mini'
        self.llm_weight = 0.3
        self.llm_cache = {}

    async def load_config(self):
        """从数据库加载配置"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            config_keys = [
                'smart_trade_enabled', 'smart_max_daily_trades', 'smart_buy_amount',
                'smart_min_score', 'smart_dynamic_stop', 'smart_base_profit',
                'smart_trailing_stop', 'smart_max_hold_days',
                'llm_enabled', 'llm_provider', 'llm_api_key', 'llm_api_base',
                'llm_model', 'llm_weight'
            ]
            
            cursor.execute(
                "SELECT config_key, config_value FROM system_config WHERE config_key IN %s",
                (config_keys,)
            )
            configs = {row['config_key']: row['config_value'] for row in cursor.fetchall()}
            
            self.is_enabled = configs.get('smart_trade_enabled', 'false').lower() == 'true'
            self.max_daily_trades = int(configs.get('smart_max_daily_trades', '3'))
            self.buy_amount = float(configs.get('smart_buy_amount', '200000'))
            self.min_prediction_score = float(configs.get('smart_min_score', '60'))
            self.dynamic_stop_profit = configs.get('smart_dynamic_stop', 'true').lower() == 'true'
            self.base_profit_target = float(configs.get('smart_base_profit', '1.0'))
            self.trailing_stop = float(configs.get('smart_trailing_stop', '0.5'))
            self.max_hold_days = int(configs.get('smart_max_hold_days', '5'))
            
            self.llm_enabled = configs.get('llm_enabled', 'false').lower() == 'true'
            self.llm_provider = configs.get('llm_provider', 'openai')
            self.llm_api_key = configs.get('llm_api_key', '')
            self.llm_api_base = configs.get('llm_api_base', 'https://api.openai.com/v1')
            self.llm_model = configs.get('llm_model', 'gpt-4o-mini')
            self.llm_weight = float(configs.get('llm_weight', '0.3'))
            
            cursor.close()
            conn.close()
            logger.info(f"智能交易配置已加载: enabled={self.is_enabled}, llm_enabled={self.llm_enabled}")
        except Exception as e:
            logger.warning(f"加载智能交易配置失败: {e}")

    async def get_historical_data(self, symbol: str, days: int = 30) -> list:
        """获取历史K线数据"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            cursor.execute("""
                SELECT trade_date, open_price, high_price, low_price, close_price, volume, change_pct
                FROM stock_kline_cache
                WHERE symbol = %s AND trade_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                ORDER BY trade_date ASC
            """, (symbol, days))
            cached_data = cursor.fetchall()
            
            if len(cached_data) >= days * 0.7:
                cursor.close()
                conn.close()
                return cached_data
            
            # 从SDK获取
            from .longbridge_sdk import longbridge_sdk
            klines = await longbridge_sdk.get_stock_history(symbol, period='day', count=days)
            
            for kline in klines:
                try:
                    cursor.execute("""
                        INSERT INTO stock_kline_cache 
                        (symbol, trade_date, open_price, high_price, low_price, close_price, volume, change_pct)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        close_price = VALUES(close_price), change_pct = VALUES(change_pct)
                    """, (
                        symbol, kline.get('date'), kline.get('open'), kline.get('high'),
                        kline.get('low'), kline.get('close'), kline.get('volume'),
                        kline.get('change_pct', 0)
                    ))
                except:
                    pass
            
            conn.commit()
            cursor.close()
            conn.close()
            return klines
        except Exception as e:
            logger.error(f"获取历史数据失败 {symbol}: {e}")
            return []

    def calculate_technical_indicators(self, data: list) -> dict:
        """计算技术指标"""
        if not data or len(data) < 10:
            return {'rsi': 50, 'macd_signal': 0, 'ma_trend': 0, 'volatility': 0, 'momentum': 0}
        
        closes = [float(d.get('close_price') or d.get('close', 0)) for d in data]
        highs = [float(d.get('high_price') or d.get('high', 0)) for d in data]
        lows = [float(d.get('low_price') or d.get('low', 0)) for d in data]
        
        return {
            'rsi': self._calculate_rsi(closes, 14),
            'macd_signal': self._calculate_macd_signal(closes),
            'ma_trend': self._calculate_ma_trend(closes),
            'volatility': self._calculate_volatility(highs, lows, closes),
            'momentum': self._calculate_momentum(closes)
        }

    def _calculate_rsi(self, closes: list, period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50
        gains, losses = [], []
        for i in range(1, len(closes)):
            change = closes[i] - closes[i-1]
            gains.append(change if change > 0 else 0)
            losses.append(abs(change) if change < 0 else 0)
        if len(gains) < period:
            return 50
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 2)

    def _calculate_macd_signal(self, closes: list) -> float:
        if len(closes) < 26:
            return 0
        ema12 = self._ema(closes, 12)
        ema26 = self._ema(closes, 26)
        macd = ema12 - ema26
        if closes[-1] != 0:
            signal = macd / closes[-1] * 100
            return max(-1, min(1, signal / 2))
        return 0

    def _ema(self, data: list, period: int) -> float:
        if len(data) < period:
            return data[-1] if data else 0
        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period
        for price in data[period:]:
            ema = (price - ema) * multiplier + ema
        return ema

    def _calculate_ma_trend(self, closes: list) -> float:
        if len(closes) < 20:
            return 0
        ma5 = sum(closes[-5:]) / 5
        ma10 = sum(closes[-10:]) / 10
        ma20 = sum(closes[-20:]) / 20
        score = 0
        if closes[-1] > ma5:
            score += 0.3
        if ma5 > ma10:
            score += 0.3
        if ma10 > ma20:
            score += 0.4
        return score * 2 - 1

    def _calculate_volatility(self, highs: list, lows: list, closes: list) -> float:
        if len(closes) < 14:
            return 0
        tr_list = []
        for i in range(1, len(closes)):
            tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
            tr_list.append(tr)
        atr = sum(tr_list[-14:]) / 14
        if closes[-1] != 0:
            return round(atr / closes[-1] * 100, 2)
        return 0

    def _calculate_momentum(self, closes: list) -> float:
        if len(closes) < 10:
            return 0
        return round((closes[-1] - closes[-10]) / closes[-10] * 100, 2) if closes[-10] != 0 else 0

    def _extract_llm_fields(self, content: str) -> dict:
        """从非标准JSON内容中尽力提取字段"""
        result = {
            'score': 50,
            'recommendation': 'hold',
            'confidence': 0,
            'reasons': [],
            'predicted_change': 0
        }

        if not content:
            return result

        score_m = re.search(r'"score"\s*:\s*([0-9]+(?:\.[0-9]+)?)', content)
        if score_m:
            result['score'] = float(score_m.group(1))

        rec_m = re.search(r'"recommendation"\s*:\s*"?([a-zA-Z]+)"?', content)
        if rec_m:
            rec = rec_m.group(1).lower()
            if rec in ('buy', 'hold', 'sell'):
                result['recommendation'] = rec

        conf_m = re.search(r'"confidence"\s*:\s*([0-9]+(?:\.[0-9]+)?)', content)
        if conf_m:
            result['confidence'] = float(conf_m.group(1))

        pred_m = re.search(r'"predicted_change"\s*:\s*"?([^",}\n]+)', content)
        if pred_m:
            result['predicted_change'] = pred_m.group(1).strip()

        reasons_m = re.search(r'"reasons"\s*:\s*\[(.*?)\]', content, re.DOTALL)
        if reasons_m:
            reasons_block = reasons_m.group(1)
            reasons = re.findall(r'"(.*?)"', reasons_block)
            if reasons:
                result['reasons'] = reasons

        return result

    async def predict_stock_return(self, symbol: str) -> dict:
        """预测股票收益（技术指标）"""
        try:
            historical_data = await self.get_historical_data(symbol, 30)
            if not historical_data or len(historical_data) < 10:
                return {'symbol': symbol, 'score': 0, 'predicted_return': 0, 'confidence': 0, 'source': 'technical'}
            
            indicators = self.calculate_technical_indicators(historical_data)
            score = 0
            
            # RSI评分
            rsi = indicators['rsi']
            if rsi < 30:
                score += 35
            elif 30 <= rsi < 40:
                score += 30
            elif 40 <= rsi <= 60:
                score += 25
            elif 60 < rsi <= 70:
                score += 20
            else:
                score += 10
            
            # MACD评分
            macd = indicators['macd_signal']
            score += 25 if macd > 0.3 else 20 if macd > 0 else 15 if macd > -0.3 else 5
            
            # 均线趋势评分
            ma_trend = indicators['ma_trend']
            score += 25 if ma_trend > 0.5 else 20 if ma_trend > 0 else 10 if ma_trend > -0.5 else 5
            
            # 动量评分
            momentum = indicators['momentum']
            score += 15 if momentum > 5 else 12 if momentum > 0 else 8 if momentum > -5 else 3
            
            # 波动率调整
            volatility = indicators['volatility']
            score += 10 if 1 <= volatility <= 3 else 5 if volatility < 1 else -5
            
            predicted_return = (score - 50) * 0.05
            confidence = min(0.9, len(historical_data) / 30 * 0.5 + abs(ma_trend) * 0.3 + 0.2)
            
            return {
                'symbol': symbol,
                'score': round(score, 2),
                'predicted_return': round(predicted_return, 4),
                'confidence': round(confidence, 4),
                'indicators': indicators,
                'source': 'technical'
            }
        except Exception as e:
            logger.error(f"预测股票收益失败 {symbol}: {e}")
            return {'symbol': symbol, 'score': 0, 'predicted_return': 0, 'confidence': 0, 'source': 'technical'}

    async def llm_analyze_stock(self, symbol: str, historical_data: list, indicators: dict) -> dict:
        """使用大模型分析股票"""
        # Ollama等本地模型不需要API Key
        llm_configured = self.llm_api_key or self.llm_provider == 'ollama'
        if not self.llm_enabled or not llm_configured:
            return {'score': 50, 'analysis': '', 'recommendation': 'hold', 'confidence': 0}
        
        cache_key = f"{symbol}_{datetime.now().strftime('%Y%m%d')}"
        if cache_key in self.llm_cache:
            return self.llm_cache[cache_key]
        
        try:
            recent_data = historical_data[-10:] if len(historical_data) >= 10 else historical_data
            price_summary = []
            for d in recent_data:
                close = float(d.get('close_price') or d.get('close', 0))
                change = float(d.get('change_pct', 0))
                date_str = str(d.get('trade_date') or d.get('date', ''))[:10]
                price_summary.append(f"{date_str}: ${close:.2f} ({change:+.2f}%)")
            
            # 判断是否为云端模型，需要联网搜索
            is_cloud_model = 'cloud' in self.llm_model.lower()
            
            if is_cloud_model:
                # 云端模型使用联网搜索，获取最新新闻和市场情绪
                prompt = f"""你是一位专业的股票分析师。请分析以下美股的短期走势并给出买入建议。

**重要：请先联网搜索该股票最新的新闻、财报、分析师评级等信息，结合实时市场数据进行分析。**

股票代码: {symbol}

最近10日价格走势:
{chr(10).join(price_summary)}

技术指标:
- RSI(14): {indicators.get('rsi', 50):.2f}
- MACD信号: {indicators.get('macd_signal', 0):.4f}
- 均线趋势: {indicators.get('ma_trend', 0):.4f}
- 波动率(ATR%): {indicators.get('volatility', 0):.2f}
- 10日动量: {indicators.get('momentum', 0):.2f}%

请综合以下因素进行分析：
1. 最新公司新闻和公告
2. 近期财报表现
3. 分析师评级变化
4. 行业趋势和竞争对手动态
5. 宏观经济因素影响
6. 技术面分析

请以JSON格式回答:
{{"score": 预测得分(0-100), "recommendation": "buy"或"hold"或"sell", "confidence": 置信度(0-1), "reasons": ["原因1", "原因2", "原因3"], "predicted_change": 预测涨跌幅百分比, "news_summary": "相关新闻摘要"}}

仅返回JSON，不要有其他内容。"""
                system_prompt = '你是专业的量化交易分析师，具备联网搜索能力。请先搜索最新信息再进行分析，用JSON格式回答。'
            else:
                # 本地模型使用基础prompt
                prompt = f"""你是一位专业的股票分析师。请分析以下美股的短期走势并给出买入建议。

股票代码: {symbol}

最近10日价格走势:
{chr(10).join(price_summary)}

技术指标:
- RSI(14): {indicators.get('rsi', 50):.2f}
- MACD信号: {indicators.get('macd_signal', 0):.4f}
- 均线趋势: {indicators.get('ma_trend', 0):.4f}
- 波动率(ATR%): {indicators.get('volatility', 0):.2f}
- 10日动量: {indicators.get('momentum', 0):.2f}%

请以JSON格式回答:
{{"score": 预测得分(0-100), "recommendation": "buy"或"hold"或"sell", "confidence": 置信度(0-1), "reasons": ["原因1", "原因2"], "predicted_change": 预测涨跌幅}}

仅返回JSON。"""
                system_prompt = '你是专业的量化交易分析师，用JSON格式回答。'

            # 构建请求参数
            request_body = {
                'model': self.llm_model,
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': prompt}
                ],
                'max_tokens': 1000 if is_cloud_model else 800,
                'temperature': 0.3
            }
            
            # 为云端模型添加联网工具（如果Ollama支持）
            if is_cloud_model:
                # Ollama云端模型通过 options 启用联网
                request_body['options'] = {
                    'num_predict': 1000
                }
                # 增加超时时间，因为联网搜索需要更长时间
                timeout = 60.0
                logger.info(f"使用云端模型 {self.llm_model} 分析 {symbol}，已启用联网搜索")
            else:
                timeout = 30.0

            async with httpx.AsyncClient(timeout=timeout) as client:
                # Ollama 不需要 Authorization header
                headers = {'Content-Type': 'application/json'}
                if self.llm_api_key:
                    headers['Authorization'] = f'Bearer {self.llm_api_key}'
                
                response = await client.post(
                    f"{self.llm_api_base}/chat/completions",
                    headers=headers,
                    json=request_body
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result.get('choices', [{}])[0].get('message', {}).get('content', '{}')
                    content = content.strip()
                    
                    # 处理 deepseek 的思考标签（先处理，因为JSON可能在思考标签之后）
                    if '<think>' in content:
                        think_end = content.find('</think>')
                        if think_end != -1:
                            content = content[think_end + 8:].strip()
                    
                    # 优先提取代码块中的JSON
                    fenced = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content, re.IGNORECASE)
                    if fenced:
                        content = fenced.group(1).strip()
                    
                    # 尝试从内容中提取JSON对象
                    if not content.startswith('{'):
                        match = re.search(r'\{[\s\S]*\}', content)
                        if match:
                            content = match.group(0)
                    
                    content = content.strip()
                    logger.debug(f"LLM返回内容解析: {content[:300]}")
                    
                    if not content or content in ('```', '```json'):
                        logger.info(f"LLM返回空JSON内容 {symbol}")
                        return {'score': 50, 'analysis': '', 'recommendation': 'hold', 'confidence': 0}
                    
                    # 只有代码块但没有JSON对象
                    if '```' in content and '{' not in content:
                        logger.info(f"LLM返回仅代码块无JSON {symbol}: {content[:50]}")
                        return {'score': 50, 'analysis': '', 'recommendation': 'hold', 'confidence': 0}
                    
                    try:
                        llm_result = json.loads(content)
                    except json.JSONDecodeError:
                        llm_result = self._extract_llm_fields(content)
                        logger.info(f"LLM返回非标准JSON，已使用兜底解析 {symbol}")
                    
                    def to_float(value, default=0.0):
                        if isinstance(value, (int, float)):
                            return float(value)
                        if isinstance(value, str):
                            s = value.strip().replace('%', '')
                            m = re.search(r'-?\d+(?:\.\d+)?', s)
                            if m:
                                return float(m.group(0))
                        return default
                    
                    llm_result['score'] = to_float(llm_result.get('score', 50), 50)
                    llm_result['confidence'] = to_float(llm_result.get('confidence', 0), 0)
                    llm_result['predicted_change'] = to_float(llm_result.get('predicted_change', 0), 0)
                    
                    llm_result['analysis'] = '; '.join(llm_result.get('reasons', []))
                    if llm_result.get('news_summary'):
                        llm_result['analysis'] += f" [新闻] {llm_result['news_summary']}"
                    llm_result['source'] = 'llm_cloud' if is_cloud_model else 'llm'
                    self.llm_cache[cache_key] = llm_result
                    
                    logger.info(f"LLM分析完成 {symbol}: score={llm_result.get('score')}, source={llm_result['source']}")
                    return llm_result
                else:
                    logger.info(f"LLM请求失败 {symbol}: HTTP {response.status_code} - {response.text[:200]}")
                    
        except Exception as e:
            msg = str(e).strip()
            if msg:
                logger.info(f"LLM分析失败 {symbol}: {msg}")
            else:
                logger.debug(f"LLM分析失败 {symbol}: unknown_error")
        
        return {'score': 50, 'analysis': '', 'recommendation': 'hold', 'confidence': 0}

    async def hybrid_predict(self, symbol: str) -> dict:
        """混合预测：技术指标 + LLM"""
        try:
            historical_data = await self.get_historical_data(symbol, 30)
            if not historical_data or len(historical_data) < 10:
                return {'symbol': symbol, 'score': 0, 'predicted_return': 0, 'confidence': 0, 'source': 'insufficient_data'}
            
            tech_prediction = await self.predict_stock_return(symbol)
            
            # Ollama等本地模型不需要API Key
            llm_configured = self.llm_api_key or self.llm_provider == 'ollama'
            if not self.llm_enabled or not llm_configured:
                return tech_prediction
            
            indicators = self.calculate_technical_indicators(historical_data)
            llm_result = await self.llm_analyze_stock(symbol, historical_data, indicators)
            
            tech_weight = 1 - self.llm_weight
            tech_score = tech_prediction.get('score', 50)
            llm_score = llm_result.get('score', 50)
            
            hybrid_score = tech_score * tech_weight + llm_score * self.llm_weight
            
            recommendation = llm_result.get('recommendation', 'hold')
            if recommendation == 'buy' and llm_result.get('confidence', 0) > 0.7:
                hybrid_score = min(100, hybrid_score + 5)
            elif recommendation == 'sell' and llm_result.get('confidence', 0) > 0.7:
                hybrid_score = max(0, hybrid_score - 10)
            
            tech_confidence = tech_prediction.get('confidence', 0.5)
            llm_confidence = llm_result.get('confidence', 0.5)
            hybrid_confidence = tech_confidence * tech_weight + llm_confidence * self.llm_weight
            
            llm_predicted_change = llm_result.get('predicted_change', 0)
            tech_predicted_return = tech_prediction.get('predicted_return', 0)
            hybrid_return = tech_predicted_return * tech_weight + llm_predicted_change * self.llm_weight
            
            return {
                'symbol': symbol,
                'score': round(hybrid_score, 2),
                'predicted_return': round(hybrid_return, 4),
                'confidence': round(hybrid_confidence, 4),
                'source': 'hybrid',
                'technical_score': tech_score,
                'llm_score': llm_score,
                'llm_recommendation': recommendation,
                'llm_analysis': llm_result.get('analysis', ''),
                'indicators': indicators
            }
        except Exception as e:
            logger.info(f"混合预测失败 {symbol}: {e}")
            return await self.predict_stock_return(symbol)

    async def run_daily_prediction(self) -> list:
        """运行每日预测"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            cursor.execute("SELECT symbol FROM stocks WHERE is_active = 1 AND stock_type = 'STOCK'")
            stocks = cursor.fetchall()
            
            predictions = []
            # Ollama等本地模型不需要API Key
            llm_configured = self.llm_api_key or self.llm_provider == 'ollama'
            llm_status = "启用" if (self.llm_enabled and llm_configured) else "未启用"
            logger.info(f"开始每日预测，共{len(stocks)}只股票，LLM辅助: {llm_status}")
            
            for stock in stocks:
                symbol = stock['symbol']
                prediction = await self.hybrid_predict(symbol)
                predictions.append(prediction)
                
                db_symbol = str(symbol)[:10]
                if db_symbol != symbol:
                    logger.info(f"预测结果symbol过长，已截断: {symbol} -> {db_symbol}")
                
                # 保存结果（带重试，避免锁等待超时）
                for attempt in range(3):
                    try:
                        cursor.execute("""
                            INSERT INTO stock_predictions 
                            (symbol, prediction_date, predicted_return, confidence_score, technical_score, 
                             llm_score, llm_recommendation, llm_analysis)
                            VALUES (%s, CURDATE(), %s, %s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                            predicted_return = VALUES(predicted_return),
                            confidence_score = VALUES(confidence_score),
                            technical_score = VALUES(technical_score),
                            llm_score = VALUES(llm_score),
                            llm_recommendation = VALUES(llm_recommendation),
                            llm_analysis = VALUES(llm_analysis)
                        """, (
                            db_symbol, 
                            prediction.get('predicted_return', 0), 
                            prediction.get('confidence', 0), 
                            prediction.get('technical_score', prediction.get('score', 0)),
                            prediction.get('llm_score'),
                            prediction.get('llm_recommendation'),
                            prediction.get('llm_analysis', '')[:500]
                        ))
                        conn.commit()
                        break
                    except pymysql.err.OperationalError as e:
                        if e.args and e.args[0] in (1205, 1213) and attempt < 2:
                            await asyncio.sleep(0.2 * (attempt + 1))
                            continue
                        logger.info(f"保存预测结果失败 {symbol}: {e}")
                        break
                    except Exception as e:
                        logger.info(f"保存预测结果失败 {symbol}: {e}")
                        break
            
            conn.commit()
            cursor.close()
            conn.close()
            
            predictions.sort(key=lambda x: x['score'], reverse=True)
            logger.info(f"每日预测完成，共预测{len(predictions)}只股票")
            return predictions
        except Exception as e:
            logger.info(f"运行每日预测失败: {e}")
            return []

    async def get_top_recommendations(self, limit: int = 3) -> list:
        """获取最佳买入推荐股票"""
        from .longbridge_sdk import longbridge_sdk
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            # 获取活跃股票列表
            cursor.execute("SELECT symbol FROM stocks WHERE is_active = 1 LIMIT 20")
            stocks = cursor.fetchall()
            cursor.close()
            conn.close()
            
            if not stocks:
                return []
            
            symbols = [s['symbol'] for s in stocks]
            recommendations = []
            
            # 获取实时行情
            quotes = await longbridge_sdk.get_realtime_quote(symbols)
            
            for quote in quotes:
                symbol = quote.get('symbol', '')
                price = quote.get('price', 0)
                change_pct = quote.get('change_pct', 0)
                
                if price <= 0:
                    continue
                
                # 获取预测数据
                prediction = await self.hybrid_predict(symbol)
                
                if prediction.get('final_score', 0) >= self.min_prediction_score:
                    recommendations.append({
                        'symbol': symbol,
                        'price': price,
                        'change_pct': change_pct,
                        'score': prediction.get('final_score', 0),
                        'predicted_return': prediction.get('predicted_return', 0),
                        'recommendation': prediction.get('recommendation', 'hold'),
                        'acceleration': 0
                    })
            
            # 按评分排序
            recommendations.sort(key=lambda x: x['score'], reverse=True)
            
            return recommendations[:limit]
        except Exception as e:
            logger.info(f"获取买入推荐失败: {e}")
            return []

    def get_status(self) -> dict:
        """获取智能交易状态"""
        # Ollama等本地模型不需要API Key
        llm_configured = bool(self.llm_api_key) or self.llm_provider == 'ollama'
        return {
            'enabled': self.is_enabled,
            'max_daily_trades': self.max_daily_trades,
            'buy_amount': self.buy_amount,
            'min_prediction_score': self.min_prediction_score,
            'dynamic_stop_profit': self.dynamic_stop_profit,
            'base_profit_target': self.base_profit_target,
            'trailing_stop': self.trailing_stop,
            'max_hold_days': self.max_hold_days,
            'tracking_positions': list(self.peak_prices.keys()),
            'llm_enabled': self.llm_enabled,
            'llm_provider': self.llm_provider,
            'llm_api_base': self.llm_api_base,
            'llm_model': self.llm_model,
            'llm_weight': self.llm_weight,
            'llm_configured': llm_configured
        }


# 全局实例
smart_trader = SmartPredictionTrader()
