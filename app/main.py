from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import aiomysql
from typing import List, Dict, Optional
import asyncio
from contextlib import asynccontextmanager
import redis.asyncio as redis
import json
import os
from concurrent.futures import ThreadPoolExecutor
import functools
import time

from .cache_manager import category_viewed
from .recommender1 import weightage_assigner
from .database1 import get_search_data, get_recent_purchased


db_pool: Optional[aiomysql.Pool] = None
redis_client: Optional[redis.Redis] = None
semaphore: Optional[asyncio.Semaphore] = None
thread_pool: Optional[ThreadPoolExecutor] = None

memory_cache: Dict[str, tuple[dict, float]] = {}
MEMORY_CACHE_SIZE = 5000
MEMORY_CACHE_TTL = 300

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "Mayur@12"),
    "db": os.getenv("DB_NAME", "searches"),
    "minsize": 20,
    "maxsize": 80,
    "pool_recycle": 3600,
    "autocommit": True,
    "connect_timeout": 5,
    "charset": "utf8mb4"
}

REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST", "localhost"),
    "port": int(os.getenv("REDIS_PORT", 6379)),
    "decode_responses": True,
    "max_connections": 300,
    "socket_keepalive": True,
    "socket_connect_timeout": 5,
    "socket_timeout": 5,
    "retry_on_timeout": True,
    "health_check_interval": 30
}

CACHE_TTL = 3600
SHORT_CACHE_TTL = 300
MAX_CONCURRENT_DB_OPS = 500
THREAD_POOL_WORKERS = 100
REQUEST_TIMEOUT = 30
BATCH_CHUNK_SIZE = 15


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool, redis_client, semaphore, thread_pool

    print("🚀 Starting API...")

    try:
        db_pool = await aiomysql.create_pool(**DB_CONFIG)
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
        print(f"✅ Database connected: {DB_CONFIG['minsize']}-{DB_CONFIG['maxsize']} pool")
    except Exception as e:
        print(f"❌ Database failed: {e}")
        raise

    try:
        redis_client = await redis.from_url(
            f"redis://{REDIS_CONFIG['host']}:{REDIS_CONFIG['port']}",
            max_connections=REDIS_CONFIG["max_connections"],
            decode_responses=REDIS_CONFIG["decode_responses"],
            socket_keepalive=REDIS_CONFIG["socket_keepalive"],
            socket_connect_timeout=REDIS_CONFIG["socket_connect_timeout"],
            socket_timeout=REDIS_CONFIG["socket_timeout"],
            retry_on_timeout=REDIS_CONFIG["retry_on_timeout"],
            health_check_interval=REDIS_CONFIG["health_check_interval"]
        )
        await redis_client.ping()
        print(f"✅ Redis connected: {REDIS_CONFIG['max_connections']} connections")
    except Exception as e:
        print(f"⚠️  Redis not available: {e}")
        print(f"⚠️  Running with in-memory cache only (limited to {MEMORY_CACHE_SIZE} items)")
        redis_client = None

    semaphore = asyncio.BoundedSemaphore(MAX_CONCURRENT_DB_OPS)
    thread_pool = ThreadPoolExecutor(max_workers=THREAD_POOL_WORKERS)
    print(f"✅ Thread pool: {THREAD_POOL_WORKERS} workers")
    print(f"✅ Ready to handle requests!")

    yield

    print("🛑 Shutting down...")
    
    if thread_pool:
        thread_pool.shutdown(wait=True)
        print("✅ Thread pool closed")
    
    if db_pool:
        db_pool.close()
        await db_pool.wait_closed()
        print("✅ Database closed")

    if redis_client:
        try:
            await redis_client.aclose()
            print("✅ Redis closed")
        except:
            pass


app = FastAPI(
    title="Optimized Recommendation API",
    version="2.5",
    lifespan=lifespan
)


def get_from_memory(key: str) -> Optional[dict]:
    if key in memory_cache:
        data, timestamp = memory_cache[key]
        if time.time() - timestamp < MEMORY_CACHE_TTL:
            return data
        else:
            del memory_cache[key]
    return None


def set_to_memory(key: str, data: dict):
    if len(memory_cache) >= MEMORY_CACHE_SIZE:
        oldest_key = min(memory_cache.keys(), key=lambda k: memory_cache[k][1])
        del memory_cache[oldest_key]
    memory_cache[key] = (data, time.time())


