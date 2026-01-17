"""
LLM客户端模拟器
"""
import random
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime


class MockLLMClient:
    """LLM客户端模拟器"""
    
    def __init__(self, simulate_errors: bool = False):
        self.simulate_errors = simulate_errors
        self.api_key = "mock_api_key"
        self.model = "gpt-3.5-turbo"
        self.request_count = 0
        self.total_tokens = 0
        
        # 预定义的股票分析响应
        self.stock_analysis_templates = {
            'bullish': {
                'recommendation': 'buy',
                'confidence': random.uniform(0.7, 0.9),
                'score': random.uniform(75, 95),
                'reasoning': '技术指标显示强劲上涨趋势，建议买入。RSI未超买，MACD金叉，成交量放大。'
            },
            'bearish': {
                'recommendation': 'sell',
                'confidence': random.uniform(0.6, 0.8),
                'score': random.uniform(20, 40),
                'reasoning': '技术指标显示下跌风险，建议卖出。RSI超买，MACD死叉，成交量萎缩。'
            },
            'neutral': {
                'recommendation': 'hold',
                'confidence': random.uniform(0.5, 0.7),
                'score': random.uniform(45, 65),
                'reasoning': '技术指标混合信号，建议观望。市场趋势不明确，等待更清晰信号。'
            }
        }
    
    async def analyze_stock(self, symbol: str, market_data: Dict[str, Any], 
                           technical_indicators: Dict[str, float]) -> Dict[str, Any]:
        """分析股票"""
        if self.simulate_errors and random.random() < 0.05:
            raise Exception("模拟LLM API调用失败")
        
        # 模拟API延迟
        await asyncio.sleep(random.uniform(0.5, 2.0))
        
        self.request_count += 1
        self.total_tokens += random.randint(500, 1500)
        
        # 根据技术指标选择分析模板
        rsi = technical_indicators.get('rsi', 50)
        macd = technical_indicators.get('macd', 0)
        change_pct = market_data.get('change_pct', 0)
        
        if rsi > 70 or macd < -0.5 or change_pct < -2:
            template_type = 'bearish'
        elif rsi < 30 or macd > 0.5 or change_pct > 2:
            template_type = 'bullish'
        else:
            template_type = 'neutral'
        
        template = self.stock_analysis_templates[template_type].copy()
        
        # 添加一些随机性
        template['confidence'] *= random.uniform(0.9, 1.1)
        template['score'] *= random.uniform(0.95, 1.05)
        
        # 限制范围
        template['confidence'] = max(0.1, min(1.0, template['confidence']))
        template['score'] = max(0, min(100, template['score']))
        
        return {
            'symbol': symbol,
            'recommendation': template['recommendation'],
            'confidence_score': round(template['confidence'], 3),
            'llm_score': round(template['score'], 1),
            'reasoning': template['reasoning'],
            'model': self.model,
            'timestamp': datetime.now(),
            'tokens_used': random.randint(400, 800),
            'analysis_details': {
                'trend_analysis': self._generate_trend_analysis(change_pct),
                'risk_assessment': self._generate_risk_assessment(rsi, macd),
                'price_target': self._generate_price_target(market_data.get('price', 100), template_type)
            }
        }
    
    async def batch_analyze_stocks(self, stocks_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量分析股票"""
        if self.simulate_errors and random.random() < 0.03:
            raise Exception("模拟批量LLM API调用失败")
        
        results = []
        for stock_data in stocks_data:
            symbol = stock_data['symbol']
            market_data = stock_data.get('market_data', {})
            technical_indicators = stock_data.get('technical_indicators', {})
            
            analysis = await self.analyze_stock(symbol, market_data, technical_indicators)
            results.append(analysis)
            
            # 模拟批量处理间隔
            await asyncio.sleep(0.1)
        
        return results
    
    async def get_market_sentiment(self, symbols: List[str]) -> Dict[str, Any]:
        """获取市场情绪分析"""
        if self.simulate_errors and random.random() < 0.02:
            raise Exception("模拟市场情绪分析失败")
        
        await asyncio.sleep(random.uniform(1.0, 3.0))
        
        sentiment_score = random.uniform(-1, 1)
        
        if sentiment_score > 0.3:
            sentiment = 'bullish'
            description = '市场情绪乐观，投资者信心较强'
        elif sentiment_score < -0.3:
            sentiment = 'bearish'
            description = '市场情绪悲观，投资者谨慎观望'
        else:
            sentiment = 'neutral'
            description = '市场情绪中性，观望情绪较重'
        
        return {
            'sentiment': sentiment,
            'sentiment_score': round(sentiment_score, 3),
            'description': description,
            'confidence': random.uniform(0.6, 0.9),
            'symbols_analyzed': symbols,
            'timestamp': datetime.now(),
            'factors': {
                'economic_indicators': random.choice(['positive', 'negative', 'neutral']),
                'news_sentiment': random.choice(['positive', 'negative', 'neutral']),
                'technical_momentum': random.choice(['strong', 'weak', 'neutral']),
                'volume_analysis': random.choice(['high', 'low', 'normal'])
            }
        }
    
    def _generate_trend_analysis(self, change_pct: float) -> str:
        """生成趋势分析"""
        if change_pct > 2:
            return "强劲上涨趋势，动能充足"
        elif change_pct > 0.5:
            return "温和上涨趋势，保持关注"
        elif change_pct < -2:
            return "明显下跌趋势，风险较高"
        elif change_pct < -0.5:
            return "轻微下跌趋势，需要谨慎"
        else:
            return "横盘整理，方向不明"
    
    def _generate_risk_assessment(self, rsi: float, macd: float) -> str:
        """生成风险评估"""
        risk_factors = []
        
        if rsi > 70:
            risk_factors.append("RSI超买")
        elif rsi < 30:
            risk_factors.append("RSI超卖")
        
        if macd < -0.5:
            risk_factors.append("MACD弱势")
        elif macd > 0.5:
            risk_factors.append("MACD强势")
        
        if not risk_factors:
            return "风险适中，技术指标正常"
        else:
            return f"注意风险: {', '.join(risk_factors)}"
    
    def _generate_price_target(self, current_price: float, template_type: str) -> Dict[str, float]:
        """生成价格目标"""
        if template_type == 'bullish':
            target = current_price * random.uniform(1.05, 1.15)
            stop_loss = current_price * random.uniform(0.95, 0.98)
        elif template_type == 'bearish':
            target = current_price * random.uniform(0.85, 0.95)
            stop_loss = current_price * random.uniform(1.02, 1.05)
        else:
            target = current_price * random.uniform(0.98, 1.02)
            stop_loss = current_price * random.uniform(0.97, 1.03)
        
        return {
            'target_price': round(target, 2),
            'stop_loss': round(stop_loss, 2),
            'risk_reward_ratio': round(abs(target - current_price) / abs(stop_loss - current_price), 2)
        }
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """获取使用统计"""
        return {
            'total_requests': self.request_count,
            'total_tokens': self.total_tokens,
            'average_tokens_per_request': self.total_tokens / max(self.request_count, 1),
            'estimated_cost': self.total_tokens * 0.002 / 1000  # 模拟成本计算
        }


def create_mock_llm_client(simulate_errors: bool = False) -> MockLLMClient:
    """创建LLM客户端模拟器实例"""
    return MockLLMClient(simulate_errors=simulate_errors)


def patch_llm_client(monkeypatch, simulate_errors: bool = False):
    """使用pytest monkeypatch替换LLM客户端"""
    mock_client = create_mock_llm_client(simulate_errors)
    
    # 替换LLM相关的导入
    monkeypatch.setattr("app.services.smart_trader.OpenAI", lambda *args, **kwargs: mock_client)
    monkeypatch.setattr("openai.AsyncOpenAI", lambda *args, **kwargs: mock_client)
    
    return mock_client