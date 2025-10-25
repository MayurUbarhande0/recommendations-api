from locust import HttpUser, task, between, events
import random
import json
import time
from typing import List

class RecommendationUser(HttpUser):
    wait_time = between(0.5, 2)
    
    # Use actual user IDs from your database (1 to 4703)
    user_ids = list(range(1, 4704))  # Your actual users
    
    # Track response times for analysis
    response_times = []

    def on_start(self):
        """Called when a simulated user starts"""
        # Health check on startup
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code != 200:
                response.failure("Health check failed")

    @task(10)  # Highest weight - most common operation
    def get_recommendation(self):
        """Test single user recommendation endpoint"""
        user_id = random.choice(self.user_ids)
        start_time = time.time()
        
        with self.client.get(
            f"/recommend/{user_id}", 
            catch_response=True,
            name="/recommend/[user_id]"  # Grouped naming for better stats
        ) as response:
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    # Validate response structure
                    if "recommendations" not in data:
                        response.failure("Missing recommendations key")
                    elif "user_id" not in data:
                        response.failure("Missing user_id in response")
                    else:
                        # Track successful response time
                        self.response_times.append(elapsed)
                        
                        # Log slow responses
                        if elapsed > 2.0:
                            print(f"⚠️ Slow response for user {user_id}: {elapsed:.2f}s")
                        
                        response.success()
                        
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code == 500:
                response.failure(f"Server error: {response.text[:100]}")
            else:
                response.failure(f"Status code {response.status_code}")

    @task(3)  # Medium frequency - batch of 5
    def batch_recommend_small(self):
        """Test small batch recommendation (5 users)"""
        sample_ids = random.sample(self.user_ids, 5)
        user_ids_param = ",".join(map(str, sample_ids))
        
        with self.client.get(
            f"/batch-recommend?user_ids={user_ids_param}", 
            catch_response=True,
            name="/batch-recommend?users=5"
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    if "results" not in data:
                        response.failure("Missing results key")
                    elif data.get("successful", 0) != 5:
                        response.failure(f"Expected 5 results, got {data.get('successful', 0)}")
                    else:
                        response.success()
                        
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"Status code {response.status_code}")

    @task(2)  # Less frequent - batch of 20
    def batch_recommend_medium(self):
        """Test medium batch recommendation (20 users)"""
        sample_ids = random.sample(self.user_ids, 20)
        user_ids_param = ",".join(map(str, sample_ids))
        
        with self.client.get(
            f"/batch-recommend?user_ids={user_ids_param}", 
            catch_response=True,
            name="/batch-recommend?users=20"
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "results" not in data:
                        response.failure("Missing results key")
                    else:
                        # Check cache hit ratio
                        cache_hits = data.get("cache_hits", 0)
                        cache_misses = data.get("cache_misses", 0)
                        total = cache_hits + cache_misses
                        
                        if total > 0:
                            hit_ratio = cache_hits / total * 100
                            if hit_ratio < 20:  # Expected some cache hits
                                print(f"⚠️ Low cache hit ratio: {hit_ratio:.1f}%")
                        
                        response.success()
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"Status code {response.status_code}")

    @task(1)  # Rare - large batch of 50
    def batch_recommend_large(self):
        """Test large batch recommendation (50 users)"""
        sample_ids = random.sample(self.user_ids, 50)
        user_ids_param = ",".join(map(str, sample_ids))
        
        with self.client.get(
            f"/batch-recommend?user_ids={user_ids_param}", 
            catch_response=True,
            name="/batch-recommend?users=50"
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "results" not in data:
                        response.failure("Missing results key")
                    else:
                        response.success()
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"Status code {response.status_code}")

    @task(1)  # Test cache invalidation
    def invalidate_cache(self):
        """Test cache invalidation endpoint"""
        user_id = random.choice(self.user_ids)
        
        with self.client.post(
            f"/invalidate-cache/{user_id}",
            catch_response=True,
            name="/invalidate-cache/[user_id]"
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "message" in data:
                        response.success()
                    else:
                        response.failure("Missing message in response")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"Status code {response.status_code}")


# Event listeners for custom reporting
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("=" * 60)
    print("🚀 Load Test Starting")
    print("=" * 60)
    print(f"Target: {environment.host}")
    print(f"Users: Will ramp up to target")
    print("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("=" * 60)
    print("✅ Load Test Completed")
    print("=" * 60)
    
    # Print statistics summary
    stats = environment.stats
    print(f"Total Requests: {stats.total.num_requests}")
    print(f"Total Failures: {stats.total.num_failures}")
    print(f"Failure Rate: {stats.total.fail_ratio * 100:.2f}%")
    print(f"Average Response Time: {stats.total.avg_response_time:.2f}ms")
    print(f"Max Response Time: {stats.total.max_response_time:.2f}ms")
    print(f"RPS: {stats.total.total_rps:.2f}")
    print("=" * 60)


# Stress test user - more aggressive
class StressTestUser(RecommendationUser):
    """More aggressive testing pattern for stress testing"""
    wait_time = between(0.1, 0.5)  # Much faster requests
    
    @task(20)
    def rapid_fire_requests(self):
        """Rapid sequential requests to test connection pooling"""
        user_id = random.choice(self.user_ids)
        
        for _ in range(3):  # 3 rapid requests
            with self.client.get(
                f"/recommend/{user_id}",
                catch_response=True,
                name="/recommend/[rapid]"
            ) as response:
                if response.status_code != 200:
                    response.failure(f"Status {response.status_code}")


# Cache warming user - simulates initial load
class CacheWarmingUser(HttpUser):
    """Separate user type for cache warming"""
    wait_time = between(2, 5)
    user_ids = list(range(1, 1001))  # Smaller subset for warming
    
    @task
    def warm_popular_users(self):
        """Warm cache for popular users"""
        sample_ids = random.sample(self.user_ids, 100)
        user_ids_param = ",".join(map(str, sample_ids))
        
        with self.client.post(
            f"/warm-cache?user_ids={user_ids_param}",
            catch_response=True,
            name="/warm-cache"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status {response.status_code}")