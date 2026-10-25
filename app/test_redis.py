"""Redis connection test. Run it from the project folder AS A MODULE, so the `app` package can be imported:

    python -m app.test_redis                                   (dev box: .venv/Scripts/python.exe -m app.test_redis)
    cd /srv/tolk && sudo -u tolk .venv/bin/python -m app.test_redis      (server)

Exit code 0 = Redis answered and a write / read / delete round trip through app.cache worked.
"""
import sys
import time
import uuid

import redis

from app import cache
from app.config import settings

__test__ = False  # a command, not a pytest module (pytest only collects tests/, see pytest.ini)


def main() -> int:
    c = cache.client()
    if c is None:
        print("FAIL: REDIS_URL is empty in .env, so the cache is off")
        return 1
    kw = c.connection_pool.connection_kwargs
    where = f"{kw.get('host')}:{kw.get('port')} db {kw.get('db')}"  # never print the URL: it may hold a password
    try:
        started = time.perf_counter()
        c.ping()
        key = f"selftest:{uuid.uuid4().hex}"
        value = {"ok": True, "text": "Salom / Привет"}
        cache.set_json(key, value, ttl=30)
        if cache.get_json(key) != value:
            print(f"FAIL: Redis at {where} answered PING but the value written through app.cache did not come back")
            return 1
        cache.delete(key)
        if c.exists(cache.PREFIX + key):
            print(f"FAIL: Redis at {where} did not delete the test key")
            return 1
        ms = (time.perf_counter() - started) * 1000
        info = c.info()
        conf = c.config_get("maxmemory*")
    except redis.RedisError as e:
        print(f"FAIL: cannot use Redis at {where}: {e}")
        return 1
    maxmemory = int(conf.get("maxmemory", 0))
    print(f"OK: Redis {info.get('redis_version')} at {where}, round trip {ms:.1f} ms")
    print(f"    memory used {info.get('used_memory_human')}, limit {f'{maxmemory // 2**20} MB' if maxmemory else 'none'}, "
          f"policy {conf.get('maxmemory-policy')}, CACHE_TTL {settings.cache_ttl} s, keys in this db {c.dbsize()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
