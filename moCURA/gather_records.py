import asyncio
import logging

async def gather_records(**kwargs):
    """Run parsing coroutines and retain successfully parsed records."""
    tasks = kwargs.get("tasks", [])
    source_name = kwargs.get("source_name", "files")

    results = await asyncio.gather(*tasks, return_exceptions=True)
    records = []

    for result in results:
        if isinstance(result, Exception):
            logging.error(f"Error parsing {source_name}: {result}")
            continue
        records.append(result)

    return records