"""
Handler for system-level diagnostics and health checks.

This module provides specialized functionality for performing diagnostic
operations on the GRL application API. It is kept separate from the main
GRLApiHandler as it provides specialized functionality that is not always needed.

The module includes:
1. API health checks that can verify connectivity to various endpoints
2. Comprehensive diagnostics that gather and log system information
"""
import logging
import time
import concurrent.futures
from typing import Dict, Any

from API.decorators import api_call

logger = logging.getLogger(__name__)


class DiagnosticsApiHandler:
    """
    Handler for system-level diagnostics and health checks.

    This handler provides methods for verifying API connectivity and gathering
    diagnostic information about the system state.

    Attributes:
        base_url (str): Base URL for the API endpoints
        logger (Logger): Logger instance for recording operations
        session: Session object (optional) for making HTTP requests
    """

    def __init__(self, base_url: str, custom_logger=None):
        """
        Initialize the diagnostics handler.

        Args:
            base_url: Base URL for the API
            custom_logger: Optional logger instance
        """
        self.base_url = base_url.rstrip("/")
        self.logger = custom_logger or logger
        self.session = None  # Will be set by the main GRLApiHandler when needed

    def send_request(self, method, service, endpoint="", params=None, data=None, headers=None):
        """
        Send an HTTP request to the API.

        This method provides a passthrough implementation to support standalone usage
        or delegation to the parent GRLApiHandler's implementation.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            service: API service name
            endpoint: API endpoint path
            params: Query parameters
            data: Request body data
            headers: HTTP headers

        Returns:
            Dictionary containing the response
        """
        # If this handler was created by GRLApiHandler and session exists
        if hasattr(self, 'session') and self.session:
            # Import here to avoid circular imports
            from API.grl_api_handler import GRLApiHandler

            # Create a temporary handler that shares our session
            temp_handler = GRLApiHandler(self.base_url, self.logger)
            temp_handler.session = self.session

            # Use its send_request method
            return temp_handler.send_request(method, service, endpoint, params, data, headers)

        # Fallback implementation for standalone usage
        self.logger.error("DiagnosticsApiHandler must be initialized with a session")
        return {
            "response": {
                "success": False,
                "error": "No session available in DiagnosticsApiHandler"
            }
        }

    @api_call
    def check_api_health(self, use_parallel: bool = False) -> Dict[str, Any]:
        """
        Check the health of various API endpoints.

        This method tests connectivity to key API endpoints and reports
        their status and response times.

        Args:
            use_parallel: Whether to check endpoints in parallel for faster results

        Returns:
            Dictionary containing health check results with the following structure:
            {
                "timestamp": "YYYY-MM-DD HH:MM:SS",
                "endpoints": {
                    "endpoint1": {"status": "ok", "response_time": 0.123},
                    ...
                },
                "overall_status": "healthy|degraded|critical"
            }
        """
        self.logger.info("Running API health check")

        health_results = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "endpoints": {},
            "overall_status": "unknown"
        }

        # Define key endpoints to check
        endpoints = [
            ("App", "GetSoftwareVersion"),
            ("ConnectionSetup", "GetIPAddressHistory"),
            ("TestConfiguration", "GetCoilFilter")
        ]

        def check(service: str, endpoint: str) -> bool:
            """
            Check a single endpoint and record its status.

            Args:
                service: API service name
                endpoint: API endpoint path

            Returns:
                Boolean indicating if the endpoint is healthy
            """
            endpoint_key = f"{service}_{endpoint}".replace("/", "_")
            start_time = time.time()
            response = self.send_request("GET", service, endpoint)
            duration = round(time.time() - start_time, 3)

            success = response["response"].get("success", False)
            health_results["endpoints"][endpoint_key] = {
                "status": "ok" if success else "error",
                "response_time": duration,
                "status_code": response["response"].get("status_code", 0)
            }
            return success

        # Execute checks - either in parallel or sequentially
        if use_parallel:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                results = executor.map(lambda ep: check(*ep), endpoints)
                success_count = sum(results)
        else:
            success_count = sum(check(*ep) for ep in endpoints)

        # Determine overall health status
        health_results["overall_status"] = (
            "healthy" if success_count == len(endpoints)
            else "degraded" if success_count > 0
            else "critical"
        )

        self.logger.info(f"API Health Status: {health_results['overall_status']}")
        return health_results

    @api_call
    def log_api_diagnostics(self) -> None:
        """
        Run comprehensive API diagnostics and log the results.

        This method gathers information about:
        - Software, firmware, and eload versions
        - Connected IP addresses
        - Available test cases
        - Coil filter configurations

        All information is logged at INFO level.
        """
        self.logger.info("=== GRL API Diagnostics ===")

        # Versions
        versions = {
            "software": self.send_request("GET", "App", "GetSoftwareVersion"),
            "firmware": self.send_request("GET", "ConnectionSetup", "LatestFirmwareVersion"),
            "eload": self.send_request("GET", "ConnectionSetup", "LatestEloadVersion")
        }

        # IP History
        ip_response = self.send_request("GET", "ConnectionSetup", "GetIPAddressHistory")
        ip_data = ip_response["response"].get("data", [])
        active_ips = [entry.get("ipAddress") for entry in ip_data if entry.get("isActive")]

        # Test cases
        tc_response = self.send_request("GET", "TestConfiguration", "GetTestCaseList")
        test_cases = tc_response["response"].get("data", [])

        # Coil Filters
        coil_response = self.send_request("GET", "TestConfiguration", "GetCoilFilter")
        coil_filters = coil_response["response"].get("data", [])

        # Log collected info
        self.logger.info(f"Software Version: {versions['software']['response'].get('data')}")
        self.logger.info(f"Firmware Version: {versions['firmware']['response'].get('data')}")
        self.logger.info(f"Eload Version: {versions['eload']['response'].get('data')}")
        self.logger.info(f"Active IPs: {', '.join(active_ips) if active_ips else 'None'}")
        self.logger.info(f"Test Case Count: {len(test_cases)}")
        self.logger.info(f"Coil Filters: {', '.join(coil_filters) if coil_filters else 'None'}")