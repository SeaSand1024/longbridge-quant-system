"""
异步任务队列
"""
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class AsyncTaskQueue:
    """异步任务队列，用于分离监控任务和API请求"""
    
    def __init__(self):
        self.queue = asyncio.Queue()
        self.is_running = False
        self.worker_task = None
    
    async def start(self):
        """启动任务队列"""
        if self.is_running:
            return
        self.is_running = True
        self.worker_task = asyncio.create_task(self._worker())
        logger.info("异步任务队列已启动")
    
    async def stop(self):
        """停止任务队列"""
        self.is_running = False
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        logger.info("异步任务队列已停止")
    
    async def add_task(self, task_func, *args, **kwargs):
        """添加任务到队列"""
        await self.queue.put((task_func, args, kwargs))
    
    async def _worker(self):
        """任务处理工作器"""
        while self.is_running:
            try:
                task_func, args, kwargs = await asyncio.wait_for(
                    self.queue.get(), timeout=1.0
                )
                try:
                    if asyncio.iscoroutinefunction(task_func):
                        await task_func(*args, **kwargs)
                    else:
                        task_func(*args, **kwargs)
                except Exception as e:
                    logger.error(f"任务执行失败: {e}")
                finally:
                    self.queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break


# 全局实例
task_queue = AsyncTaskQueue()
