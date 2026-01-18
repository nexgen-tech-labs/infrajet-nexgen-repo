"""
Code Generation API Router.

This module provides RESTful endpoints for autonomous Terraform code generation,
including async job management, validation, diff generation, and monitoring.
"""

from .routes import router

__all__ = ["router"]