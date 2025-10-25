"""
Redis Health Monitor
Run this to check if Redis is the bottleneck
"""
import redis
import time
import statistics

def test_redis_performance():
    print("🔍 Redis Performance Check\n" + "="*60)
    
    try:
        r = redis.Redis(
            host='localhost',
            port=6379,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        
        # Test connection
        print("✅ Redis connected")
        
        # Get Redis info
        info = r.info()
        print(f"\n📊 Redis Stats:")
        print(f"  Version: {info.get('redis_version')}")
        print(f"  Connected clients: {info.get('connected_clients')}")
        print(f"  Used memory: {info.get('used_memory_human')}")
        print(f"  Total connections received: {info.get('total_connections_received')}")
        print(f"  Total commands processed: {info.get('total_commands_processed')}")
        print(f"  Ops per second: {info.get('instantaneous_ops_per_sec')}")
        print(f"  Rejected connections: {info.get('rejected_connections', 0)}")
        
        # Check for slow log
        slowlog = r.slowlog_get(10)
        if slowlog:
            print(f"\n⚠️  Slow operations detected: {len(slowlog)} recent slow queries")
            for entry in slowlog[:3]:
                print(f"    - Duration: {entry['duration']}μs, Command: {entry['command']}")
        
        # Performance test - single operations
        print(f"\n⚡ Performance Test (1000 operations):")
        
        # SET test
        set_times = []
        for i in range(1000):
            start = time.time()
            r.set(f"test_key_{i}", f"test_value_{i}")
            set_times.append((time.time() - start) * 1000)
        
        print(f"  SET operations:")
        print(f"    Average: {statistics.mean(set_times):.2f}ms")
        print(f"    Median: {statistics.median(set_times):.2f}ms")
        print(f"    95th percentile: {statistics.quantiles(set_times, n=20)[18]:.2f}ms")
        print(f"    Max: {max(set_times):.2f}ms")
        
        # GET test
        get_times = []
        for i in range(1000):
            start = time.time()
            r.get(f"test_key_{i}")
            get_times.append((time.time() - start) * 1000)
        
        print(f"  GET operations:")
        print(f"    Average: {statistics.mean(get_times):.2f}ms")
        print(f"    Median: {statistics.median(get_times):.2f}ms")
        print(f"    95th percentile: {statistics.quantiles(get_times, n=20)[18]:.2f}ms")
        print(f"    Max: {max(get_times):.2f}ms")
        
        # Pipeline test
        pipe_times = []
        for batch in range(100):
            start = time.time()
            pipe = r.pipeline()
            for i in range(10):
                pipe.get(f"test_key_{batch * 10 + i}")
            pipe.execute()
            pipe_times.append((time.time() - start) * 1000)
        
        print(f"  PIPELINE (10 ops):")
        print(f"    Average: {statistics.mean(pipe_times):.2f}ms")
        print(f"    95th percentile: {statistics.quantiles(pipe_times, n=20)[18]:.2f}ms")
        
        # Cleanup
        for i in range(1000):
            r.delete(f"test_key_{i}")
        
        # Recommendations
        print(f"\n💡 Recommendations:")
        avg_get = statistics.mean(get_times)
        if avg_get > 5:
            print(f"  ⚠️  GET operations are slow ({avg_get:.2f}ms avg)")
            print(f"     - Check if Redis is running on same machine")
            print(f"     - Consider increasing Redis memory")
            print(f"     - Check network latency")
        else:
            print(f"  ✅ GET performance is good ({avg_get:.2f}ms avg)")
        
        if info.get('rejected_connections', 0) > 0:
            print(f"  ⚠️  Rejected connections detected!")
            print(f"     - Increase maxclients in redis.conf")
        
        if info.get('instantaneous_ops_per_sec', 0) > 50000:
            print(f"  ⚠️  High operations per second")
            print(f"     - Consider Redis Cluster for scaling")
        
        # Check memory
        used_memory_pct = info.get('used_memory') / info.get('maxmemory', float('inf'))
        if used_memory_pct > 0.8:
            print(f"  ⚠️  Memory usage high ({used_memory_pct*100:.1f}%)")
            print(f"     - Increase maxmemory or enable eviction")
        
    except redis.ConnectionError as e:
        print(f"❌ Cannot connect to Redis: {e}")
        print(f"\n💡 Solutions:")
        print(f"  1. Make sure Redis is running: redis-server")
        print(f"  2. Check if Redis is on correct host/port")
        print(f"  3. Check firewall settings")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_redis_performance()