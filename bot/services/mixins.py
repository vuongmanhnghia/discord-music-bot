"""
Service Mixins for common patterns
Reduces code duplication and improves maintainability
"""

from typing import Optional, Tuple
from ..pkg.logger import logger
from ..config.service_constants import ErrorMessages


class ValidationMixin:
    """Mixin for common validation patterns in services"""

    @staticmethod
    def validate_guild_context(
        guild_id: int, audio_service
    ) -> Tuple[bool, Optional[object], Optional[object]]:
        """
        Validate and get guild context (audio_player and queue_manager)

        Returns:
            (is_valid, audio_player, queue_manager)
        """
        from .audio_service import audio_service as _audio_service

        audio_player = _audio_service.get_audio_player(guild_id)
        queue_manager = _audio_service.get_queue_manager(guild_id)

        if not audio_player or not queue_manager:
            return False, audio_player, queue_manager

        return True, audio_player, queue_manager


class LoggingMixin:
    """Mixin for smart logging with context"""

    def _log_operation(
        self,
        operation: str,
        guild_id: Optional[int] = None,
        details: str = "",
        level: str = "info",
    ):
        """
        Smart logging with context

        Args:
            operation: Operation name (e.g., "play_song", "skip")
            guild_id: Optional guild ID for context
            details: Additional details
            level: Log level (info, debug, warning, error)
        """
        context = f"[Guild:{guild_id}]" if guild_id else ""
        message = f"{context} {operation}"
        if details:
            message += f" - {details}"

        log_func = getattr(logger, level, logger.info)
        log_func(message)

    def _log_success(
        self, operation: str, guild_id: Optional[int] = None, details: str = ""
    ):
        """Log successful operation"""
        self._log_operation(f"✅ {operation}", guild_id, details, "info")

    def _log_error(
        self, operation: str, error: Exception, guild_id: Optional[int] = None
    ):
        """Log error with exception"""
        self._log_operation(f"❌ {operation} failed", guild_id, str(error), "error")

    def _log_warning(self, operation: str, reason: str, guild_id: Optional[int] = None):
        """Log warning"""
        self._log_operation(f"⚠️ {operation}", guild_id, reason, "warning")


class ErrorHandlingMixin:
    """Mixin for consistent error handling"""

    @staticmethod
    def safe_execute(operation_name: str, func, *args, **kwargs):
        """
        Safely execute a function with consistent error handling

        Returns:
            (success, result_or_error_message)
        """
        try:
            result = func(*args, **kwargs)
            return True, result
        except Exception as e:
            logger.error(f"{operation_name} failed: {e}")
            return False, str(e)

    @staticmethod
    async def safe_execute_async(operation_name: str, func, *args, **kwargs):
        """
        Safely execute an async function with consistent error handling

        Returns:
            (success, result_or_error_message)
        """
        try:
            result = await func(*args, **kwargs)
            return True, result
        except Exception as e:
            logger.error(f"{operation_name} failed: {e}")
            return False, str(e)
