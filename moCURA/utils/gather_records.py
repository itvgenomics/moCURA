import asyncio
import logging


async def gather_records(**kwargs):
    """Run parsing coroutines and retain successfully parsed records."""
    tasks = kwargs.get("tasks", [])
    source_name = kwargs.get("source_name", "files")
    keep_none = bool(kwargs.get("keep_none", False))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    records = []

    for result in results:
        if isinstance(result, Exception):
            logging.error("Error parsing %s: %s", source_name, result)
            continue
        if result is None and not keep_none:
            continue
        records.append(result)

    return records
