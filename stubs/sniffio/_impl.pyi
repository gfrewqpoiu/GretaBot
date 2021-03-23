from contextvars import ContextVar
from typing import Optional

current_async_library_cvar: ContextVar[Optional[str]]

class AsyncLibraryNotFoundError(RuntimeError): ...

def current_async_library() -> str: ...
