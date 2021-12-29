from __future__ import annotations
import edgedb
import discord
from typing import Union, Optional, Final, cast

instance_name: Final[str] = "SAIL"
AsyncQuerySource = Union[edgedb.AsyncIOConnection, edgedb.AsyncIOTransaction, edgedb.AsyncIOPool]

async def _run_query(query: str, source: AsyncQuerySource, *args, **kwargs) -> edgedb.Set:
    if not isinstance(source, edgedb.AsyncIOTransaction):
        async for tx in source.retrying_transaction():
            async with tx:
                return await _run_query(query, tx, args, kwargs)
    else:
        return await source.query(query, *args, **kwargs)
