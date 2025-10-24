from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import aiomysql
from typing import List, Dict, Optional
import asyncio
from contextlib import asynccontextmanager
import redis.asyncio as redis
from datetime import timedelta
import json
import os

from .cache_manager import category_viewed
from .recommender1 import weightage_assigner
from .database1 import get_search_data, get_recent_purchased

db_pool = None
redis_client = None
semaphore = None

# Configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "Mayur@12"),
    "db": os.getenv("DB_NAME", "searches"),
    "minsize": 10,
    "maxsize": 50,  # Increased pool size
    "pool_recycle": 3600,
    "autocommit": True
}

REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST", "localhost"),
    "port": int(os.getenv("REDIS_PORT", 6379)),
    "decode_responses": True,
    "max_connections": 100
}

# Cache TTL in seconds
CACHE_TTL = 3600  # 1 hour

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool, redis_client, semaphore
    
    # Startup
    print("🚀 Starting up...")
    
    # Create database pool
    db_pool = await aiomysql.create_pool(**DB_CONFIG)
    print(f"✅ Database pool created (size: {DB_CONFIG['minsize']}-{DB_CONFIG['maxsize']})")
    
    # Create Redis client
    try:
        redis_client = await redis.from_url(
            f"redis://{REDIS_CONFIG['host']}:{REDIS_CONFIG['port']}",
            max_connections=REDIS_CONFIG['max_connections'],
            decode_responses=REDIS_CONFIG['decode_responses']
        )
        await redis_client.ping()
        print("✅ Redis connected")
    except Exception as e:
        print(f"⚠️ Redis not available: {e}. Running without cache.")
        redis_client = None
    
    # Semaphore to limit concurrent DB operations
    semaphore = asyncio.Semaphore(100)  # Max 100 concurrent DB queries
    
    yield
    
    # Shutdown
    print("🛑 Shutting down...")
    if db_pool:
        db_pool.close()
        await db_pool.wait_closed()
        print("✅ Database pool closed")
    
    if redis_client:
        await redis_client.close()
        print("✅ Redis connection closed")

app = FastAPI(
    title="Scalable Recommendation API",
    version="2.0",
    lifespan=lifespan
)

# -------------------------
# Redis Cache Helpers
# -------------------------
async def get_from_cache(key: str) -> Optional[dict]:
    """Get data from Redis cache"""
    if not redis_client:
        return None
    
    try:
        data = await redis_client.get(key)
        if data:
            return json.loads(data)
    except Exception as e:
        print(f"⚠️ Cache read error: {e}")
    return None

async def set_to_cache(key: str, data: dict, ttl: int = CACHE_TTL):
    """Set data to Redis cache"""
    if not redis_client:
        return
    
    try:
        await redis_client.setex(
            key,
            ttl,
            json.dumps(data, default=str)
        )
    except Exception as e:
        print(f"⚠️ Cache write error: {e}")

async def invalidate_cache(user_id: int):
    """Invalidate all cache keys for a user"""
    if not redis_client:
        return
    
    try:
        keys = [
            f"search:{user_id}",
            f"purchase:{user_id}",
            f"recommendation:{user_id}"
        ]
        await redis_client.delete(*keys)
    except Exception as e:
        print(f"⚠️ Cache invalidation error: {e}")

# -------------------------
# Database Operations with Semaphore
# -------------------------
async def fetch_search_data(user_id: int) -> List[Dict]:
    """Fetch search data with caching and rate limiting"""
    cache_key = f"search:{user_id}"
    
    # Try cache first
    cached = await get_from_cache(cache_key)
    if cached is not None:
        return cached
    
    # Fetch from DB with semaphore
    async with semaphore:
        data = await get_search_data(user_id, db_pool)
    
    # Cache the result
    await set_to_cache(cache_key, data)
    return data

async def fetch_purchase_data(user_id: int) -> List[Dict]:
    """Fetch purchase data with caching and rate limiting"""
    cache_key = f"purchase:{user_id}"
    
    # Try cache first
    cached = await get_from_cache(cache_key)
    if cached is not None:
        return cached
    
    # Fetch from DB with semaphore
    async with semaphore:
        data = await get_recent_purchased(user_id, db_pool)
    
    # Cache the result
    await set_to_cache(cache_key, data)
    return data

