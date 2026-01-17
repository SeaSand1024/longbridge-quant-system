"""
SSE (Server-Sent Events) 管理
"""
import asyncio
import json
import logging

logger = logging.getLogger(__name__)

# SSE连接管理
sse_clients = set()


async def notify_sse_clients(event_type: str, data: dict):
    """通知所有SSE客户端"""
    if not sse_clients:
        return
    
    message = json.dumps({
        'type': event_type,
        'data': data
    }, ensure_ascii=False, default=str)
    
    dead_clients = set()
    for client in sse_clients:
        try:
            await client.put(message)
        except Exception as e:
            logger.warning(f"SSE客户端通知失败: {e}")
            dead_clients.add(client)
    
    # 清理断开的客户端
    sse_clients.difference_update(dead_clients)
