"""
Web application controller for GRL API.
Handles launching, monitoring, and interacting with the GRL application.
"""

import os
import time
import logging
import subprocess
import requests
import socket
from typing import Optional


class WebAppController:
    """
    Controller for launching and interacting with web applications.
    Manages the application process and connectivity.
    """

    def __init__(self, app_path: str, known_port: Optional[int] = None,
                 max_connection_attempts: int = 3, connection_timeout: int = 30):
        self.app_path = app_path
        self.known_port = known_port
        self.max_connection_attempts = max_connection_attempts
        self.connection_timeout = connection_timeout

        self.process = None
        self.web_url = f"http://localhost:{self.known_port}" if self.known_port else None

        self.logger = logging.getLogger("WebAppController")
        self.logger.addHandler(logging.NullHandler())

    def set_logger(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.logger.debug("Logger set for WebAppController")

    def _check_port_in_use(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("localhost", port))
                return False
            except socket.error:
                return True

    def _check_application_running(self) -> bool:
        if not self.known_port:
            self.logger.warning("Cannot check application status without a known port.")
            return False

        if not self._check_port_in_use(self.known_port):
            self.logger.debug(f"Port {self.known_port} is free.")
            return False

        endpoints = ["/api/healthcheck", "/", "/api/status"]
        for endpoint in endpoints:
            try:
                response = requests.get(f"{self.web_url}{endpoint}", timeout=2)
                self.logger.info(f"Application detected on port {self.known_port} (status {response.status_code} at {endpoint})")
                return True
            except requests.exceptions.RequestException:
                continue

        self.logger.debug(f"Port {self.known_port} occupied but no valid application detected.")
        return False

    def _launch_process(self) -> bool:
        if self._check_application_running():
            self.logger.info("Application is already running.")
            return True

        if self.process and self.process.poll() is None:
            self.logger.info("Process already active.")
            return True

        if not os.path.exists(self.app_path):
            self.logger.error(f"Application path not found: {self.app_path}")
            return False

        try:
            self.logger.debug(f"Launching application: {self.app_path}")
            self.process = subprocess.Popen([self.app_path])

            if self.process.poll() is None:
                self.logger.info(f"Successfully launched {os.path.basename(self.app_path)} (PID {self.process.pid})")
                return True
            else:
                self.logger.error(f"Process terminated immediately (exit code {self.process.returncode})")
                return False

        except Exception as e:
            self.logger.error(f"Failed to launch application: {repr(e)}")
            return False

    def start_and_get_url(self, initial_wait: int = 10) -> Optional[str]:
        if self._check_application_running():
            self.logger.info(f"Using existing application at {self.web_url}")
            return self.web_url

        if not self._launch_process():
            return None

        self.logger.info(f"Waiting {initial_wait} seconds for initialization...")
        time.sleep(initial_wait)

        if not self.web_url:
            self.logger.error("Known port not specified. Cannot determine web URL.")
            return None

        self.logger.info(f"Attempting to connect to web server at {self.web_url} (timeout {self.connection_timeout}s)")
        start_time = time.time()

        endpoints = ["/api/healthcheck", "/", "/api/status"]

        for attempt in range(1, self.max_connection_attempts + 1):
            if time.time() - start_time > self.connection_timeout:
                self.logger.error(f"Connection timeout after {self.connection_timeout} seconds.")
                return None

            self.logger.debug(f"Attempt {attempt}/{self.max_connection_attempts} to {self.web_url}")

            for endpoint in endpoints:
                try:
                    response = requests.get(f"{self.web_url}{endpoint}", timeout=5)
                    self.logger.info(f"Connected to {self.web_url} (status {response.status_code} at {endpoint})")
                    return self.web_url
                except requests.exceptions.RequestException:
                    continue

            time.sleep(2)

        self.logger.error("Failed to connect to the web server after multiple attempts.")
        return None

    def stop_process(self) -> bool:
        if self.process and self.process.poll() is None:
            try:
                self.logger.info("Stopping application process...")
                self.process.terminate()

                for _ in range(5):
                    if self.process.poll() is not None:
                        self.logger.info(f"Process terminated (exit code {self.process.returncode})")
                        return True
                    time.sleep(1)

                self.logger.warning("Force killing unresponsive process...")
                self.process.kill()
                self.process.wait()
                self.logger.info("Process killed successfully.")
                return True

            except Exception as e:
                self.logger.error(f"Error stopping process: {repr(e)}")
                return False
        else:
            self.logger.debug("No active process found.")
            return True

    def is_running(self) -> bool:
        return (self.process and self.process.poll() is None) or self._check_application_running()

    def __del__(self):
        try:
            self.stop_process()
        except Exception:
            pass
