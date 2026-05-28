import redis
import json
import logging
from config import REDIS_HOST, REDIS_PORT, REDIS_DB

logger = logging.getLogger(__name__)

class RedisCache:
    def __init__(self):
        try:
            self.redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=5
            )
            self.redis_client.ping()
            self.enabled = True
            logger.info("Redis cache initialized successfully")
        except Exception as e:
            logger.warning(f"Redis not available: {e}. Cache disabled.")
            self.enabled = False
            self.redis_client = None
    
    def get_user(self, telegram_id: int):
        if not self.enabled:
            return None
        try:
            data = self.redis_client.get(f"user:{telegram_id}")
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    def set_user(self, telegram_id: int, user_data: dict, ttl: int = 300):
        if not self.enabled:
            return
        try:
            self.redis_client.setex(f"user:{telegram_id}", ttl, json.dumps(user_data, default=str))
        except Exception as e:
            logger.error(f"Redis set error: {e}")
    
    def delete_user(self, telegram_id: int):
        if not self.enabled:
            return
        try:
            self.redis_client.delete(f"user:{telegram_id}")
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
    
    def clear_all(self):
        if not self.enabled:
            return
        try:
            self.redis_client.flushdb()
            logger.info("Redis cache cleared")
        except Exception as e:
            logger.error(f"Redis clear error: {e}")

redis_cache = RedisCache()