# -------------------------
# Background Task for Cache Warming
# -------------------------
async def warm_cache_background(user_id: int):
    """Background task to warm cache without blocking response"""
    try:
        await fetch_search_data(user_id)
        await fetch_purchase_data(user_id)
    except Exception as e:
        print(f"⚠️ Background cache warming failed for user {user_id}: {e}")

# -------------------------
# API Endpoints
# -------------------------
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    db_status = "connected" if db_pool else "disconnected"
    redis_status = "connected" if redis_client else "not_available"
    
    return {
        "status": "healthy",
        "database": db_status,
        "redis": redis_status,
        "pool_size": f"{DB_CONFIG['minsize']}-{DB_CONFIG['maxsize']}"
    }

@app.get("/recommend/{user_id}")
async def get_recommendation(user_id: int, background_tasks: BackgroundTasks):
    """
    Get personalized recommendations for a user.
    Uses multi-level caching and async operations.
    """
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Check recommendation cache
    cache_key = f"recommendation:{user_id}"
    cached_result = await get_from_cache(cache_key)
    if cached_result:
        return JSONResponse(
            content=cached_result,
            headers={"X-Cache": "HIT"}
        )
    
    try:
        # Fetch data concurrently
        search_data, purchase_data = await asyncio.gather(
            fetch_search_data(user_id),
            fetch_purchase_data(user_id),
            return_exceptions=True
        )
        
        # Handle exceptions
        if isinstance(search_data, Exception):
            print(f"❌ Search data error: {search_data}")
            search_data = []
        if isinstance(purchase_data, Exception):
            print(f"❌ Purchase data error: {purchase_data}")
            purchase_data = []
        
        # If no data found
        if not search_data and not purchase_data:
            result = {
                "user_id": user_id,
                "message": "No data found for this user",
                "recommendations": []
            }
            await set_to_cache(cache_key, result, ttl=300)  # Cache for 5 min
            return JSONResponse(
                content=result,
                headers={"X-Cache": "MISS"}
            )
        
        # Prepare data for weightage calculation
        combined_data = {
            "search": search_data,
            "purchase": purchase_data
        }
        
        # Calculate weightage
        weightage_result = weightage_assigner(combined_data, user_id)
        
        # Build response
        result = {
            "user_id": user_id,
            "recommendations": {
                "weightage": weightage_result.get("overall_weight", 0),
                "search_weight": weightage_result.get("weightage_search", 0),
                "purchase_weight": weightage_result.get("weightage_purchase", 0),
                "recommended_categories": list(set(
                    weightage_result.get("search_category_duplicates", []) +
                    weightage_result.get("purchase_category_duplicates", [])
                ))[:10],  # Top 10
                "explore_categories": list(set(
                    weightage_result.get("search_category_unique", []) +
                    weightage_result.get("purchase_category_unique", [])
                ))[:5]  # Top 5
            },
            "metadata": {
                "search_count": len(search_data),
                "purchase_count": len(purchase_data)
            }
        }
        
        # Cache the result
        await set_to_cache(cache_key, result)
        
        return JSONResponse(
            content=result,
            headers={"X-Cache": "MISS"}
        )
        
    except Exception as e:
        print(f"❌ Error processing user {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing recommendation: {str(e)}"
        )

@app.post("/invalidate-cache/{user_id}")
async def invalidate_user_cache(user_id: int):
    """Manually invalidate cache for a user"""
    await invalidate_cache(user_id)
    return {"message": f"Cache invalidated for user {user_id}"}

@app.get("/batch-recommend")
async def batch_recommendations(user_ids: str):
    """
    Get recommendations for multiple users.
    Example: /batch-recommend?user_ids=1,2,3,4,5
    """
    try:
        ids = [int(uid.strip()) for uid in user_ids.split(",")]
        if len(ids) > 50:
            raise HTTPException(
                status_code=400,
                detail="Maximum 50 users per batch request"
            )
        
        
        tasks = [get_recommendation(uid, BackgroundTasks()) for uid in ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        
        successful = []
        failed = []
        for uid, result in zip(ids, results):
            if isinstance(result, Exception):
                failed.append({"user_id": uid, "error": str(result)})
            else:
                successful.append(result.body.decode() if hasattr(result, 'body') else result)
        
        return {
            "successful": len(successful),
            "failed": len(failed),
            "results": successful,
            "errors": failed
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_ids format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

