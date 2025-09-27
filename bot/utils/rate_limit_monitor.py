import time
from typing import Dict, Optional
import asyncio

class RateLimitMonitor:
    def __init__(self):
        self.request_times: Dict[str, list] = {}
        
    def can_make_request(self, endpoint: str, limit: int = 50, window: int = 1) -> bool:
        """Check if we can make a request to endpoint"""
        now = time.time()
        
        if endpoint not in self.request_times:
            self.request_times[endpoint] = []
            
        # Remove old requests outside window
        self.request_times[endpoint] = [
            req_time for req_time in self.request_times[endpoint]
            if now - req_time < window
        ]
        
        # Check if under limit
        return len(self.request_times[endpoint]) < limit
        
    def record_request(self, endpoint: str):
        """Record a request to endpoint"""
        now = time.time()
        if endpoint not in self.request_times:
            self.request_times[endpoint] = []
        self.request_times[endpoint].append(now)

rate_monitor = RateLimitMonitor()