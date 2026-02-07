#!/usr/bin/env python3
"""
API Rate Limiter for Petty Cash Sorter
Implements token bucket algorithm with burst handling and cooldown periods
"""

import time
import logging
import threading
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_minute: int = 60
    burst_limit: int = 10
    cooldown_period_seconds: int = 60
    enabled: bool = True

@dataclass
class RateLimitStats:
    """Statistics for rate limiting."""
    total_requests: int = 0
    successful_requests: int = 0
    rate_limited_requests: int = 0
    average_response_time: float = 0.0
    last_request_time: Optional[datetime] = None
    cooldown_start_time: Optional[datetime] = None

class TokenBucketRateLimiter:
    """Token bucket rate limiter with burst handling."""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.stats = RateLimitStats()
        
        # Token bucket parameters
        self.tokens = config.burst_limit
        self.max_tokens = config.burst_limit
        self.tokens_per_second = config.requests_per_minute / 60.0
        
        # Timing
        self.last_refill_time = time.time()
        self.cooldown_active = False
        self.cooldown_start_time = None
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/api_rate_limiter.log'),
                logging.StreamHandler()
            ]
        )
        
        logging.info("INITIALIZING API RATE LIMITER")
        logging.info("=" * 50)
        logging.info(f"Requests per minute: {config.requests_per_minute}")
        logging.info(f"Burst limit: {config.burst_limit}")
        logging.info(f"Cooldown period: {config.cooldown_period_seconds}s")
    
    def _refill_tokens(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        time_passed = now - self.last_refill_time
        tokens_to_add = time_passed * self.tokens_per_second
        
        self.tokens = min(self.max_tokens, self.tokens + tokens_to_add)
        self.last_refill_time = now
    
    def _check_cooldown(self) -> bool:
        """Check if system is in cooldown period."""
        if not self.cooldown_active or not self.cooldown_start_time:
            return False
        
        cooldown_end = self.cooldown_start_time + timedelta(seconds=self.config.cooldown_period_seconds)
        if datetime.now() >= cooldown_end:
            self.cooldown_active = False
            self.cooldown_start_time = None
            logging.info("Cooldown period ended")
            return False
        
        return True
    
    def acquire_token(self, timeout: float = 30.0) -> bool:
        """Acquire a token for API request."""
        if not self.config.enabled:
            return True
        
        start_time = time.time()
        
        with self.lock:
            # Check cooldown first
            if self._check_cooldown():
                remaining_cooldown = self.config.cooldown_period_seconds - (
                    datetime.now() - self.cooldown_start_time
                ).total_seconds()
                logging.warning(f"System in cooldown. Remaining: {remaining_cooldown:.1f}s")
                return False
            
            # Refill tokens
            self._refill_tokens()
            
            # Check if tokens available
            if self.tokens >= 1:
                self.tokens -= 1
                self.stats.total_requests += 1
                self.stats.last_request_time = datetime.now()
                return True
            
            # No tokens available, wait if timeout allows
            if timeout > 0:
                wait_time = (1 - self.tokens) / self.tokens_per_second
                if wait_time <= timeout:
                    logging.info(f"Waiting {wait_time:.1f}s for token refill")
                    time.sleep(wait_time)
                    self._refill_tokens()
                    if self.tokens >= 1:
                        self.tokens -= 1
                        self.stats.total_requests += 1
                        self.stats.last_request_time = datetime.now()
                        return True
            
            # Could not acquire token
            self.stats.rate_limited_requests += 1
            logging.warning("Rate limit exceeded - request blocked")
            return False
    
    def record_success(self, response_time: float):
        """Record successful API request."""
        self.stats.successful_requests += 1
        
        # Update average response time
        if self.stats.successful_requests == 1:
            self.stats.average_response_time = response_time
        else:
            self.stats.average_response_time = (
                (self.stats.average_response_time * (self.stats.successful_requests - 1) + response_time) /
                self.stats.successful_requests
            )
    
    def record_failure(self, error_type: str = "unknown"):
        """Record failed API request and potentially trigger cooldown."""
        logging.warning(f"API request failed: {error_type}")
        
        # Check if we should enter cooldown
        if self.stats.rate_limited_requests > 0:
            failure_rate = self.stats.rate_limited_requests / max(1, self.stats.total_requests)
            if failure_rate > 0.5:  # More than 50% failures
                self._enter_cooldown()
    
    def _enter_cooldown(self):
        """Enter cooldown period."""
        self.cooldown_active = True
        self.cooldown_start_time = datetime.now()
        logging.warning(f"Entering cooldown period for {self.config.cooldown_period_seconds}s")
    
    def get_stats(self) -> Dict:
        """Get current rate limiting statistics."""
        with self.lock:
            return {
                'total_requests': self.stats.total_requests,
                'successful_requests': self.stats.successful_requests,
                'rate_limited_requests': self.stats.rate_limited_requests,
                'success_rate': (
                    self.stats.successful_requests / max(1, self.stats.total_requests) * 100
                ),
                'average_response_time': self.stats.average_response_time,
                'current_tokens': self.tokens,
                'max_tokens': self.max_tokens,
                'cooldown_active': self.cooldown_active,
                'last_request_time': (
                    self.stats.last_request_time.isoformat() 
                    if self.stats.last_request_time else None
                )
            }

class RateLimitedFunction:
    """Decorator for rate-limited function calls."""
    
    def __init__(self, rate_limiter: TokenBucketRateLimiter, timeout: float = 30.0):
        self.rate_limiter = rate_limiter
        self.timeout = timeout
    
    def __call__(self, func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            
            # Try to acquire token
            if not self.rate_limiter.acquire_token(self.timeout):
                raise Exception("Rate limit exceeded - unable to acquire token")
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Record success
                response_time = time.time() - start_time
                self.rate_limiter.record_success(response_time)
                
                return result
                
            except Exception as e:
                # Record failure
                self.rate_limiter.record_failure(str(type(e).__name__))
                raise
        
        return wrapper

class APIRateLimiter:
    """Main API rate limiter class with multiple endpoint support."""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.rate_limiters: Dict[str, TokenBucketRateLimiter] = {}
        self.global_limiter = TokenBucketRateLimiter(config)
        
        logging.info("INITIALIZING API RATE LIMITER SYSTEM")
        logging.info("=" * 60)
    
    def get_limiter(self, endpoint: str = "default") -> TokenBucketRateLimiter:
        """Get rate limiter for specific endpoint."""
        if endpoint not in self.rate_limiters:
            self.rate_limiters[endpoint] = TokenBucketRateLimiter(self.config)
        
        return self.rate_limiters[endpoint]
    
    def rate_limited(self, endpoint: str = "default", timeout: float = 30.0):
        """Decorator for rate-limited API calls."""
        limiter = self.get_limiter(endpoint)
        return RateLimitedFunction(limiter, timeout)
    
    def get_all_stats(self) -> Dict:
        """Get statistics for all rate limiters."""
        stats = {
            'global': self.global_limiter.get_stats(),
            'endpoints': {}
        }
        
        for endpoint, limiter in self.rate_limiters.items():
            stats['endpoints'][endpoint] = limiter.get_stats()
        
        return stats
    
    def print_stats(self):
        """Print formatted statistics."""
        stats = self.get_all_stats()
        
        print("\n" + "="*60)
        print("API RATE LIMITER STATISTICS")
        print("="*60)
        
        # Global stats
        global_stats = stats['global']
        print(f"\n🌐 GLOBAL STATISTICS:")
        print(f"  Total Requests: {global_stats['total_requests']}")
        print(f"  Successful: {global_stats['successful_requests']}")
        print(f"  Rate Limited: {global_stats['rate_limited_requests']}")
        print(f"  Success Rate: {global_stats['success_rate']:.1f}%")
        print(f"  Avg Response Time: {global_stats['average_response_time']:.3f}s")
        print(f"  Current Tokens: {global_stats['current_tokens']:.1f}/{global_stats['max_tokens']}")
        print(f"  Cooldown Active: {global_stats['cooldown_active']}")
        
        # Endpoint stats
        if stats['endpoints']:
            print(f"\n🔗 ENDPOINT STATISTICS:")
            for endpoint, endpoint_stats in stats['endpoints'].items():
                print(f"  {endpoint}:")
                print(f"    Requests: {endpoint_stats['total_requests']}")
                print(f"    Success Rate: {endpoint_stats['success_rate']:.1f}%")
                print(f"    Avg Response: {endpoint_stats['average_response_time']:.3f}s")
        
        print("="*60 + "\n")

def main():
    """Test the rate limiter."""
    import random
    import time
    
    # Create rate limiter
    config = RateLimitConfig(
        requests_per_minute=10,  # Low for testing
        burst_limit=3,
        cooldown_period_seconds=5,
        enabled=True
    )
    
    rate_limiter = APIRateLimiter(config)
    
    # Test function
    @rate_limiter.rate_limited("test_endpoint", timeout=5.0)
    def test_api_call():
        time.sleep(random.uniform(0.1, 0.5))  # Simulate API call
        if random.random() < 0.1:  # 10% failure rate
            raise Exception("Simulated API error")
        return "success"
    
    # Run tests
    print("Testing API rate limiter...")
    
    for i in range(15):
        try:
            result = test_api_call()
            print(f"Request {i+1}: {result}")
        except Exception as e:
            print(f"Request {i+1}: Failed - {e}")
        
        time.sleep(0.1)
    
    # Print statistics
    rate_limiter.print_stats()

if __name__ == "__main__":
    main() 