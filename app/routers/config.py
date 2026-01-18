"""
系统配置路由
"""
from fastapi import APIRouter, Depends
import pymysql
import httpx
import logging

from app.config.database import get_db_connection
from app.config.settings import CONFIG_DEFINITIONS, ensure_default_system_configs
from app.auth.utils import get_current_user

router = APIRouter(prefix="/api/config", tags=["配置"])
logger = logging.getLogger(__name__)


@router.get("")
async def get_config(current_user: dict = Depends(get_current_user)):
    """获取系统配置"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        ensure_default_system_configs(cursor)
        conn.commit()
        
        cursor.execute("SELECT * FROM system_config")
        configs = cursor.fetchall()
        
        config_dict = {c['config_key']: c['config_value'] for c in configs}
        
        return {
            "code": 0,
            "data": {
                "configs": config_dict,
                "values": config_dict,  # 前端兼容字段
                "definitions": CONFIG_DEFINITIONS
            }
        }
    finally:
        cursor.close()
        conn.close()


@router.put("")
async def update_config(config: dict, current_user: dict = Depends(get_current_user)):
    """更新系统配置"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        config_key = config.get('config_key')
        config_value = config.get('config_value')
        
        if not config_key:
            return {"code": 1, "message": "配置键不能为空"}
        
        cursor.execute("""
            INSERT INTO system_config (config_key, config_value) VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)
        """, (config_key, str(config_value)))
        
        conn.commit()
        
        # 更新交易策略配置
        from app.services.trading_strategy import trading_strategy
        await trading_strategy.load_config()
        
        return {"code": 0, "message": "配置已更新"}
    finally:
        cursor.close()
        conn.close()


@router.get("/llm-models")
async def get_llm_models(current_user: dict = Depends(get_current_user)):
    """获取可用的 LLM 模型列表"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        # 获取当前 LLM 配置
        cursor.execute("SELECT config_key, config_value FROM system_config WHERE config_key IN ('llm_provider', 'llm_api_base')")
        configs = {row['config_key']: row['config_value'] for row in cursor.fetchall()}
        
        provider = configs.get('llm_provider', 'openai')
        api_base = configs.get('llm_api_base', '')
        
        models = []
        
        if provider == 'ollama':
            # 查询 Ollama 本地模型
            try:
                ollama_url = api_base.replace('/v1', '') if api_base.endswith('/v1') else api_base
                if not ollama_url:
                    ollama_url = 'http://localhost:11434'
                
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(f"{ollama_url}/api/tags")
                    if response.status_code == 200:
                        data = response.json()
                        for model in data.get('models', []):
                            model_name = model.get('name', '')
                            model_size = model.get('details', {}).get('parameter_size', '')
                            model_family = model.get('details', {}).get('family', '')
                            is_cloud = 'cloud' in model_name.lower()
                            
                            models.append({
                                'name': model_name,
                                'size': model_size,
                                'family': model_family,
                                'type': 'cloud' if is_cloud else 'local',
                                'description': f"{model_family} {model_size}" + (" (云端)" if is_cloud else " (本地)")
                            })
            except Exception as e:
                logger.warning(f"获取 Ollama 模型列表失败: {e}")
                # 返回默认模型
                models = [
                    {'name': 'deepseek-r1:1.5b', 'size': '1.5B', 'family': 'qwen2', 'type': 'local', 'description': 'DeepSeek R1 1.5B (本地)'},
                    {'name': 'llama3:8b', 'size': '8B', 'family': 'llama', 'type': 'local', 'description': 'Llama 3 8B (本地)'},
                    {'name': 'qwen2:7b', 'size': '7B', 'family': 'qwen2', 'type': 'local', 'description': 'Qwen2 7B (本地)'},
                ]
        else:
            # OpenAI 或其他提供商的预设模型
            models = [
                {'name': 'gpt-4o-mini', 'size': '', 'family': 'gpt', 'type': 'cloud', 'description': 'GPT-4o Mini (快速/便宜)'},
                {'name': 'gpt-4o', 'size': '', 'family': 'gpt', 'type': 'cloud', 'description': 'GPT-4o (推荐)'},
                {'name': 'gpt-4-turbo', 'size': '', 'family': 'gpt', 'type': 'cloud', 'description': 'GPT-4 Turbo'},
                {'name': 'gpt-3.5-turbo', 'size': '', 'family': 'gpt', 'type': 'cloud', 'description': 'GPT-3.5 Turbo (经济)'},
            ]
        
        return {
            "code": 0,
            "data": {
                "provider": provider,
                "api_base": api_base,
                "models": models
            }
        }
    except Exception as e:
        logger.error(f"获取 LLM 模型列表失败: {e}")
        return {"code": 1, "message": str(e)}
    finally:
        cursor.close()
        conn.close()
