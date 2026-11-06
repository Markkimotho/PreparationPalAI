"""Small, validated structured-output batches for constrained local models."""
from collections.abc import Callable
from copy import deepcopy
import logging

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


def validation_feedback(exc: Exception):
    if isinstance(exc, ValidationError):
        return [{'path': error['loc'], 'message': error['msg']} for error in exc.errors(include_input=False)]
    return {'message': str(exc)}


def validated_batches(llm, render: Callable, parse: Callable, batch_model: type[BaseModel],
                      n: int, key: str, unique_key: str, validate: Callable | None = None,
                      schema: dict | None = None) -> list[dict]:
    items = []
    seen = set()
    while len(items) < n:
        count = min(2, n - len(items))
        batch_schema = deepcopy(schema or batch_model.model_json_schema())
        batch_schema['properties'][key]['maxItems'] = count
        feedback = None
        for attempt in range(2):
            try:
                response = llm.invoke([HumanMessage(content=render(count, items, bool(attempt), batch_schema, feedback))], format=batch_schema)
                if getattr(response, 'response_metadata', {}).get('done_reason') == 'length':
                    raise ValueError('Output limit reached')
                raw = parse(response.content)
                batch = batch_model.model_validate({key: raw} if isinstance(raw, list) else raw)
                entries = getattr(batch, key)
                if len(entries) > count:
                    raise ValueError('Too many items in batch')
                current = set()
                for entry in entries:
                    item = entry.model_dump(exclude_none=True)
                    identity = item[unique_key].strip().casefold()
                    if identity in seen or identity in current:
                        raise ValueError('Repeated item')
                    if validate:
                        validate(item)
                    current.add(identity)
                items.extend(entry.model_dump(exclude_none=True) for entry in entries)
                seen.update(current)
                break
            except (ValueError, TypeError) as exc:
                feedback = validation_feedback(exc)
                if attempt:
                    if items:
                        logger.warning('Generation stopped after an invalid batch', extra={'completed': len(items), 'requested': n, 'kind': key})
                        return items
                    raise
        if not entries:
            break  # No more supported, distinct items; never invent one just to fill a count.
    return items
