"""
Decorators for API handlers.

This module provides decorators that can be applied to API handler methods
to add common functionality like logging, error handling, and performance
monitoring.

These decorators help maintain consistent behavior across all API calls and
simplify error tracking.
"""
from functools import wraps
import logging
import traceback

logger = logging.getLogger(__name__)


def api_call(func):
    """
    Decorator to wrap API methods for logging entry, exit, and error handling.

    This decorator:
    1. Logs method entry with arguments
    2. Executes the method and catches any exceptions
    3. Logs method exit with return value or error details
    4. Re-raises any exceptions for proper error handling

    Args:
        func: The function to be decorated

    Returns:
        Wrapped function with logging and error handling

    Example:
        @api_call
        def get_version(self):
            # Method implementation
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        # Get logger from instance or use module logger
        log = getattr(self, "logger", logger)
        func_name = f"{self.__class__.__name__}.{func.__name__}"

        # Log method entry
        log.debug(f"[ENTRY] {func_name} | args={args}, kwargs={kwargs}")

        try:
            # Execute the method
            result = func(self, *args, **kwargs)

            # Log successful exit
            log.debug(f"[EXIT] {func_name} | result={repr(result)}")
            return result

        except Exception as e:
            # Log error with traceback
            log.error(f"[ERROR] {func_name} raised: {e}")
            log.debug(traceback.format_exc())

            # Re-raise the exception
            raise

    return wrapper