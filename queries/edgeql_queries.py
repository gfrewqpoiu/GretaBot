from __future__ import annotations
import edgedb
import discord
from typing import Union, Optional, Final, cast

# instance_name: Final[str] = "SAIL"
client = edgedb.create_async_client()


async def run_query(query: str, database_client=client, *args, **kwargs) -> edgedb.Set:
    """Run an EdgeDB Query in a new transaction and return the result set"""
    async for tx in database_client.transaction():
        async with tx:  # TODO: Check whether this is correct.
            return await tx.query(query, *args, **kwargs)
