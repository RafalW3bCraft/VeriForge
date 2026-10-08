from typing import Any, TypeVar

from config import get_settings
from integrations.featherless import get_featherless_client
from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)

def demo_mode():
    return get_settings().demo_mode

async def llm_json(
    task: str,
    payload: dict[str, Any],
    response_model: type[ModelT],
) -> ModelT:
    return await get_featherless_client().complete_json(
        task, payload, response_model
    )