async def get_from_cache(key: str) -> Optional[dict]:
    mem_data = get_from_memory(key)
    if mem_data is not None:
        return mem_data
    
    if redis_client:
        try:
            data = await asyncio.wait_for(redis_client.get(key), timeout=2.0)
            if data:
                result = json.loads(data)
                set_to_memory(key, result)
                return result
        except asyncio.TimeoutError:
            pass
        except Exception:
            pass
    
    return None


async def set_to_cache(key: str, data: dict, ttl: int = CACHE_TTL):
    set_to_memory(key, data)
    
    if redis_client:
        async def _write_redis():
            try:
                await asyncio.wait_for(
                    redis_client.setex(key, ttl, json.dumps(data, default=str)),
                    timeout=2.0
                )
            except:
                pass
        
        asyncio.create_task(_write_redis())


async def get_many_from_cache(keys: List[str]) -> Dict[str, Optional[dict]]:
    results = {}
    redis_keys = []
    
    for key in keys:
        mem_data = get_from_memory(key)
        if mem_data is not None:
            results[key] = mem_data
        else:
            redis_keys.append(key)
    
    if redis_client and redis_keys:
        try:
            pipe = redis_client.pipeline()
            for key in redis_keys:
                pipe.get(key)
            
            redis_results = await asyncio.wait_for(pipe.execute(), timeout=3.0)
            
            for key, data in zip(redis_keys, redis_results):
                if data:
                    result = json.loads(data)
                    results[key] = result
                    set_to_memory(key, result)
                else:
                    results[key] = None
        except:
            for key in redis_keys:
                results[key] = None
    else:
        for key in redis_keys:
            results[key] = None
    
    return results


async def invalidate_cache(user_id: int):
    keys = [
        f"search:{user_id}",
        f"purchase:{user_id}",
        f"recommendation:{user_id}"
    ]
    
    for key in keys:
        memory_cache.pop(key, None)
    
    if redis_client:
        try:
            await asyncio.wait_for(redis_client.delete(*keys), timeout=2.0)
        except:
            pass


async def fetch_search_data(user_id: int) -> List[Dict]:
    cache_key = f"search:{user_id}"
    
    cached = await get_from_cache(cache_key)
    if cached is not None:
        return cached

    try:
        async with semaphore:
            data = await asyncio.wait_for(
                get_search_data(user_id, db_pool),
                timeout=5.0
            )
        
        await set_to_cache(cache_key, data)
        return data
    
    except asyncio.TimeoutError:
        print(f"⚠️  Search data timeout for user {user_id}")
        return []
    except Exception as e:
        print(f"⚠️  Search data error for user {user_id}: {e}")
        return []


async def fetch_purchase_data(user_id: int) -> List[Dict]:
    cache_key = f"purchase:{user_id}"
    
    cached = await get_from_cache(cache_key)
    if cached is not None:
        return cached

    try:
        async with semaphore:
            data = await asyncio.wait_for(
                get_recent_purchased(user_id, db_pool),
                timeout=5.0
            )
        
        await set_to_cache(cache_key, data)
        return data
    
    except asyncio.TimeoutError:
        print(f"⚠️  Purchase data timeout for user {user_id}")
        return []
    except Exception as e:
        print(f"⚠️  Purchase data error for user {user_id}: {e}")
        return []


def run_in_thread(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(
                    thread_pool,
                    functools.partial(func, *args, **kwargs)
                ),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            print(f"⚠️  Thread timeout for {func.__name__}")
            raise
    return wrapper


@run_in_thread
def process_weightage(combined_data: dict, user_id: int) -> dict:
    return weightage_assigner(combined_data, user_id)


async def compute_recommendation(user_id: int) -> dict:
    cache_key = f"recommendation:{user_id}"
    
    cached = await get_from_cache(cache_key)
    if cached is not None:
        return cached

    try:
        search_data, purchase_data = await asyncio.gather(
            fetch_search_data(user_id),
            fetch_purchase_data(user_id),
            return_exceptions=True
        )

        if isinstance(search_data, Exception):
            search_data = []
        if isinstance(purchase_data, Exception):
            purchase_data = []

        if not search_data and not purchase_data:
            result = {
                "user_id": user_id,
                "message": "No data found for this user",
                "recommendations": []
            }
            await set_to_cache(cache_key, result, ttl=SHORT_CACHE_TTL)
            return result

        combined_data = {"search": search_data, "purchase": purchase_data}
        
        try:
            weightage_result = await process_weightage(combined_data, user_id)
        except asyncio.TimeoutError:
            return {
                "user_id": user_id,
                "error": "Processing timeout",
                "recommendations": []
            }

        result = {
            "user_id": user_id,
            "recommendations": {
                "weightage": weightage_result.get("overall_weight", 0),
                "search_weight": weightage_result.get("weightage_search", 0),
                "purchase_weight": weightage_result.get("weightage_purchase", 0),
                "recommended_categories": list(set(
                    weightage_result.get("search_category_duplicates", []) +
                    weightage_result.get("purchase_category_duplicates", [])
                ))[:10],
                "explore_categories": list(set(
                    weightage_result.get("search_category_unique", []) +
                    weightage_result.get("purchase_category_unique", [])
                ))[:5]
            },
            "metadata": {
                "search_count": len(search_data),
                "purchase_count": len(purchase_data)
            }
        }

        await set_to_cache(cache_key, result)
        return result
    
    except Exception as e:
        print(f"❌ Error computing recommendation for user {user_id}: {e}")
        return {
            "user_id": user_id,
            "error": "Internal error",
            "recommendations": []
        }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "database": "connected" if db_pool else "disconnected",
        "redis": "connected" if redis_client else "disconnected",
        "memory_cache_size": len(memory_cache),
        "memory_cache_limit": MEMORY_CACHE_SIZE
    }


