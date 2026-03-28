import json
from typing import Optional, Any
from app.schemas.requirement_agent import RequirementContext
from app.services.redis import get_redis
import redis.asyncio as redis
import logging
from fastapi import Depends

logger = logging.getLogger(__name__)

class RequirementsContextManager:
    def __init__(self, redis: redis.Redis):
        self.ttl = 3600
        self.redis = redis

    def _key(self, session_id: str) -> str:
        return f"requirements.context:{session_id}"

    async def get_context(self, session_id: str) -> Optional[RequirementContext]:
        try:
            data = await self.redis.get(self._key(session_id))
            if data:
                return RequirementContext.model_validate_json(data)
            return None
        except Exception:
            logger.exception("Error fetching context")
            raise

    async def save_context(self, session_id: str, context: RequirementContext):
        try:
            await self.redis.setex(
                self._key(session_id),
                self.ttl,
                context.model_dump_json()
            )
        except Exception:
            logger.exception("Error saving context")
            raise

    async def update_context_field(self, session_id: str, field: str, value: Any):
        try:
            context = await self.get_context(session_id)
            if not context:
                raise ValueError(f"No context for session_id={session_id}")

            setattr(context, field, value)
            await self.save_context(session_id, context)

        except Exception:
            logger.exception("Error updating context")
            raise

    async def delete_context(self, session_id: str):
        try:
            await self.redis.delete(self._key(session_id))
        except Exception:
            logger.exception("Error deleting context")
            raise