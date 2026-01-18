"""
Application middleware package.
"""

from .error_handler import ErrorHandlingMiddleware

__all__ = ["ErrorHandlingMiddleware"]
