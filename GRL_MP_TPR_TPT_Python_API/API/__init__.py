"""
API handler module for GRL application APIs.

This module provides the main entry point for interacting with GRL application
APIs. It exports the GRLApiHandler class as the primary interface for making
API calls to the GRL application.

Usage:
    from API import GRLApiHandler

    api_handler = GRLApiHandler(base_url)
    version = api_handler.get_software_version()
"""
from API.grl_api_handler import GRLApiHandler

# Export GRLApiHandler as the primary interface
__all__ = ['GRLApiHandler']