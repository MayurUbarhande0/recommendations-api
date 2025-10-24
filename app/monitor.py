"""
Real-time monitoring script for the Recommendation API
Usage: python monitor.py
"""

import asyncio
import aiohttp
import time
from datetime import datetime
from collections import deque
import statistics

class APIMonitor:
    def __init__(self, base_url="http://localhost:8000", interval=5):
        self.base_url = base_url
        self.interval = interval
        self.response_times = deque(maxlen=100)
        self.error_count = 0
        self.success_count = 0
        self.cache_hits = 0
        self.cache_misses = 0
        
    async def check_health(self, session):
        """Check API health endpoint"""
        try:
            start = time.time()
            async with session.get(f"{self.base_url}/health") as response:
                elapsed = (time.time() - start) * 1000
                data = await response.json()
                return {
                    "status": "UP" if response.status == 200 else "DOWN",
                    "response_time": elapsed,
                    "details": data
                }
        except Exception as e:
            return {"status": "DOWN", "error": str(e)}
    
    async def test_endpoint(self, session, user_id):
        """Test recommendation endpoint"""
        try:
            start = time.time()
            async with session.get(
                f"{self.base_url}/recommend/{user_id}",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                elapsed = (time.time() - start) * 1000
                self.response_times.append(elapsed)
                
                # Check cache header
                cache_status = response.headers.get('X-Cache', 'UNKNOWN')
                if cache_status == 'HIT':
                    self.cache_hits += 1
                elif cache_status == 'MISS':
                    self.cache_misses += 1
                
                if response.status == 200:
                    self.success_count += 1
                    return {"status": "success", "time": elapsed, "cache": cache_status}
                else:
                    self.error_count += 1
                    return {"status": "error", "code": response.status, "time": elapsed}
                    
        except asyncio.TimeoutError:
            self.error_count += 1
            return {"status": "timeout"}
        except Exception as e:
            self.error_count += 1
            return {"status": "error", "error": str(e)}
    
    async def run_batch_test(self, session, num_requests=10):
        """Test with multiple concurrent requests"""
        tasks = [
            self.test_endpoint(session, user_id)
            for user_id in range(1, num_requests + 1)
        ]
        return await asyncio.gather(*tasks)
    
    def get_stats(self):
        """Calculate statistics"""
        if not self.response_times:
            return None
        
        total_requests = self.success_count + self.error_count
        cache_total = self.cache_hits + self.cache_misses
        
        return {
            "total_requests": total_requests,
            "success_rate": (self.success_count / total_requests * 100) if total_requests > 0 else 0,
            "error_rate": (self.error_count / total_requests * 100) if total_requests > 0 else 0,
            "cache_hit_rate": (self.cache_hits / cache_total * 100) if cache_total > 0 else 0,
            "response_times": {
                "min": min(self.response_times),
                "max": max(self.response_times),
                "avg": statistics.mean(self.response_times),
                "median": statistics.median(self.response_times),
                "p95": statistics.quantiles(self.response_times, n=20)[18] if len(self.response_times) > 10 else 0,
                "p99": statistics.quantiles(self.response_times, n=100)[98] if len(self.response_times) > 100 else 0,
            }
        }
    
    def print_stats(self, stats, health):
        """Pretty print statistics"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print("\n" + "="*80)
        print(f"📊 API Monitor Report - {timestamp}")
        print("="*80)
        
        # Health Status
        print(f"\n🏥 Health Status: {health['status']}")
        if 'details' in health:
            details = health['details']
            print(f"   Database: {details.get('database', 'unknown')}")
            print(f"   Redis: {details.get('redis', 'unknown')}")
            print(f"   Pool Size: {details.get('pool_size', 'unknown')}")
        
        if stats:
            # Request Stats
            print(f"\n📈 Request Statistics:")
            print(f"   Total Requests: {stats['total_requests']}")
            print(f"   Success Rate: {stats['success_rate']:.2f}%")
            print(f"   Error Rate: {stats['error_rate']:.2f}%")
            
            # Cache Stats
            print(f"\n💾 Cache Performance:")
            print(f"   Hit Rate: {stats['cache_hit_rate']:.2f}%")
            print(f"   Hits: {self.cache_hits}")
            print(f"   Misses: {self.cache_misses}")
            
            # Response Times
            rt = stats['response_times']
            print(f"\n⚡ Response Times (ms):")
            print(f"   Min: {rt['min']:.2f}")
            print(f"   Avg: {rt['avg']:.2f}")
            print(f"   Median: {rt['median']:.2f}")
            print(f"   P95: {rt['p95']:.2f}")
            print(f"   P99: {rt.get('p99', 0):.2f}")
            print(f"   Max: {rt['max']:.2f}")
            
            # Performance Status
            print(f"\n🎯 Performance Status:")
            avg_time = rt['avg']
            if avg_time < 50:
                print(f"   ✅ Excellent (avg: {avg_time:.2f}ms)")
            elif avg_time < 100:
                print(f"   ✅ Good (avg: {avg_time:.2f}ms)")
            elif avg_time < 500:
                print(f"   ⚠️  Acceptable (avg: {avg_time:.2f}ms)")
            else:
                print(f"   ❌ Poor (avg: {avg_time:.2f}ms)")
        
        print("\n" + "="*80)
    
    async def monitor_loop(self):
        """Main monitoring loop"""
        print("🚀 Starting API Monitor...")
        print(f"📍 Monitoring: {self.base_url}")
        print(f"⏱️  Interval: {self.interval}s")
        print("\nPress Ctrl+C to stop\n")
        
        async with aiohttp.ClientSession() as session:
            try:
                while True:
                    # Check health
                    health = await self.check_health(session)
                    
                    # Run batch test
                    await self.run_batch_test(session, num_requests=20)
                    
                    # Get and print stats
                    stats = self.get_stats()
                    self.print_stats(stats, health)
                    
                    # Wait for next interval
                    await asyncio.sleep(self.interval)
                    
            except KeyboardInterrupt:
                print("\n\n👋 Monitoring stopped by user")
                if stats:
                    print("\n📊 Final Statistics:")
                    self.print_stats(stats, health)

async def main():
    """Main entry point"""
    monitor = APIMonitor(
        base_url="http://localhost:8000",
        interval=10  # Check every 10 seconds
    )
    await monitor.monitor_loop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")