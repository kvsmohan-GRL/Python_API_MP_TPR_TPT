"""
Configuration manager for GRL API.
Handles loading application configuration settings from JSON file.
"""

import json
import logging
from typing import Dict, Any, Optional


class GRLConfigManager:
    """
    Simple manager for GRL application configuration.
    Handles loading configuration settings from JSON file.
    """

    def __init__(self, config_file_path: str = "grl_config.json"):
        """
        Initialize the configuration manager.

        Args:
            config_file_path (str): Path to the configuration JSON file
        """
        self.config_file_path = config_file_path
        self.config = {}  # Store config data

        # Initialize with a null logger
        self.logger = logging.getLogger("NullLogger")
        self.logger.addHandler(logging.NullHandler())

        # Initialize attributes
        self.ip_address = None
        self.load_from_json = None
        self.project_name_with_time_stamp = None
        self.initial_wait = None
        self.log_filename = None
        self.default_log_mode = None
        self.max_connection_attempts = None
        self.connection_timeout = None
        self.api_timeout = None
        self.app_name = None
        self.app_path = None
        self.known_port = None

        # Load configuration when instantiated
        self.load_config()

    def set_logger(self, logger: logging.Logger) -> None:
        """
        Set the logger to be used by this class.

        Args:
            logger (logging.Logger): Logger instance to use
        """
        self.logger = logger
        self.logger.debug("Logger set for GRLConfigManager")

    def load_config(self) -> bool:
        """
        Load configuration from the JSON file.

        Returns:
            bool: True if config loaded successfully, False otherwise
        """
        try:
            with open(self.config_file_path, 'r') as config_file:
                self.config = json.load(config_file)

            # Load IP address
            self.ip_address = self.config.get("ip_address")

            # Load from JSON flag
            load_from_json = self.config.get("Load_from_json")
            if isinstance(load_from_json, str):
                self.load_from_json = load_from_json.lower() == "true"
            else:
                self.load_from_json = load_from_json

            # Project name with timestamp
            project_name_ts = self.config.get("project_name_with_time_stamp")
            if isinstance(project_name_ts, str):
                self.project_name_with_time_stamp = project_name_ts.lower() == "true"
            else:
                self.project_name_with_time_stamp = project_name_ts

            # Load common settings
            common = self.config.get("common", {})
            self.initial_wait = common.get("initial_wait")
            self.log_filename = common.get("log_filename")
            self.default_log_mode = common.get("default_log_mode")
            self.max_connection_attempts = common.get("max_connection_attempts")
            self.connection_timeout = common.get("connection_timeout")
            self.api_timeout = common.get("api_timeout")

            # Load application-specific settings
            default_app = self.config.get("default_app")
            if default_app and default_app in self.config.get("applications", {}):
                app_config = self.config["applications"][default_app]
                self.app_name = app_config.get("app_name")
                self.app_path = app_config.get("app_path")
                self.known_port = app_config.get("known_port")

                self.logger.debug(f"Loaded configuration for app '{default_app}'")

            return True

        except Exception as e:
            self.logger.error(f"Exception during config loading: {str(e)}")
            return False

    def get_app_config(self, app_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get configuration for a specific application.

        Args:
            app_name: Name of the application to get config for.
                     If None, uses the default app.

        Returns:
            Dict containing the application configuration, or empty dict if not found
        """
        if app_name is None:
            app_name = self.config.get("default_app")
            self.logger.debug(f"Using default app: {app_name}")

        if not app_name:
            self.logger.warning("No application name provided and no default app configured")
            return {}

        app_config = self.config.get("applications", {}).get(app_name, {})
        if app_config:
            self.logger.debug(f"Found configuration for app '{app_name}'")
        else:
            self.logger.warning(f"No configuration found for app '{app_name}'")

        return app_config