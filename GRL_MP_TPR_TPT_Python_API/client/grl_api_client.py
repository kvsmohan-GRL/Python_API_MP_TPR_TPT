
"""
Main API client for interacting with GRL applications.

This module provides the GRLApiClient class which serves as a high-level wrapper
around the GRLApiHandler, adding additional functionality for:
1. Application lifecycle management (launch, connection, shutdown)
2. Test execution and monitoring
3. Popup and dialog handling
4. Project configuration management
5. Diagnostic operations

The client handles common tasks like popup management, test status tracking,
and configuration loading, making it easier to interact with GRL applications
in an automated way.
"""

import contextlib
import json
import os
import threading
import time
from datetime import datetime
from typing import Dict, Any, List

from API import GRLApiHandler
from client.system_state import SystemState
from utils.config_manager import GRLConfigManager
from utils.log_manager import LogManager
from utils.web_app_controller import WebAppController


class GRLApiClient:
    """
    API client for interacting with the GRL application.
    Uses configuration from GRLConfigManager.

    This class provides a high-level interface for:
    1. Initialization and configuration management
    2. Application lifecycle management (launch/disconnect)
    3. Test equipment connection handling
    4. Popup and dialog management
    """

    # ---------------------------------------------------------------------------
    # SECTION: Initialization and Configuration
    # ---------------------------------------------------------------------------

    def __init__(self, config_file_path: str = "grl_config.json") -> None:
        """
        Initialize the GRL API client with configuration.

        This constructor sets up the client by:
        1. Loading configuration from the specified JSON file
        2. Initializing logging infrastructure
        3. Setting up state tracking
        4. Preparing for popup handling and test execution

        Parameters:
            config_file_path: Path to the configuration JSON file
        """
        # Step 1: Initialize configuration manager first
        self.config_manager = GRLConfigManager(config_file_path)

        # Step 2: Initialize default logger temporarily
        temp_log_filename = self.config_manager.log_filename or "grl_api_debug.log"
        self.popup_json_file_name="popup_messages.json"
        self.test_cases_popup_json_file_name = "test_case_popup_messages.json"
        self.log_manager = LogManager(log_filename=temp_log_filename, logger_name="GRLApiClient")
        self.logger = self.log_manager.get_logger()
        self.config_manager.set_logger(self.logger)
        self.log_manager.log_run_start()

        self.logger.info("Initializing GRL API Client")

        # Step 3: Load configuration values
        self.app_name = self.config_manager.app_name
        self.app_path = self.config_manager.app_path
        self.known_port = self.config_manager.known_port
        self.initial_wait = self.config_manager.initial_wait
        self.max_connection_attempts = self.config_manager.max_connection_attempts
        self.connection_timeout = self.config_manager.connection_timeout
        self.api_timeout = self.config_manager.api_timeout
        self.log_filename = self.config_manager.log_filename
        self.ip_address = self.config_manager.ip_address
        self.load_from_json = self.config_manager.load_from_json
        self.project_name_with_time_stamp = self.config_manager.project_name_with_time_stamp
        self.system_state_data = SystemState(app_state='UNKNOWN', connection_state='UNKNOWN')
        self.is_test_list_with_project_name = False

        # Step 4: If log filename changed from temporary one, reinitialize logger
        if self.log_filename != temp_log_filename:
            self.logger.info(f"Switching to log file: {self.log_filename}")
            self.log_manager = LogManager(log_filename=self.log_filename, logger_name="GRLApiClient")
            self.logger = self.log_manager.get_logger()
            self.config_manager.set_logger(self.logger)
            self.log_manager.log_run_start()

        # Step 5: Initialize session and other properties
        self.base_url = None  # Will be set during app launch
        self.controller = None  # WebAppController instance

        # API handler will be initialized when the app is launched
        self.api_handler = None  # GRLApiHandler instance

        self.popup_thread_active = False  # Flag for popup handling thread
        self.stop_requested = False  # Flag for test run stop requests

        # Log the final configuration
        self._log_configuration()

        self.create_empty_json()

    def _log_configuration(self) -> None:
        """
        Log the current configuration settings.
        
        Outputs key configuration parameters to the log file for debugging
        and tracking purposes.
        """
        self.logger.info("GRL API Client Configuration:")
        self.logger.info(f"  Application Name: {self.app_name}")
        self.logger.info(f"  Application Path: {self.app_path}")
        self.logger.info(f"  Known Port: {self.known_port}")
        self.logger.info(f"  Initial Wait: {self.initial_wait} seconds")
        self.logger.info(f"  Log Filename: {self.log_filename}")

    def __del__(self) -> None:
        """
        Destructor to ensure resources are cleaned up safely.
        Automatically calls disconnect() to clean up resources.
        """
        with contextlib.suppress(Exception):
            self.disconnect()

    # ---------------------------------------------------------------------------
    # SECTION: Application Lifecycle Management
    # ---------------------------------------------------------------------------

    def launch_app(self) -> bool:
        """
        Launch the GRL application using WebAppController.
        
        This method:
        1. Initializes the WebAppController
        2. Launches the application process
        3. Establishes connection to the application API
        4. Verifies connectivity by checking software version

        Returns:
            bool: True if the application was launched successfully, False otherwise.
        """
        self.logger.info(f"Launching GRL application: {self.app_path} on port {self.known_port}")

        try:
            # Step 1: Initialize the WebAppController with the application path and port
            self.controller = WebAppController(self.app_path, known_port=self.known_port)
            self.controller.set_logger(self.logger)

            # Step 2: Start the application and get the base URL
            self.base_url = self.controller.start_and_get_url(initial_wait=self.initial_wait)

            if self.base_url:
                # Step 3: If we got a valid URL, initialize the API handler
                api_base_url = f"{self.base_url}/api"
                self.api_handler = GRLApiHandler(api_base_url, self.logger)

                # Step 4: Verify connection by getting the software version
                version = self.api_handler.get_software_version()
                if version and version["response"].get("success"):
                    version_str = version["response"].get("data", "Unknown")
                    self.logger.info(f"Connected to GRL App successfully. Software version: {version_str}")
                    return True
                else:
                    self.logger.error("Failed to get software version - API connection failed")
                    return False
            else:
                self.logger.error("Failed to connect to application - No base URL returned")
                return False

        except Exception as e:
            self.logger.error(f"Exception during application launch: {str(e)}")
            return False

    def disconnect(self) -> None:
        """
        Safely disconnect from the GRL application and close sessions.
        
        This method performs cleanup of all resources:
        1. Stops any running popup handling threads
        2. Closes the API handler connection
        3. Stops the application process
        4. Clears internal state
        """
        self.logger.info("Disconnecting from GRL application")

        # Step 1: Stop the popup handling thread if active
        if getattr(self, 'popup_thread_active', False):
            self.popup_thread_active = False
            self.logger.info("Stopping popup thread")

        # Step 2: Close the API handler
        if self.api_handler:
            try:
                self.api_handler.close()
                self.logger.info("API handler closed successfully")
            except Exception as e:
                self.logger.warning(f"Error closing API handler: {str(e)}")
            self.api_handler = None

        # Step 3: Stop the application process
        if self.controller:
            try:
                self.controller.stop_process()
                self.logger.info("Application process stopped")
            except Exception as e:
                self.logger.warning(f"Error stopping application process: {str(e)}")
            self.controller = None

        # Step 4: Clear the base URL
        self.base_url = None

    # ---------------------------------------------------------------------------
    # SECTION: Test Equipment Connection
    # ---------------------------------------------------------------------------

    def connect(self, ip_address=None):
        """
        Connect to the test equipment.
        
        This method:
        1. Uses the provided IP address or the one from configuration
        2. Starts a popup handling thread to manage connection dialogs
        3. Attempts to connect to the test equipment
        4. Runs diagnostics on successful connection
        
        Parameters:
            ip_address: IP address of the test equipment. If None, will use from config.

        Returns:
            Dict: Connection result or error information.
        """
        self.logger.info("Attempting connection to test equipment")
        self._check_api_handler()

        # Step 1: Get the IP address if not provided
        if not ip_address:
            ip_address = self.ip_address

        # Step 2: Validate the IP address
        if not ip_address:
            self.logger.error("No IP address provided or found.")
            return {"success": False, "error": "No IP address available."}

        # Step 3: Start the popup handling thread
        self.popup_thread_active = True
        popup_thread = threading.Thread(target=self._handle_popups, daemon=True)
        popup_thread.start()

        try:
            # Step 4: Connect to the test equipment
            result = self.api_handler.connect_to_test_equipment(ip_address)
            self._log_connection_result(result)

            if result["response"].get("success"):
                self.logger.info(f"Connected to equipment at {ip_address}")
                self.run_diagnostics()
                return {"success": True, "data": result["response"].get("data")}
            else:
                error_msg = f"Failed to connect to equipment: {result['response'].get('data', 'Unknown error')}"
                self.logger.error(error_msg)
                return {"success": False, "error": error_msg}

        except Exception as e:
            self.logger.error(f"Exception during connection: {str(e)}")
            return {"success": False, "error": str(e)}

        finally:
            # Step 5: Clean up the popup thread
            self.popup_thread_active = False
            popup_thread.join(timeout=2)
            self.logger.info("Popup thread safely stopped after connect")

    def create_empty_json(self):
        """
        Creates empty JSON files for storing popup messages.
        
        Initializes two JSON files:
        1. A file for all popup messages
        2. A file for popup messages organized by test case
        """
        try:
            with open(self.popup_json_file_name, 'w') as file:
                json.dump([], file, indent=4)
            self.logger.info(f"Created empty JSON file: {self.popup_json_file_name}")
            with open(self.test_cases_popup_json_file_name, 'w') as file:
                json.dump([], file, indent=4)
            self.logger.info(f"Created empty JSON file: {self.test_cases_popup_json_file_name}")
        except Exception as e:
            self.logger.error(f"Failed to create empty JSON file '{self.test_cases_popup_json_file_name}': {e}")

    def _log_connection_result(self, result: Dict[str, Any]) -> None:
        """
        Logs the connection result details to debug logs.
        
        Parses the connection result and logs key details for debugging purposes.

        Args:
            result: Dictionary containing connection result data.
        """
        if not result or not result.get("response", {}).get("data"):
            self.logger.debug("No connection result to log.")
            return

        self.logger.debug("Connection Result Details:")
        result_data = result["response"].get("data")

        if isinstance(result_data, dict):
            for key, value in result_data.items():
                self.logger.debug(f"  {key}: {value}")
        else:
            self.logger.debug(f"Connection result is not a dictionary: {result_data}")

    def run_diagnostics(self) -> None:
        """
        Run full API diagnostics on the connected equipment and log the results.
        
        This method performs comprehensive diagnostics including:
        1. API diagnostics via the diagnostics handler
        2. API health check
        3. Version verification
        4. Error log examination
        """
        self.logger.debug("\n=== Running API Diagnostics ===")
        try:
            self.api_handler.log_api_diagnostics()
        except Exception as e:
            self.logger.error(f"Error running API diagnostics: {str(e)}")

        # Check API health
        self.logger.debug("\n=== Checking API Health ===")
        try:
            health_response = self.api_handler.check_api_health()

            # handle dictionary response
            health = health_response.get("response", {}).get("data", {})

            if health:
                self.logger.debug(f"API Health Status: {health.get('overall_status', 'Unknown')}")
                for endpoint, status in health.get("endpoints", {}).items():
                    status_text = status.get("status", "Unknown")
                    response_time = status.get("response_time", "N/A")
                    self.logger.debug(f"  - {endpoint}: {status_text} (Response time: {response_time}s)")
        except Exception as e:
            self.logger.error(f"Error checking API health: {str(e)}")

        # Verify versions
        self.logger.debug("\n=== Verifying Versions ===")
        try:
            versions = self.verify_versions()  # returns a dict

            if versions:
                for key, value in versions.items():
                    self.logger.debug(f"  - {key.replace('_', ' ').title()}: {value}")
        except Exception as e:
            self.logger.error(f"Error retrieving versions: {str(e)}")

        # Get error log (negative test scenario)
        self.logger.debug("\n=== Checking Error Log (Negative Test) ===")

        try:
            import requests
            api_base_url = f"{self.base_url}/api"
            url = f"{api_base_url}/App/GetErrorLog"

            response = requests.get(url)

            status_code = response.status_code
            self.logger.debug(f"Error log response status: {status_code}")

            if 200 <= status_code < 300:
                try:
                    error_log = response.json()
                    if isinstance(error_log, list) and error_log:
                        self.logger.debug(f"Found {len(error_log)} error log entries:")
                        for i, error in enumerate(error_log[:3], 1):
                            self.logger.debug(f"  Error {i}: {error.get('message', 'Unknown error')}")
                        if len(error_log) > 3:
                            self.logger.debug(f"  ... and {len(error_log) - 3} more errors")
                    else:
                        self.logger.debug("No errors found in log.")
                except ValueError:
                    self.logger.debug(f"Error log response is not JSON: {response.text[:100]}")
            else:
                self.logger.warning(
                    f"Expected failure: Unable to retrieve error log (Status: {status_code}) - {response.text}"
                )

        except Exception as e:
            self.logger.exception(f"Unexpected exception occurred while retrieving error log: {str(e)}")

    def verify_versions(self) -> Dict[str, str]:
        """
        Verify and return all version information.
        
        Retrieves version information for various components:
        1. Software version
        2. Firmware version
        3. Electronic load version
        4. Short fixture version
        
        Returns:
            Dict[str, str]: Dictionary mapping version types to their values
        """
        self.logger.info("Verifying software and hardware versions")
        self._check_api_handler()

        try:
            # Get software version
            sw_response = self.api_handler.get_software_version()
            sw_version = sw_response.get("response", {}).get("data", "Unknown")

            # Get firmware version
            fw_version = self.api_handler.get_latest_firmware_version()

            # Get eload version
            eload_version = self.api_handler.get_latest_eload_version()

            # Get short fixture version
            sf_version = self.api_handler.get_latest_short_fixture_version()

            versions = {
                "software_version": sw_version,
                "firmware_version": fw_version,
                "eload_version": eload_version,
                "short_fixture_version": sf_version
            }

            self.logger.info(f"Versions fetched: {versions}")
            return versions

        except Exception as e:
            self.logger.error(f"Failed to verify versions: {str(e)}")
            raise

    def submit_test_list(self, test_list: List[str]) -> Dict[str, Any]:
        """
        Submit a list of test cases to be executed via the API.
        
        This method:
        1. Submits the test list to the API
        2. Monitors the test execution status
        3. Handles popups that appear during testing
        4. Supports cancellation via the stop_requested flag
        
        Args:
            test_list: List of test case names to execute

        Returns:
            Dict: Success/failure information and any error messages
        """
        self.logger.info("Submitting test list for execution...")
        self._check_api_handler()

        if not test_list:
            return {"success": False, "error": "Empty test list provided"}

        # Start the popup handling thread
        self.popup_thread_active = True
        self.stop_requested = False  # Ensure stop_requested flag is initially False
        popup_thread = threading.Thread(target=self._handle_popups, daemon=True)
        popup_thread.start()

        try:
            # Submit the test list
            result = self.api_handler.post_test_list_to_execute(test_list)

            if not result["response"].get("success"):
                self.logger.error(f"Failed to submit test list: {result['response'].get('data', 'Unknown error')}")
                return {"success": False, "error": "Failed to submit test list"}

            self.logger.info("Test list submitted successfully.")

            # Monitor the test status and allow the popup handler to work
            start_time = time.time()
            timeout = 30  # seconds to wait for test to start

            # Wait for test to start
            test_started = False
            while time.time() - start_time < timeout and not self.stop_requested:
                if self._is_test_running():
                    test_started = True
                    break
                time.sleep(1)

            if not test_started and not self.stop_requested:
                self.logger.warning(f"Test did not start within {timeout} seconds")
                return {"success": True, "warning": "Test submission successful but test did not start within timeout"}

            # Monitor until test completes
            while self._is_test_running() and not self.stop_requested:
                time.sleep(0.5)  # Check periodically

            if self.stop_requested:
                self.logger.info("Stop requested by user. Cancelling test submission.")
                self._cancel_running_test()
                return {"success": False, "error": "Test cancelled by user"}

            self.logger.info("Test run complete.")
            return {"success": True}

        except Exception as e:
            error_msg = f"Failed to submit test list: {str(e)}"
            self.logger.error(error_msg)
            return {"success": False, "error": error_msg}
        finally:
            # Ensure the popup handler thread is stopped
            self.popup_thread_active = False
            try:
                popup_thread.join(timeout=2)
                self.logger.info("Popup handler thread safely stopped after submit_test_list")
            except Exception as e:
                self.logger.warning(f"Error stopping popup thread: {str(e)}")

    def _is_test_running(self) -> bool:
        """
        Check if a test is currently running by querying the test status and app state.
        
        This method:
        1. Gets the current test status and app state from the API
        2. Updates the system state tracking
        3. Determines if a test is still running based on status
        
        Returns:
            bool: True if test is still running, False if it has ended.
        """
        try:
            # Get the current test status and app state
            test_status_response = self.api_handler.get_test_status()
            app_state_response = self.api_handler.get_app_state()

            test_status = test_status_response.get("response", {}).get("data", {})
            app_state = app_state_response.get("response", {}).get("data", {})

            self.update_system_state(app_state_dict=app_state,test_status_dict=test_status)
            current_test_status = test_status.get("Test Status", "")
            app_state_value = app_state.get("appState", "")

            self.logger.debug(f"App state: {app_state_value}")
            self.logger.debug(f"Test status: {current_test_status}")

            if app_state_value == "READY":
                self.logger.info("Test has ended. App state is READY.")
                return False

            if "Started" in current_test_status or app_state_value == "BUSY":
                self.logger.info("Test is currently running.")
                return True

            self.logger.info("Test is not running based on current status.")
            return False

        except Exception as e:
            self.logger.error(f"Failed to check test status: {str(e)}")
            return False

    def update_system_state(self, app_state_dict: dict, test_status_dict: dict) -> None:
        """
        Update self.system_state_data based on application state and test status dictionaries.
        
        This method parses the API response data and updates the SystemState object
        with the current application state, connection state, test case name, and test status.
        
        Args:
            app_state_dict: Dictionary containing appState and connectionState
            test_status_dict: Dictionary containing test status information
        """
        try:
            # Update app state and connection state
            self.system_state_data.app_state = app_state_dict.get('appState', 'UNKNOWN')
            self.system_state_data.connection_state = app_state_dict.get('connectionState', 'UNKNOWN')

            # Extract test information if available
            test_info_string = test_status_dict.get('Test Status', '')
            if test_info_string and test_info_string.startswith('Test:'):
                self.logger.info(f"Parsing test info from: {test_info_string}")

                try:
                    # Parse test info - Split the string by colon
                    parts = test_info_string.split(':')

                    # Check if we have at least 3 parts (Test, test_case_name, status)
                    if len(parts) >= 3:
                        # The second item (index 1) is the test case name (after 'Test')
                        test_case_name = parts[1].strip()

                        # The last item is the status
                        status = parts[-1].strip()

                        # Update the system state with parsed values
                        self.system_state_data.test_case_name = test_case_name
                        self.system_state_data.test_status = status

                        self.logger.info(
                            f"Test case updated: {self.system_state_data.test_case_name} - "
                            f"Status: {self.system_state_data.test_status}"
                        )
                    else:
                        self.logger.warning(f"Test info string doesn't have enough parts: {test_info_string}")
                except Exception as e:
                    self.logger.error(f"Error parsing test info: {str(e)}")
            else:
                self.logger.debug("No test status information available")

        except Exception as e:
            self.logger.error(f"Error updating system state: {str(e)}")
            # Set system state to error values in case of failure
            self.system_state_data.app_state = 'ERROR'
            self.system_state_data.connection_state = 'ERROR'
            self.system_state_data.test_case_name = None
            self.system_state_data.test_status = None

    def _cancel_running_test(self) -> bool:
        """
        Cancel a running test.
        
        Sends a force stop command to the API to cancel the current test execution.
        
        Returns:
            bool: True if cancel request was sent successfully, False otherwise
        """
        try:
            response = self.api_handler.post_force_stop()
            if response["response"].get("success"):
                self.logger.info("Test cancelled successfully")
                return True
            else:
                self.logger.error(f"Failed to cancel test: {response['response'].get('data', 'Unknown error')}")
                return False
        except Exception as e:
            self.logger.error(f"Error cancelling test: {str(e)}")
            return False

    def stop_test_execution(self) -> bool:
        """
        Request stopping the test run.
        
        This is the public method for cancelling tests that first checks
        if a test is running before attempting to cancel it.
        
        Returns:
            bool: True if stop request was initiated, False if there's no active test
        """
        if not self._is_test_running():
            self.logger.warning("Cannot stop test - no test is currently running")
            return False

        self.stop_requested = True
        self.logger.info("Stop request received. Test run will be cancelled.")
        return self._cancel_running_test()

    def _check_api_handler(self) -> None:
        """
        Ensure API handler is initialized before performing API operations.
        
        Verifies that launch_app() has been called and the API handler
        is properly initialized before attempting any API operations.
        
        Raises:
            Exception: If the API handler is not initialized.
        """
        if not self.api_handler:
            error_msg = "API handler not initialized. Please call launch_app() first."
            self.logger.error(error_msg)
            raise Exception(error_msg)

    # ---------------------------------------------------------------------------
    # SECTION: Popup and Dialog Management
    # ---------------------------------------------------------------------------

    def _handle_popups(self) -> None:
        """
        Internal thread function to handle popups during connect.
        
        Runs in a separate thread to continuously check for and respond to popups.
        Continues running until popup_thread_active is set to False.
        """
        self.logger.debug("Popup handler thread started")
        while self.popup_thread_active:
            try:
                self._handle_connection_popup()
                time.sleep(0.5)  # Check for popups every 500ms
            except Exception as e:
                self.logger.error(f"Popup handler thread error: {str(e)}")
        self.logger.debug("Popup handler thread exiting")

    def _handle_connection_popup(self) -> None:
        """
        Handle a popup during connection automatically.
        
        This method:
        1. Fetches popup data from the API
        2. Saves the popup message for logging
        3. Creates a standard response to clear the popup
        4. Sends the response back to the application
        """
        if not self.api_handler:
            return

        # Fetch the popup data from the API
        response = self.api_handler.get_message_box()

        if not response.get("response", {}).get("success"):
            return

        popup_data = response.get("response", {}).get("data")
        if not popup_data:
            return

        # Check if the popup_data contains a message
        if not popup_data.get("message"):
            self.logger.debug("No message found in popup data. Skipping response.")
            return
        self.save_only_message(popup_data)
        self.save_message_by_test_case(popup_data)

        # Define the popup response data with changes for expected types
        popupdata = {
            "userTextBoxInput": "",
            "responseButton": "Ok",
            "shouldTextBoxBeAdded": False,
            "isValid": True,
            "popID": popup_data.get("popID", 23),
            "displayPopUp": False,
            "isDisplayPopUpOpen": False,
            "title": popup_data.get("title", "GRL Test Solution"),
            "message": "",
            "button": "OK",
            "image": "",
            "icon": "Asterisk",
            "isFrontEndPopUp": False,
            "callBackMethod": "",
            "comboBoxEntries": "",
            "selectedComboBoxValue": "",
            "comboBoxEntriesFE": [],
            "selectedComboBoxValueFE": "",
            "onlyDropdownAdded": False,
            "enableTimerOKButton": False,
            "enableCustomUserInputs": False,
            "customInputValues": {}
        }



        try:
            # Send the popup response using the API handler
            put_response = self.api_handler.put_message_box_response(popupdata)

            if put_response["response"].get("success"):
                self.logger.debug(f"Popup response sent successfully: {popupdata.get('message', '')}")
            else:
                self.logger.error(
                    f"Failed to send popup response. Status: {put_response['response'].get('status_code')}")

        except Exception as e:
            self.logger.error(f"Failed to send popup response: {str(e)}")

    def save_only_message(self, json_data: dict) -> None:
        """
        Saves a unique popup message to a JSON file.

        Records popup messages in a chronological list in the popup_json_file_name file.

        Args:
            json_data: Dictionary containing the popup data including message
        """
        try:
            file_path = self.popup_json_file_name
            message = json_data.get("message")
            if not message:
                self.logger.debug("No message found in the provided data.")
                return

            messages = []

            if os.path.exists(file_path):
                if os.path.getsize(file_path) > 0:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        messages = json.load(f)
                    self.logger.debug(f"Loaded {len(messages)} existing messages from {file_path}.")
                else:
                    self.logger.debug(f"{file_path} is empty. Initializing with an empty list.")
            else:
                self.logger.debug(f"{file_path} does not exist. A new file will be created.")

            messages.append(message)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(messages, f, indent=4, ensure_ascii=False)
            self.logger.debug("New message saved successfully.")

        except Exception as e:
            self.logger.error(f"Error saving message: {str(e)}")

    def save_message_by_test_case(self, json_data: dict) -> None:
        """
        Saves all popup messages to a JSON file organized by test case name.

        Uses test case name as dictionary key and stores a chronological list of all
        messages for each test case. This helps analyze popup messages in the context
        of specific test cases.

        Args:
            json_data: Dictionary containing the popup data including message
        """
        try:
            file_path = self.test_cases_popup_json_file_name
            # file_path = "test_case_messages.json"
            message = json_data.get("message")
            if not message:
                self.logger.debug("No message found in the provided data.")
                return

            # Get the current test case name from system_state_data
            test_case_name = self.system_state_data.test_case_name
            if not test_case_name:
                test_case_name = "Other_message"  # Default key if no test case name is available
                self.logger.warning("No test case name available, using 'Other_message' as key.")

            # Initialize an empty dictionary to store messages by test case
            messages_by_test = {}

            # Load existing data if the file exists
            if os.path.exists(file_path):
                if os.path.getsize(file_path) > 0:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            messages_by_test = json.load(f)
                        # Check if loaded data is a dictionary
                        if not isinstance(messages_by_test, dict):
                            self.logger.warning(
                                f"Existing file {file_path} is not in dictionary format. Creating new dictionary.")
                            messages_by_test = {}
                        self.logger.debug(f"Loaded messages for {len(messages_by_test)} test cases from {file_path}.")
                    except json.JSONDecodeError:
                        self.logger.warning(f"Error decoding JSON from {file_path}. Creating new dictionary.")
                        messages_by_test = {}
                else:
                    self.logger.debug(f"{file_path} is empty. Initializing with an empty dictionary.")
            else:
                self.logger.debug(f"{file_path} does not exist. A new file will be created.")

            # Initialize list for this test case if it doesn't exist
            if test_case_name not in messages_by_test:
                messages_by_test[test_case_name] = []
                self.logger.debug(f"Created new entry for test case: {test_case_name}")

            # Add message to the list without checking for duplicates
            messages_by_test[test_case_name].append(message)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(messages_by_test, f, indent=4, ensure_ascii=False)
            self.logger.debug(f"Message saved for test case '{test_case_name}': {message[:50]}...")

        except Exception as e:
            self.logger.error(f"Error saving message: {str(e)}")
            self.logger.exception("Detailed traceback:")

        # ---------------------------------------------------------------------------
        # SECTION: Project Management
        # ---------------------------------------------------------------------------

    def _load_config_model(self, json_dir, filename, model_key):
        """
        Helper method to load a configuration model from a JSON file.

        Loads and extracts a specific configuration model from a JSON file.

        Args:
            json_dir (str): Directory containing the JSON files.
            filename (str): JSON file name to load.
            model_key (str): Key of the configuration model inside the file.

        Returns:
            dict or None: Loaded model dict if successful, None if error occurs.
        """
        try:
            file_path = os.path.join(json_dir, filename)
            self.logger.debug(f"Loading {model_key} data from: {file_path}")

            with open(file_path, 'r') as json_file:
                data = json.load(json_file)

            return data.get(model_key)
        except Exception as e:
            self.logger.error(f"Failed to load {model_key} from {filename}: {e}")
            return None

    def set_project(self, project_name: str = None) -> bool:
        """
        Set up a new project on the test system.

        This method:
        1. Loads configuration models from JSON files
        2. Sets up the project name with optional timestamp
        3. Sends the project configuration to the API
        4. Saves test case list to a JSON file

        Args:
            project_name (str, optional): Name of the project. If None, loads from project_config.json.

        Returns:
            bool: True if project created successfully, False otherwise.
        """
        try:
            # Determine JSON directory
            script_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(script_dir)
            json_dir = os.path.join(parent_dir, 'JSON_User_input')

            put_project_config = {}

            # Load all configurations including ProjectConfigurationModel first (for better debugging)

            for fname, key in [
                ('project_config.json', 'ProjectConfigurationModel'),
                ('esdf.json', 'EsdfConfigurationModel'),
                ('tester_config.json', 'TesterConfigurationModel'),
                ('report_config.json', 'ReportConfigurationModel')
            ]:

                model = self._load_config_model(json_dir, fname, key)
                if not model:
                    return False
                put_project_config[key] = model

            # Handle project name setup from config or fallback
            project_model = put_project_config["ProjectConfigurationModel"]

            if not project_name:
                project_name = project_model.get("projectName")
                if not project_name:
                    project_name = "Project"
                    self.logger.info(f"No project name provided. Auto-generated: {project_name}")

            if str(self.project_name_with_time_stamp).lower() == "true":
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                project_name = f"{project_name}_{timestamp}"
                self.logger.info(f"project_name_with_time_stamp is selected. New project name: {project_name}")

            # Set final project name into config
            project_model["projectName"] = project_name

            # Convert and send to API
            with open("project_Configuration_Model_input.json", "w") as f:
                json.dump(put_project_config, f, indent=4)

            response = self.api_handler.put_project_folder(put_project_config)

            if response['response']['success']:
                self.logger.info(f"Project '{project_name}' created successfully.")
                if hasattr(self, 'logs') and hasattr(self.logs, 'Updatelogs'):
                    self.logs.Updatelogs("UI", f"Project {project_name} created successfully.")
                self._save_test_cases_to_json(project_name)
                return True
            else:
                self.logger.error(f"Project creation failed: {response.get_data()}")
                if hasattr(self, 'logs') and hasattr(self.logs, 'Updatelogs'):
                    self.logs.Updatelogs("UI", "Project Creation Failed.")
                return False

        except Exception as e:
            self.logger.error(f"Exception during project setup: {str(e)}")
            if hasattr(self, 'logs') and hasattr(self.logs, 'Updatelogs'):
                self.logs.Updatelogs("UI", f"Project Creation Failed: {str(e)}")
            return False

    def _save_test_cases_to_json(self, project_name):
        """
        Save test case list to a JSON file.

        Retrieves the list of available test cases from the API and saves
        them to a JSON file, either with the project name or with a generic name.

        Args:
            project_name: Name of the project for the output filename
        """
        test_cases_response = self.api_handler.get_test_case_list()

        if test_cases_response["response"].get("success"):
            data = test_cases_response["response"].get("data")

            # If the data is a list, take the first element
            if isinstance(data, list):
                if not data:
                    self.logger.warning("Test case list is empty. Nothing written to file.")
                    return
                data_to_write = data[0]
            else:
                data_to_write = data
                # Check if data_to_write is JSON serializable
                try:
                    json.dumps(data_to_write)  # Just to validate
                except TypeError as e:
                    self.logger.error(f"Data is not JSON serializable: {e}")
                    return

            try:
                output_dir = "Test_Case_List_From_System"
                os.makedirs(output_dir, exist_ok=True)

                if self.is_test_list_with_project_name:
                    filename = f"Test_cases_list_{project_name}.json"
                else:
                    filename = "Generated_Test_cases_list.json"

                # Full path
                json_file_path = os.path.join(output_dir, filename)

                with open(json_file_path, "w", encoding="utf-8") as f:
                    json.dump(data_to_write, f, indent=4)
                self.logger.info(f"Test case data saved to {json_file_path}")
            except Exception as e:
                self.logger.error(f"Failed to write test case to JSON: {e}")
        else:
            self.logger.error(f"Failed to retrieve test cases: {test_cases_response['response'].get('data')}")

    def stop_test_run(self):
        """
        Allow the user to request stopping the test run.

        Sets the stop_requested flag to True, which will be detected by
        the test monitoring loop and trigger cancellation of the test.
        """
        self.stop_requested = True
        self.logger.info("Stop request received. Test run will be canceled.")

