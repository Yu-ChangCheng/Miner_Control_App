import requests
import time
import threading
import logging
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

class MinerControlApp:
    def __init__(self, miner_ips, max_workers=10, max_retries=3, log_file='miner_control.log'):
        """
        Initializes the MinerControlApp with the provided miner IPs, maximum number of worker threads,
        maximum number of retries for API requests, and the log file location.
        """
        self.miner_ips = miner_ips  # List of miner IP addresses
        self.base_url = 'http://127.0.0.1:5000/api'  # Base URL for API requests
        self.lock = threading.Lock()  # Lock for thread-safe operations
        self.miner_tokens = {}  # Cache for miner tokens and their TTLs (Time-To-Live)
        self.max_workers = max_workers  # Maximum number of worker threads
        self.max_retries = max_retries  # Maximum number of retries for API requests

        # Setup logging configuration
        logging.basicConfig(
            filename=log_file,
            level=logging.DEBUG,
            format='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger()

    def make_request(self, url, data, retries, re_login_on_unauthorized=False, ignore_errors=None):
        """
        Centralized method to make a POST request to the API with retry logic and specific error handling.

        Args:
            url (str): The API endpoint URL.
            data (dict): The JSON data to send in the POST request.
            retries (int): Number of times to retry the request on failure.
            re_login_on_unauthorized (bool): Whether to attempt re-login if unauthorized.
            ignore_errors (list): List of error messages to ignore during the request.

        Returns:
            response: The response object if the request is successful, or None if all retries fail.
        """
        if ignore_errors is None:
            ignore_errors = []

        for attempt in range(retries):
            try:
                response = requests.post(url, json=data, timeout=5)  # Increased timeout
                self.logger.debug(f"Response status code: {response.status_code}")

                # Handle successful response
                if response.status_code == 200:
                    return response
                
                # Handle specific errors that should be ignored such as the profile/ curtail is being set already
                response_json = response.json()
                error_message = response_json.get('message', '')
                if any(error in error_message for error in ignore_errors):
                    self.logger.info(f"Ignoring error: {error_message}. No retry will be performed.")
                    response.status_code = 100  # Custom status code to indicate ignored error
                    response._content = b"Ignoring error due to it is being set already"  # Modify the content
                    return response  # Exit early to avoid retrying

                # Handle unauthorized error with optional re-login
                if response.status_code == 401 and re_login_on_unauthorized:
                    self.logger.warning(f"Unauthorized request to {url}, attempting re-login.")
                    return 'unauthorized'

                # Handle other non-200 responses
                self.logger.warning(f"Failed request to {url}. Response: {response.text}")
                print(f"Failed request to {url}. Response: {response.text}")

            except requests.RequestException as e:
                self.logger.error(f"Error making request to {url}: {str(e)}. Attempt {attempt + 1} of {retries}. Retrying...")
                print(f"Error making request to {url}: {str(e)}. Attempt {attempt + 1} of {retries}. Retrying...")

            time.sleep(2 ** attempt)  # Exponential backoff
            
        self.logger.error(f"Failed to complete request to {url} after {retries} attempts.")
        return None

    def login(self, miner_ip):
        url = f'{self.base_url}/login'
        data = {'miner_ip': miner_ip}
        response = self.make_request(url, data, self.max_retries)
        
        if response:
            token_data = response.json()
            token = token_data.get('token')
            ttl = token_data.get('ttl')

            if token:
                with self.lock:
                    # Store even if ttl is missing
                    self.miner_tokens[miner_ip] = {'token': token, 'ttl': ttl}
                self.logger.info(f'Successfully logged in miner {miner_ip}')
                print(f'Successfully logged in miner {miner_ip}')
                return token
            else:
                self.logger.error(f"Login response for miner {miner_ip} did not contain a token.")
                print(f"Login response for miner {miner_ip} did not contain a token.")
                return None
        else:
            self.logger.error(f'Failed to log in miner {miner_ip} after {self.max_retries} attempts.')
            print(f'Failed to log in miner {miner_ip} after {self.max_retries} attempts.')
            return None
    
    def logout(self, miner_ip):
        """
        Logs out from a miner and removes its token from the cache.

        Args:
            miner_ip (str): The IP address of the miner.
        """
        url = f'{self.base_url}/logout'
        data = {'miner_ip': miner_ip}
        response = self.make_request(url, data, self.max_retries)
        if response:
            with self.lock:
                if miner_ip in self.miner_tokens:
                    del self.miner_tokens[miner_ip]
            self.logger.info(f'Successfully logged out miner {miner_ip}.')
            print(f'Successfully logged out miner {miner_ip}.')
        else:
            self.logger.error(f'Failed to log out miner {miner_ip} after {self.max_retries} attempts.')
            print(f'Failed to log out miner {miner_ip} after {self.max_retries} attempts.')

    def set_profile(self, miner_ip, token, profile):
        """
        Sets the operation profile of the miner (e.g., overclock, normal, underclock).

        Args:
            miner_ip (str): The IP address of the miner.
            token (str): The authentication token for the miner.
            profile (str): The desired profile to set.
        """
        url = f'{self.base_url}/profileset'
        data = {'token': token, 'profile': profile}
        response = self.make_request(url, data, self.max_retries, re_login_on_unauthorized=True, ignore_errors=["Miner is already in"])
        if response == 'unauthorized':
            self.logger.warning(f"Unauthorized token for miner {miner_ip}, attempting re-login...")
            print(f"Unauthorized token for miner {miner_ip}, attempting re-login...")
            token = self.login(miner_ip)
            if token:
                self.set_profile(miner_ip, token, profile)
        elif response:
            self.logger.info(f'Successfully set profile for miner {miner_ip} to {profile}.')
            print(f'Successfully set profile for miner {miner_ip} to {profile}.')
        else:
            self.logger.error(f'Failed to set profile for miner {miner_ip} after {self.max_retries} attempts.')
            print(f'Failed to set profile for miner {miner_ip} after {self.max_retries} attempts.')

    def set_curtail(self, miner_ip, token, mode):
        """
        Sets the curtailment mode of the miner (e.g., active, sleep).

        Args:
            miner_ip (str): The IP address of the miner.
            token (str): The authentication token for the miner.
            mode (str): The desired curtailment mode to set.
        """
        url = f'{self.base_url}/curtail'
        data = {'token': token, 'mode': mode}
        response = self.make_request(url, data, self.max_retries, re_login_on_unauthorized=True, ignore_errors=["Miner is already in"])
        if response == 'unauthorized':
            self.logger.warning(f"Unauthorized token for miner {miner_ip}, attempting re-login...")
            print(f"Unauthorized token for miner {miner_ip}, attempting re-login...")
            token = self.login(miner_ip)
            if token:
                self.set_curtail(miner_ip, token, mode)
        elif response:
            self.logger.info(f'Curtail mode for miner {miner_ip} set to {mode}.')
            print(f'Curtail mode for miner {miner_ip} set to {mode}.')
        else:
            self.logger.error(f'Failed to curtail miner {miner_ip} after {self.max_retries} attempts.')
            print(f'Failed to curtail miner {miner_ip} after {self.max_retries} attempts.')

    def determine_mode(self):
        """
        Determines the current operation mode and the next transition time based on the time of day.

        Returns:
            tuple: (profile, curtail_mode, next_transition) where profile is the operation profile, 
            curtail_mode is the curtailment mode, and next_transition is the datetime for the next mode transition.
        """
        current_hour = datetime.now(timezone.utc).hour
        if 0 <= current_hour < 6:
            next_transition = datetime.now(timezone.utc).replace(hour=6, minute=0, second=0, microsecond=0)
            return 'overclock', 'active', next_transition
        elif 6 <= current_hour < 12:
            next_transition = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
            return 'normal', 'active', next_transition
        elif 12 <= current_hour < 18:
            next_transition = datetime.now(timezone.utc).replace(hour=18, minute=0, second=0, microsecond=0)
            return 'underclock', 'active', next_transition
        else:
            next_transition = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            return 'normal', 'sleep', next_transition

    def process_miner(self, miner_ip):
        """
        Processes a miner by logging in, setting curtail mode, setting profile, and logging out.

        Args:
            miner_ip (str): The IP address of the miner.
        """

        # token_info = self.miner_tokens.get(miner_ip)
        # if not token_info or token_info['ttl'] <= datetime.utcnow():
        #     token = self.login(miner_ip)
        # else:
        #     token = token_info['token']
        try:
            token = self.login(miner_ip)
            if token:
                try:
                    profile, curtail_mode, _ = self.determine_mode()
                    self.set_curtail(miner_ip, token, curtail_mode)
                except Exception as e:
                    self.logger.error(f"Error setting curtail mode for {miner_ip}: {str(e)}")
                
                try:
                    self.set_profile(miner_ip, token, profile)
                except Exception as e:
                    self.logger.error(f"Error setting profile for {miner_ip}: {str(e)}")
                
                try:
                    self.logout(miner_ip)
                except Exception as e:
                    self.logger.error(f"Error logging out {miner_ip}: {str(e)}")
            else:
                self.logger.error(f"No token received for {miner_ip}, skipping further steps.")
        except Exception as e:
            self.logger.error(f"Error processing miner {miner_ip}: {str(e)}")

    def start(self, cycles=None):
        """
        Starts the application, processing all miners in cycles based on the time of day.
        """
        cycle_count = 0
        while True:
            profile, curtail_mode, next_transition = self.determine_mode()
            
            # Process miners concurrently using a thread pool
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                executor.map(self.process_miner, self.miner_ips)

            sleep_time = (next_transition - datetime.now(timezone.utc)).total_seconds()
            current_time_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            
            self.logger.info(f"Current time: {current_time_str}")
            print(f"Current time: {current_time_str}")
            
            self.logger.info(f"Completed one cycle. Sleeping until next transition in {sleep_time // 60} minutes...")
            print(f"Completed one cycle. Sleeping until next transition in {sleep_time // 60} minutes...")

            if cycles is not None:
                cycle_count += 1
                if cycle_count >= cycles:
                    break

            time.sleep(sleep_time)

if __name__ == "__main__":
    # Example IPs, replace with actual miner IPs
    miner_ips = ["192.168.0." + str(i) for i in range(1000)]
    app = MinerControlApp(miner_ips, max_workers=10, max_retries=3)
    app.start()
