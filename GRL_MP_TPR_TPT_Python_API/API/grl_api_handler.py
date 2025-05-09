"""
Consolidated API handler for GRL application.

This module provides the main GRLApiHandler class which is responsible for:
1. Making HTTP requests to the GRL application API
2. Handling connection to test equipment
3. Managing test execution
4. Handling project configuration
5. Processing message box responses

The GRLApiHandler consolidates functionality that was previously spread across
multiple handler classes, providing a unified interface for API interactions.
"""
import logging
import requests
from typing import Dict, Any, List, Optional

# Logger configuration
logger = logging.getLogger(__name__)


class GRLApiHandler:
    """
    Complete GRL API handler with core functionality.

    This handler consolidates connection, test execution, configuration, and reporting methods.
    Diagnostics functionality is kept in a separate module but is accessible through
    convenience methods.

    Attributes:
        base_url (str): Base URL for the API endpoints
        logger (Logger): Logger instance for recording operations
        session (Session): Requests session for making HTTP requests
    """

    def __init__(self, base_url: str, custom_logger: Optional[logging.Logger] = None):
        """
        Initialize the GRL API handler.

        Args:
            base_url: Base URL for the API (e.g., "http://localhost:8080/api")
            custom_logger: Optional logger instance. If None, a default logger is used.
        """
        self.base_url = base_url.rstrip("/")
        self.logger = custom_logger or logger
        self.session = requests.Session()
        self.logger.info(f"Initialized GRLApiHandler with base URL: {self.base_url}")

    #---------------------------------------------------------------------------
    # Base API functionality
    #---------------------------------------------------------------------------

    def send_request(self,
                    method: str,
                    service: str,
                    endpoint: str = "",
                    params: Optional[Dict] = None,
                    data: Optional[Dict] = None,
                    headers: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Send an HTTP request to the API.

        This is the core method that handles all API communication. It constructs
        the request, sends it, and processes the response.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            service: API service name (e.g., "App", "ConnectionSetup")
            endpoint: API endpoint path (e.g., "GetSoftwareVersion")
            params: Optional query parameters
            data: Optional request body data
            headers: Optional HTTP headers

        Returns:
            Dict containing both request and response information
        """
        url = f"{self.base_url}/{service}"
        if endpoint:
            url += f"/{endpoint}"

        headers = headers or {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        self.logger.info(f"Sending {method.upper()} request to {url}")
        if params:
            self.logger.debug(f"Query Parameters: {params}")
        if data:
            self.logger.debug(f"Request Body: {data}")

        result = {
            "request": {
                "method": method.upper(),
                "url": url,
                "params": params,
                "data": data,
                "headers": headers
            },
            "response": {}
        }

        try:
            response = self._dispatch_request(method.upper(), url, params, data, headers)
            result["response"].update({
                "status_code": response.status_code,
                "success": 200 <= response.status_code < 300,
                "headers": dict(response.headers),
                "content_type": response.headers.get("Content-Type", "")
            })

            try:
                result["response"]["data"] = response.json()
                result["response"]["content_type"] = "json"
            except ValueError:
                result["response"]["data"] = response.text
                result["response"]["content_type"] = "text"

            self.logger.info(f"Response Status: {response.status_code}")
            return result

        except requests.exceptions.ConnectionError:
            error_msg = "Connection error"
        except requests.exceptions.Timeout:
            error_msg = "Request timed out"
        except requests.exceptions.RequestException as e:
            error_msg = str(e)

        self.logger.error(f"Request failed: {error_msg}")
        result["response"]["error"] = error_msg
        return result

    def _dispatch_request(self, method: str, url: str,
                        params: Optional[Dict], data: Optional[Dict],
                        headers: Dict) -> requests.Response:
        """
        Dispatch the HTTP request using the appropriate method.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            url: Complete URL for the request
            params: Query parameters
            data: Request body data
            headers: HTTP headers

        Returns:
            Response object from the requests library

        Raises:
            ValueError: If an unsupported HTTP method is provided
        """
        if method == "GET":
            return self.session.get(url, params=params, headers=headers)
        elif method == "POST":
            return self.session.post(url, params=params, json=data, headers=headers)
        elif method == "PUT":
            return self.session.put(url, params=params, json=data, headers=headers)
        elif method == "DELETE":
            return self.session.delete(url, params=params, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

    def close(self) -> None:
        """
        Close the HTTP session and free resources.

        This should be called when the handler is no longer needed to ensure
        proper cleanup of resources.
        """
        self.session.close()
        self.logger.info("Session closed.")

    #---------------------------------------------------------------------------
    # Connection related methods
    #---------------------------------------------------------------------------

    def get_latest_firmware_version(self) -> str:
        """
        Get the latest firmware version from the test equipment.

        Returns:
            String representation of the firmware version
        """
        return self._get_latest_version("LatestFirmwareVersion", "firmware")

    def get_latest_eload_version(self) -> str:
        """
        Get the latest electronic load version from the test equipment.

        Returns:
            String representation of the eload version
        """
        return self._get_latest_version("LatestEloadVersion", "eload")

    def get_latest_short_fixture_version(self) -> str:
        """
        Get the latest short fixture version from the test equipment.

        Returns:
            String representation of the short fixture version
        """
        return self._get_latest_version("LatestShortFixtureVersion", "short fixture")

    def _get_latest_version(self, endpoint_suffix: str, version_label: str) -> str:
        """
        Helper method to retrieve version information.

        Args:
            endpoint_suffix: API endpoint suffix for the version request
            version_label: Label for logging purposes

        Returns:
            String representation of the requested version
        """
        self.logger.info(f"Getting latest {version_label} version")
        response = self.send_request("GET", "ConnectionSetup", endpoint_suffix)

        if response["response"].get("success"):
            data = response["response"].get("data", "")
            if isinstance(data, dict):
                return data.get("text_response", "")
            return str(data)

        self.logger.error(f"Failed to get {version_label} version: {response['response'].get('data')}")
        return ""

    def connect_to_test_equipment(self, ip_address: str) -> Dict[str, Any]:
        """
        Connect to the test equipment at the specified IP address.

        Args:
            ip_address: IP address of the test equipment

        Returns:
            Dictionary containing connection result information
        """
        self.logger.info(f"Connecting to test equipment at: {ip_address}")
        return self.send_request("GET", "ConnectionSetup", ip_address)

    #---------------------------------------------------------------------------
    # Test execution methods
    #---------------------------------------------------------------------------

    def get_software_version(self) -> Dict[str, Any]:
        """
        Get the software version of the GRL application.

        Returns:
            Dictionary containing version information
        """
        self.logger.info("Getting software version")
        return self.send_request("GET", "App", "GetSoftwareVersion")

    def get_message_box(self) -> Dict[str, Any]:
        """
        Get message box data from the application.

        This retrieves any active popup messages that may need user response.

        Returns:
            Dictionary containing message box information
        """
        self.logger.debug("Fetching message box data")
        response = self.send_request("GET", "App", "GetMessageBox")
        self.logger.debug(f"Raw response: {response}")
        return response

    def get_test_case_list(self) -> Dict[str, Any]:
        """
        Get the list of available test cases.

        Returns:
            Dictionary containing the test case list
        """
        self.logger.info("Getting test case list")
        return self.send_request("GET", "TestConfiguration", "GetTestCaseList")

    def get_app_state(self) -> Dict[str, Any]:
        """
        Get the current state of the application.

        This returns information about whether the application is READY, BUSY, etc.

        Returns:
            Dictionary containing application state information
        """
        self.logger.info("Fetching application state")
        return self.send_request("GET", "App", "GetAppState")

    def get_test_status(self) -> Dict[str, Any]:
        """
        Get the status of the current test.

        Returns:
            Dictionary containing test status information
        """
        self.logger.info("Fetching current test status")
        return self.send_request("GET", "Results", "GetTestStatus")

    def post_force_stop(self) -> Dict[str, Any]:
        """
        Force stop the current test execution.

        Returns:
            Dictionary containing the result of the stop request
        """
        self.logger.info("Sending force stop request")
        return self.send_request("POST", "ConnectionSetup", "ForceStopCurrentExecution")

    def post_test_list_to_execute(self, test_list: List[str]) -> Dict[str, Any]:
        """
        Submit a list of test cases to be executed.

        Args:
            test_list: List of test case names to execute

        Returns:
            Dictionary containing the result of the submission
        """
        self.logger.info(f"Submitting {len(test_list)} tests to execute")
        endpoint = "PostTestListToExecute/0/true"  # Using default groupIndex=0, enableTestCase=True
        return self.send_request("POST", "TestConfiguration", endpoint, data=test_list)

    #---------------------------------------------------------------------------
    # Configuration methods
    #---------------------------------------------------------------------------

    def put_project_folder(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create or update a project folder with the provided configuration.

        Args:
            project_data: Dictionary containing project configuration data

        Returns:
            Dictionary containing the result of the operation

        Raises:
            Exception: If the project folder creation fails
        """
        try:
            self.logger.info("Updating put project folder")
            return self.send_request("PUT", "TestConfiguration", "PutProjectFolder", data=project_data)
        except Exception as e:
            self.logger.error(f"Failed to create project folder: {str(e)}")
            raise

    #---------------------------------------------------------------------------
    # Reporting methods
    #---------------------------------------------------------------------------

    def put_message_box_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a response to an active message box/dialog.

        Args:
            response_data: Dictionary containing response information

        Returns:
            Dictionary containing the result of the response
        """
        pop_id = response_data.get("popID", "unknown")
        button = response_data.get("responseButton", "unknown")
        self.logger.info(f"Putting message box response (popID: {pop_id}, button: {button})")
        return self.send_request("PUT", "App", "PutMessageBoxResponse", data=response_data)

    #---------------------------------------------------------------------------
    # Diagnostics integration methods (for using DiagnosticsApiHandler)
    #---------------------------------------------------------------------------

    def check_api_health(self, use_parallel: bool = False) -> Dict[str, Any]:
        """
        Check the health of the API endpoints.

        This is a convenience method that delegates to the DiagnosticsApiHandler
        to perform health checks on various API endpoints.

        Args:
            use_parallel: Whether to check endpoints in parallel

        Returns:
            Dictionary containing health check results
        """
        from API.diagnostics_api_handler import DiagnosticsApiHandler

        # Create temporary diagnostics handler using our session/logger
        diagnostics = DiagnosticsApiHandler(self.base_url, self.logger)

        # Pass our session to the diagnostics handler to maintain auth state
        diagnostics.session = self.session

        # Delegate the call
        return diagnostics.check_api_health(use_parallel)

    def log_api_diagnostics(self) -> None:
        """
        Run comprehensive API diagnostics and log the results.

        This is a convenience method that delegates to the DiagnosticsApiHandler
        to perform detailed diagnostics on the API.
        """
        from API.diagnostics_api_handler import DiagnosticsApiHandler

        # Create temporary diagnostics handler using our session/logger
        diagnostics = DiagnosticsApiHandler(self.base_url, self.logger)

        # Pass our session to the diagnostics handler to maintain auth state
        diagnostics.session = self.session

        # Delegate the call
        diagnostics.log_api_diagnostics()