import asyncio

def read_text_file(**kwargs):
    file_path = kwargs.get("file_path")
    encoding = kwargs.get("encoding", "utf-8")
    errors = kwargs.get("errors", "replace")

    if file_path is None:
        raise ValueError("file_path is required")

    with open(
        file_path,
        mode="r",
        encoding=encoding,
        errors=errors,
    ) as file_handle:
        return file_handle.read()


async def read_text_async(**kwargs):
    file_path = kwargs.get("file_path")
    encoding = kwargs.get("encoding", "utf-8")
    errors = kwargs.get("errors", "replace")

    if file_path is None:
        raise ValueError("file_path is required")

    return await asyncio.to_thread(
        read_text_file,
        file_path=file_path,
        encoding=encoding,
        errors=errors,
    )