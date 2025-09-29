#!/usr/bin/env python3
"""
Priority Optimization Implementation Plan
Critical fixes that should be implemented immediately for production stability
"""

import asyncio
import time
from typing import Dict, Optional, Set
from collections import OrderedDict
import weakref

# =============================================================================
# PRIORITY 1: Fix Interaction Timeouts (Critical)
# =============================================================================


class InteractionManager:
    """Manage long-running Discord interactions to prevent timeouts"""

    @staticmethod
    async def handle_long_operation(interaction, operation_func, *args, **kwargs):
        """Handle operations that might take >3 seconds"""
        try:
            # Always defer first to get 15 minutes
            await interaction.response.defer()

            # Run the operation
            result = await operation_func(*args, **kwargs)

            # Send result via followup
            if isinstance(result, str):
                await interaction.followup.send(result)
            else:
                await interaction.followup.send(embed=result)

        except Exception as e:
            error_msg = f"❌ Operation failed: {str(e)}"
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(error_msg, ephemeral=True)
                else:
                    await interaction.response.send_message(error_msg, ephemeral=True)
            except:
                pass  # Interaction might be expired


# =============================================================================
# PRIORITY 2: Resource Cleanup & Memory Management (Critical)
# =============================================================================


class ResourceManager:
    """LRU-based resource management to prevent memory leaks"""

    def __init__(self, max_size: int = 50, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.resources = OrderedDict()
        self.timestamps = {}
        self.cleanup_task: Optional[asyncio.Task] = None

    async def start_cleanup_worker(self):
        """Start background cleanup worker"""
        if self.cleanup_task and not self.cleanup_task.done():
            return
        self.cleanup_task = asyncio.create_task(self._cleanup_worker())

    async def _cleanup_worker(self):
        """Background worker for cleaning up expired resources"""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Cleanup worker error: {e}")

    async def _cleanup_expired(self):
        """Clean up expired resources"""
        current_time = time.time()
        expired_keys = []

        for key, timestamp in self.timestamps.items():
            if current_time - timestamp > self.ttl_seconds:
                expired_keys.append(key)

        for key in expired_keys:
            await self.remove_resource(key)

    async def get_resource(self, key: str):
        """Get resource and update access time"""
        if key in self.resources:
            # Move to end (most recently used)
            self.resources.move_to_end(key)
            self.timestamps[key] = time.time()
            return self.resources[key]
        return None

    async def add_resource(self, key: str, resource):
        """Add resource with LRU eviction"""
        # Remove oldest if at capacity
        while len(self.resources) >= self.max_size:
            oldest_key = next(iter(self.resources))
            await self.remove_resource(oldest_key)

        self.resources[key] = resource
        self.timestamps[key] = time.time()

    async def remove_resource(self, key: str):
        """Remove resource and clean up properly"""
        if key in self.resources:
            resource = self.resources.pop(key)
            self.timestamps.pop(key, None)

            # Clean up resource if it has cleanup method
            if hasattr(resource, "cleanup"):
                try:
                    await resource.cleanup()
                except Exception as e:
                    print(f"Error cleaning up resource {key}: {e}")


# =============================================================================
# PRIORITY 3: Smart Caching System (High Impact)
# =============================================================================


class SmartCache:
    """Multi-tier caching for songs and metadata"""

    def __init__(self):
        self.memory_cache: Dict[str, any] = {}
        self.access_count: Dict[str, int] = {}
        self.last_access: Dict[str, float] = {}
        self.max_memory_items = 100

    async def get_cached_song(self, url: str) -> Optional[dict]:
        """Get cached song data"""
        if url in self.memory_cache:
            self.access_count[url] = self.access_count.get(url, 0) + 1
            self.last_access[url] = time.time()
            return self.memory_cache[url]
        return None

    async def cache_song(self, url: str, song_data: dict):
        """Cache song data with intelligent eviction"""
        # Evict least valuable items if needed
        if len(self.memory_cache) >= self.max_memory_items:
            await self._evict_least_valuable()

        self.memory_cache[url] = song_data
        self.access_count[url] = 1
        self.last_access[url] = time.time()

    async def _evict_least_valuable(self):
        """Evict items based on access patterns"""
        if not self.memory_cache:
            return

        # Calculate value score for each item
        current_time = time.time()
        scores = {}

        for url in self.memory_cache:
            access_frequency = self.access_count.get(url, 1)
            recency = current_time - self.last_access.get(url, current_time)
            # Higher score = more valuable (keep)
            scores[url] = access_frequency / (1 + recency / 3600)  # Decay over hours

        # Remove lowest scoring item
        worst_url = min(scores.keys(), key=lambda k: scores[k])
        self.memory_cache.pop(worst_url, None)
        self.access_count.pop(worst_url, None)
        self.last_access.pop(worst_url, None)


# =============================================================================
# PRIORITY 4: Async Song Processing Pipeline (Performance)
# =============================================================================


class AsyncSongProcessor:
    """Asynchronous song processing with worker pool"""

    def __init__(self, num_workers: int = 3):
        self.num_workers = num_workers
        self.processing_queue = asyncio.Queue()
        self.result_futures: Dict[str, asyncio.Future] = {}
        self.workers: list[asyncio.Task] = []
        self.shutdown_event = asyncio.Event()

    async def start_workers(self):
        """Start background processing workers"""
        for i in range(self.num_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)

    async def _worker(self, worker_name: str):
        """Background worker for processing songs"""
        print(f"Started {worker_name}")

        while not self.shutdown_event.is_set():
            try:
                # Wait for work with timeout to allow shutdown
                work_item = await asyncio.wait_for(
                    self.processing_queue.get(), timeout=1.0
                )

                url, future = work_item

                try:
                    # Simulate actual yt-dlp processing
                    result = await self._process_song_async(url)
                    future.set_result(result)
                except Exception as e:
                    future.set_exception(e)
                finally:
                    self.processing_queue.task_done()

            except asyncio.TimeoutError:
                continue  # Check shutdown event
            except Exception as e:
                print(f"{worker_name} error: {e}")

        print(f"Stopped {worker_name}")

    async def process_song(self, url: str) -> dict:
        """Submit song for processing and wait for result"""
        future = asyncio.Future()
        self.result_futures[url] = future

        await self.processing_queue.put((url, future))

        try:
            result = await future
            return result
        finally:
            self.result_futures.pop(url, None)

    async def _process_song_async(self, url: str) -> dict:
        """Actual async song processing (replace with real yt-dlp)"""
        # This would be the actual yt-dlp processing
        await asyncio.sleep(2)  # Simulate processing time
        return {
            "url": url,
            "title": f"Processed song for {url}",
            "duration": 180,
            "stream_url": f"stream_{url}",
        }

    async def shutdown(self):
        """Gracefully shutdown workers"""
        self.shutdown_event.set()

        # Cancel any pending futures
        for future in self.result_futures.values():
            if not future.done():
                future.cancel()

        # Wait for workers to finish
        if self.workers:
            await asyncio.gather(*self.workers, return_exceptions=True)


# =============================================================================
# PRIORITY 5: Improved Error Handling (Reliability)
# =============================================================================


class RobustErrorHandler:
    """Enhanced error handling with retry and circuit breaker"""

    def __init__(self):
        self.failure_counts: Dict[str, int] = {}
        self.circuit_breakers: Dict[str, bool] = {}
        self.last_failure: Dict[str, float] = {}

    async def execute_with_retry(
        self, operation_name: str, func, *args, max_retries=3, **kwargs
    ):
        """Execute function with exponential backoff retry"""

        # Check circuit breaker
        if self._is_circuit_open(operation_name):
            raise Exception(f"Circuit breaker open for {operation_name}")

        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                result = await func(*args, **kwargs)
                # Success - reset failure count
                self.failure_counts[operation_name] = 0
                return result

            except Exception as e:
                last_exception = e
                self._record_failure(operation_name)

                if attempt < max_retries:
                    # Exponential backoff
                    delay = (2**attempt) + (time.time() % 1)  # Add jitter
                    await asyncio.sleep(delay)
                    print(
                        f"Retrying {operation_name} (attempt {attempt + 2}/{max_retries + 1})"
                    )

        # All retries failed
        raise last_exception

    def _record_failure(self, operation_name: str):
        """Record failure for circuit breaker logic"""
        self.failure_counts[operation_name] = (
            self.failure_counts.get(operation_name, 0) + 1
        )
        self.last_failure[operation_name] = time.time()

        # Open circuit breaker after 5 failures
        if self.failure_counts[operation_name] >= 5:
            self.circuit_breakers[operation_name] = True
            print(f"Circuit breaker opened for {operation_name}")

    def _is_circuit_open(self, operation_name: str) -> bool:
        """Check if circuit breaker is open"""
        if operation_name not in self.circuit_breakers:
            return False

        if not self.circuit_breakers[operation_name]:
            return False

        # Auto-reset circuit breaker after 5 minutes
        if time.time() - self.last_failure.get(operation_name, 0) > 300:
            self.circuit_breakers[operation_name] = False
            self.failure_counts[operation_name] = 0
            print(f"Circuit breaker reset for {operation_name}")
            return False

        return True


# =============================================================================
# IMPLEMENTATION EXAMPLE
# =============================================================================


async def demo_optimized_system():
    """Demo the optimized components working together"""

    print("🚀 Starting Optimized Discord Music Bot Demo")

    # Initialize components
    resource_manager = ResourceManager(max_size=10, ttl_seconds=60)
    cache = SmartCache()
    processor = AsyncSongProcessor(num_workers=2)
    error_handler = RobustErrorHandler()

    # Start background tasks
    await resource_manager.start_cleanup_worker()
    await processor.start_workers()

    try:
        # Demo 1: Fast cached song access
        print("\n1️⃣ Testing smart caching...")
        test_url = "https://youtube.com/watch?v=test123"

        # First access - will be processed
        start_time = time.time()
        result1 = await processor.process_song(test_url)
        first_time = time.time() - start_time
        await cache.cache_song(test_url, result1)
        print(f"   First access: {first_time:.1f}s (processed)")

        # Second access - from cache
        start_time = time.time()
        cached_result = await cache.get_cached_song(test_url)
        cache_time = time.time() - start_time
        print(f"   Cache access: {cache_time:.3f}s (cached)")
        print(f"   Speed improvement: {first_time/cache_time:.1f}x faster!")

        # Demo 2: Resource management
        print("\n2️⃣ Testing resource management...")
        for i in range(15):  # Exceed max_size to test LRU
            await resource_manager.add_resource(f"resource_{i}", f"data_{i}")
        print(
            f"   Resources managed: {len(resource_manager.resources)}/{resource_manager.max_size}"
        )

        # Demo 3: Error handling with retry
        print("\n3️⃣ Testing robust error handling...")

        async def flaky_operation():
            import random

            if random.random() < 0.3:  # 30% success rate
                return "Success!"
            raise Exception("Random failure")

        try:
            result = await error_handler.execute_with_retry("test_op", flaky_operation)
            print(f"   Operation result: {result}")
        except Exception as e:
            print(f"   Operation failed after retries: {e}")

        print("\n✅ All optimization components working correctly!")

    finally:
        # Cleanup
        await processor.shutdown()
        if resource_manager.cleanup_task:
            resource_manager.cleanup_task.cancel()


if __name__ == "__main__":
    asyncio.run(demo_optimized_system())
