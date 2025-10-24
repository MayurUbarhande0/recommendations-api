from locust import HttpUser, task, between
import random

class RecommendationUser(HttpUser):
    wait_time = between(1, 3)  # Wait 1-3 seconds between requests

    @task
    def get_recommendation(self):
        user_id = random.randint(1, 1000)  # simulate random users
        self.client.get(f"/recommend/{user_id}")
