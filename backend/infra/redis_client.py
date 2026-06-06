"""
Redis client (async).
 
One shared async client built from REDIS_URL. decode_responses is False on
purpose: the capability vector is stored as raw float32 bytes on the agent hash,
and a decoding client would try to utf-8 decode those bytes and corrupt them. So
this client returns bytes for everything and the registry decodes the text
fields itself via util.to_str.
 
get_redis() is synchronous: redis.asyncio.from_url builds the client object
without opening a connection, so there is nothing to await here. The connection
opens lazily on the first awaited command. Callers await every command on the
returned client (await r.hgetall(...), async for k in r.scan_iter(...), etc.).
"""

import redis.asyncio as redis

from backend.config import REDIS_URL

_client: redis.Redis | None = None

def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(REDIS_URL, decode_responses=False)
    return _client

async def close_redis():
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None