@app.get("/recommend/{user_id}")
async def get_recommendation(user_id: int):
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        result = await asyncio.wait_for(
            compute_recommendation(user_id),
            timeout=REQUEST_TIMEOUT
        )
        return JSONResponse(content=result)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Request timeout")
    except Exception as e:
        print(f"❌ Error in endpoint for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/invalidate-cache/{user_id}")
async def invalidate_user_cache(user_id: int):
    await invalidate_cache(user_id)
    return {"message": f"Cache invalidated for user {user_id}"}


@app.get("/batch-recommend")
async def batch_recommendations(user_ids: str):
    try:
        ids = [int(uid.strip()) for uid in user_ids.split(",")]
        if len(ids) > 100:
            raise HTTPException(status_code=400, detail="Maximum 100 users per batch")

        cache_keys = [f"recommendation:{uid}" for uid in ids]
        cached_results = await get_many_from_cache(cache_keys)
        
        results = []
        uncached_ids = []
        
        for uid in ids:
            cache_key = f"recommendation:{uid}"
            cached = cached_results.get(cache_key)
            if cached:
                results.append(cached)
            else:
                uncached_ids.append(uid)
        
        if uncached_ids:
            for i in range(0, len(uncached_ids), BATCH_CHUNK_SIZE):
                chunk = uncached_ids[i:i + BATCH_CHUNK_SIZE]
                
                try:
                    chunk_results = await asyncio.wait_for(
                        asyncio.gather(
                            *[compute_recommendation(uid) for uid in chunk],
                            return_exceptions=True
                        ),
                        timeout=REQUEST_TIMEOUT
                    )
                    
                    for result in chunk_results:
                        if not isinstance(result, Exception) and "error" not in result:
                            results.append(result)
                
                except asyncio.TimeoutError:
                    print(f"⚠️  Batch chunk timeout for chunk starting at index {i}")
        
        return {
            "successful": len(results),
            "failed": len(ids) - len(results),
            "total_requested": len(ids),
            "results": results,
            "cache_hits": len(ids) - len(uncached_ids),
            "cache_misses": len(uncached_ids)
        }

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_ids format")
    except Exception as e:
        print(f"❌ Batch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/warm-cache")
async def warm_cache_batch(user_ids: str):
    try:
        ids = [int(uid.strip()) for uid in user_ids.split(",")]
        if len(ids) > 500:
            raise HTTPException(status_code=400, detail="Maximum 500 users for cache warming")
        
        async def warm_batch():
            for i in range(0, len(ids), 20):
                chunk = ids[i:i + 20]
                await asyncio.gather(
                    *[compute_recommendation(uid) for uid in chunk],
                    return_exceptions=True
                )
                await asyncio.sleep(0.05)
        
        asyncio.create_task(warm_batch())
        
        return {
            "message": f"Cache warming initiated for {len(ids)} users",
            "user_count": len(ids),
            "status": "processing"
        }
    
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_ids format")


@app.get("/stats")
async def get_stats():
    return {
        "memory_cache_size": len(memory_cache),
        "memory_cache_limit": MEMORY_CACHE_SIZE,
        "redis_available": redis_client is not None,
        "db_pool_size": f"{DB_CONFIG['minsize']}-{DB_CONFIG['maxsize']}",
        "thread_workers": THREAD_POOL_WORKERS,
        "max_concurrent_db": MAX_CONCURRENT_DB_OPS
    }
