"""Small, validated structured-output batches for constrained local models."""
from collections.abc import Callable

from langchain_core.messages import HumanMessage
from pydantic import BaseModel


def validated_batches(llm, render: Callable, parse: Callable, batch_model: type[BaseModel],
                      n: int, key: str, unique_key: str, validate: Callable | None = None) -> list[dict]:
    items = []
    seen = set()
    while len(items) < n:
        count = min(2, n - len(items))
        for attempt in range(2):
            try:
                response = llm.invoke([HumanMessage(content=render(count, items, bool(attempt)))])
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
            except (ValueError, TypeError):
                if attempt:
                    raise
        if len(entries) < count:
            break  # The evidence may support fewer useful items than requested.
    return items
