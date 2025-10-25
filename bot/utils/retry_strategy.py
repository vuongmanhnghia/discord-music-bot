"""
Retry Strategy for external service calls
Centralizes retry logic with exponential backoff
"""

import asyncio
import random
from typing import Optional, Callable, Any, TypeVar
from ..pkg.logger import logger

T = TypeVar("T")


class RetryStrategy:
    """Generic retry strategy with exponential backoff and jitter"""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        backoff_factor: float = 2.0,
        timeout: int = 30,
        jitter: bool = True,
    ):
        """
        Initialize retry strategy

        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Base delay in seconds before first retry
            backoff_factor: Multiplier for exponential backoff
            timeout: Timeout in seconds for each attempt
            jitter: Add random jitter to prevent thundering herd
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.backoff_factor = backoff_factor
        self.timeout = timeout
        self.jitter = jitter

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and optional jitter"""
        delay = self.base_delay * (self.backoff_factor**attempt)
        if self.jitter:
            # Add random jitter ±25%
            jitter_amount = delay * 0.25
            delay += random.uniform(-jitter_amount, jitter_amount)
        return max(0, delay)

    async def execute(
        self,
        operation: Callable[..., Any],
        operation_name: str = "operation",
    ) -> Optional[T]:
        """
        Execute operation with retry logic

        Args:
            operation: Async function to execute (no arguments)
            operation_name: Name for logging

        Returns:
            Result of operation or None if all retries failed
        """
        last_exception = None

        for attempt in range(self.max_attempts):
            try:
                result = await asyncio.wait_for(operation(), timeout=self.timeout)
                return result

            except asyncio.TimeoutError as e:
                last_exception = e
                if attempt < self.max_attempts - 1:
                    delay = self._calculate_delay(attempt)
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"{operation_name} failed after {self.max_attempts} timeout attempts")

            except Exception as e:
                last_exception = e
                if attempt < self.max_attempts - 1:
                    delay = self._calculate_delay(attempt)
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"{operation_name} failed after {self.max_attempts} attempts: {e}")

        return None
