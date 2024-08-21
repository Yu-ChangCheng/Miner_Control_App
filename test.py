import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone
from miner_control_app import MinerControlApp
import requests

class TestMinerControlApp(unittest.TestCase):

    def setUp(self):
        """Set up the test environment."""
        self.miner_ips = [f'192.168.0.{i}' for i in range(1000)]
        self.app = MinerControlApp(self.miner_ips, max_workers=10, max_retries=3)

    @patch('requests.post')
    def test_login_successful(self, mock_post):
        """Test a successful login."""
        mock_post.return_value = self._mock_response(200, {'token': 'test_token', 'ttl': (datetime.utcnow() + timedelta(minutes=1)).isoformat()})
        token = self.app.login('192.168.0.1')
        
        self.assertEqual(token, 'test_token')
        self.assertIn('192.168.0.1', self.app.miner_tokens)
        self.assertEqual(self.app.miner_tokens['192.168.0.1']['token'], 'test_token')

    @patch('requests.post')
    def test_login_failed(self, mock_post):
        """Test a failed login."""
        mock_post.return_value = self._mock_response(401)
        token = self.app.login('192.168.0.1')
        
        self.assertIsNone(token)
        self.assertNotIn('192.168.0.1', self.app.miner_tokens)

    @patch('requests.post')
    def test_logout_successful(self, mock_post):
        """Test a successful logout."""
        self.app.miner_tokens['192.168.0.1'] = {'token': 'test_token', 'ttl': datetime.utcnow() + timedelta(minutes=1)}
        mock_post.return_value = self._mock_response(200)
        
        self.app.logout('192.168.0.1')
        self.assertNotIn('192.168.0.1', self.app.miner_tokens)

    @patch('requests.post')
    def test_set_profile_success(self, mock_post):
        """Test setting a profile successfully."""
        mock_post.return_value = self._mock_response(200)
        self.app.set_profile('192.168.0.1', 'test_token', 'normal')
        
        mock_post.assert_called_once_with(f'{self.app.base_url}/profileset', json={'token': 'test_token', 'profile': 'normal'}, timeout=5)

    @patch('requests.post')
    def test_set_profile_already_set(self, mock_post):
        """Test setting a profile that is already set (should ignore)."""
        mock_post.return_value = self._mock_response(400, {'message': 'Miner is already in normal profile.'})
        with patch('builtins.print') as mocked_print:
            self.app.set_profile('192.168.0.1', 'test_token', 'normal')
        
        mocked_print.assert_any_call('Successfully set profile for miner 192.168.0.1 to normal.')

    @patch('requests.post')
    def test_set_curtail_success(self, mock_post):
        """Test setting curtail successfully."""
        mock_post.return_value = self._mock_response(200)
        self.app.set_curtail('192.168.0.1', 'test_token', 'active')
        
        mock_post.assert_called_once_with(f'{self.app.base_url}/curtail', json={'token': 'test_token', 'mode': 'active'}, timeout=5)

    @patch('requests.post')
    def test_set_curtail_already_set(self, mock_post):
        """Test setting curtail that is already set (should ignore)."""
        mock_post.return_value = self._mock_response(400, {'message': 'Miner is already in active mode.'})
        with patch('builtins.print') as mocked_print:
            self.app.set_curtail('192.168.0.1', 'test_token', 'active')
        
        mocked_print.assert_any_call('Curtail mode for miner 192.168.0.1 set to active.')

    @patch('miner_control_app.datetime')
    def test_determine_mode(self, mock_datetime):
        """Test the determine_mode method for different times of the day."""
        test_cases = [
            (datetime(2024, 1, 1, 5, 0, 0, tzinfo=timezone.utc), 'overclock', 'active'),
            (datetime(2024, 1, 1, 7, 0, 0, tzinfo=timezone.utc), 'normal', 'active'),
            (datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc), 'underclock', 'active'),
            (datetime(2024, 1, 1, 20, 0, 0, tzinfo=timezone.utc), 'normal', 'sleep')
        ]
        
        for current_time, expected_profile, expected_curtail_mode in test_cases:
            mock_datetime.now.return_value = current_time
            profile, curtail_mode, _ = self.app.determine_mode()
            self.assertEqual(profile, expected_profile)
            self.assertEqual(curtail_mode, expected_curtail_mode)

    @patch('requests.post')
    def test_login_network_failure(self, mock_post):
        """Test login failure due to network issues."""
        mock_post.side_effect = requests.exceptions.RequestException("Network Error")
        token = self.app.login('192.168.0.1')
        self.assertIsNone(token)

    @patch('requests.post')
    def test_process_miner_with_exceptions(self, mock_post):
        """Test process_miner with simulated exceptions in curtail, profile, and logout."""
        mock_post.return_value = self._mock_response(200, {'token': 'test_token', 'ttl': (datetime.utcnow() + timedelta(minutes=1)).isoformat()})
        
        with patch.object(self.app, 'set_curtail', side_effect=Exception("Curtail Error")), \
             patch.object(self.app, 'set_profile', side_effect=Exception("Profile Error")), \
             patch.object(self.app, 'logout', side_effect=Exception("Logout Error")):
            
            self.app.process_miner('192.168.0.1')

    @patch('requests.post')
    def test_make_request_retry_on_failure(self, mock_post):
        """Test retries on failure with exponential backoff."""
        mock_post.side_effect = [requests.exceptions.RequestException("Network Error"), self._mock_response(200)]
        response = self.app.make_request('/login', {'miner_ip': '192.168.0.1'}, retries=3)
        self.assertEqual(response.status_code, 200)

    @patch('requests.post')
    def test_make_request_unauthorized(self, mock_post):
        """Test an unauthorized POST request that triggers re-login."""
        mock_post.return_value = self._mock_response(401, {'message': 'Unauthorized'})
        response = self.app.make_request('/login', {'miner_ip': '192.168.0.1'}, retries=3, re_login_on_unauthorized=True)
        self.assertEqual(response, 'unauthorized')

    @patch('requests.post')
    def test_login_no_ttl(self, mock_post):
        """Test login response without a ttl."""
        mock_post.return_value = self._mock_response(200, {'token': 'test_token'})
        token = self.app.login('192.168.0.1')
        
        self.assertIn('192.168.0.1', self.app.miner_tokens)
        self.assertEqual(token, 'test_token')
        self.assertIsNone(self.app.miner_tokens['192.168.0.1']['ttl'])

    @patch('requests.post')
    def test_logout_nonexistent_miner(self, mock_post):
        """Test logout for a miner not in miner_tokens."""
        mock_post.return_value = self._mock_response(200)
        self.app.logout('192.168.0.1')
        self.assertNotIn('192.168.0.1', self.app.miner_tokens)

    @patch('requests.post')
    def test_set_profile_error_handling(self, mock_post):
        """Test set_profile with an error response."""
        mock_post.return_value = self._mock_response(500, {'message': 'Internal Server Error'})
        with self.assertLogs(self.app.logger, level='ERROR') as log:
            self.app.set_profile('192.168.0.1', 'test_token', 'normal')
        self.assertIn('Failed to set profile', log.output[-1])

    @patch('requests.post')
    def test_login_response_missing_token(self, mock_post):
        """Test login when the response does not contain a token."""
        mock_post.return_value = self._mock_response(200, {'ttl': (datetime.utcnow() + timedelta(minutes=1)).isoformat()})
        with self.assertLogs(self.app.logger, level='ERROR') as log:
            token = self.app.login('192.168.0.1')
        self.assertIsNone(token)
        self.assertIn('Login response for miner 192.168.0.1 did not contain a token.', log.output[0])

    @patch('miner_control_app.MinerControlApp.set_profile')
    @patch('miner_control_app.MinerControlApp.login')
    @patch('miner_control_app.MinerControlApp.determine_mode')
    @patch('miner_control_app.MinerControlApp.set_curtail')
    @patch('miner_control_app.MinerControlApp.logout')
    def test_process_miner_set_profile_exception(self, mock_logout, mock_set_curtail, mock_determine_mode, mock_login, mock_set_profile):
        """Test process_miner when an exception occurs during set_profile."""
        mock_login.return_value = 'test_token'
        mock_determine_mode.return_value = ('normal', 'active', datetime.utcnow() + timedelta(hours=1))
        mock_set_profile.side_effect = Exception("Profile Error")
        
        with self.assertLogs(self.app.logger, level='ERROR') as log:
            self.app.process_miner('192.168.0.1')
        self.assertIn("Error setting profile for 192.168.0.1: Profile Error", log.output[-1])

    @patch('miner_control_app.MinerControlApp.login')
    @patch('miner_control_app.MinerControlApp.make_request')
    def test_set_profile_unauthorized_relogin_success(self, mock_make_request, mock_login):
        """Test set_profile where unauthorized triggers a re-login and succeeds."""
        mock_make_request.side_effect = ['unauthorized', self._mock_response(200)]
        mock_login.return_value = 'new_token'
        
        self.app.set_profile('192.168.0.1', 'expired_token', 'normal')
        
        mock_login.assert_called_once_with('192.168.0.1')
        self.assertEqual(mock_make_request.call_count, 2)
        mock_make_request.assert_called_with(
            f'{self.app.base_url}/profileset',
            {'token': 'new_token', 'profile': 'normal'},
            3,
            re_login_on_unauthorized=True,
            ignore_errors=["Miner is already in"]
        )

    @patch('miner_control_app.MinerControlApp.login')
    @patch('miner_control_app.MinerControlApp.make_request')
    def test_set_profile_unauthorized_relogin_failure(self, mock_make_request, mock_login):
        """Test set_profile where unauthorized triggers a re-login but login fails."""
        mock_make_request.side_effect = ['unauthorized']
        mock_login.return_value = None
        
        with self.assertLogs(self.app.logger, level='WARNING') as log:
            self.app.set_profile('192.168.0.1', 'expired_token', 'normal')
        
        mock_login.assert_called_once_with('192.168.0.1')
        self.assertEqual(mock_make_request.call_count, 1)
        self.assertIn("Unauthorized token for miner 192.168.0.1, attempting re-login...", log.output[0])

    @patch('miner_control_app.MinerControlApp.make_request')
    def test_logout_failure(self, mock_make_request):
        """Test logout failure after maximum retries."""
        mock_make_request.return_value = None
        self.app.miner_tokens['192.168.0.1'] = {'token': 'test_token', 'ttl': datetime.utcnow() + timedelta(minutes=1)}
        
        with self.assertLogs(self.app.logger, level='ERROR') as log:
            self.app.logout('192.168.0.1')
        self.assertIn(f'Failed to log out miner 192.168.0.1 after {self.app.max_retries} attempts.', log.output[-1])

    @patch('miner_control_app.MinerControlApp.make_request')
    @patch('miner_control_app.MinerControlApp.login')
    def test_set_curtail_unauthorized_relogin_success(self, mock_login, mock_make_request):
        """Test set_curtail where unauthorized triggers a re-login and succeeds."""
        mock_make_request.side_effect = ['unauthorized', self._mock_response(200)]
        mock_login.return_value = 'new_token'
        
        self.app.set_curtail('192.168.0.1', 'old_token', 'active')
        
        mock_login.assert_called_once_with('192.168.0.1')
        mock_make_request.assert_any_call(
            f'{self.app.base_url}/curtail',
            {'token': 'new_token', 'mode': 'active'},
            self.app.max_retries,
            re_login_on_unauthorized=True,
            ignore_errors=["Miner is already in"]
        )

    @patch('miner_control_app.MinerControlApp.make_request')
    def test_set_curtail_failure_after_retries(self, mock_make_request):
        """Test set_curtail failure after max retries."""
        mock_make_request.return_value = None
        
        with self.assertLogs(self.app.logger, level='ERROR') as log, patch('builtins.print') as mocked_print:
            self.app.set_curtail('192.168.0.1', 'test_token', 'active')
            
            mocked_print.assert_called_with('Failed to curtail miner 192.168.0.1 after 3 attempts.')
            self.assertIn('Failed to curtail miner 192.168.0.1 after 3 attempts.', log.output[-1])

    @patch('miner_control_app.MinerControlApp.login')
    def test_process_miner_no_token_skips_steps(self, mock_login):
        """Test process_miner skips further steps when no token is received."""
        mock_login.return_value = None
        
        with self.assertLogs(self.app.logger, level='ERROR') as log:
            self.app.process_miner('192.168.0.1')
        
        self.assertIn('No token received for 192.168.0.1, skipping further steps.', log.output[-1])
    
    @patch('miner_control_app.MinerControlApp.login')
    def test_process_miner_top_level_exception(self, mock_login):
        """Test process_miner handles a top-level exception properly."""
        
        # Simulate a successful login
        mock_login.return_value = 'test_token'
        
        # Force a top-level exception by mocking an attribute access that raises an exception
        with patch.object(self.app, 'login', side_effect=Exception("Top Level Exception")):
            with self.assertLogs(self.app.logger, level='ERROR') as log:
                self.app.process_miner('192.168.0.1')

                # Print all log messages for debugging
                for message in log.output:
                    print(f"LOG: {message}")
                
                # Ensure the top-level error message was logged
                self.assertTrue(any("Error processing miner 192.168.0.1: Top Level Exception" in message for message in log.output))

    @patch('miner_control_app.time.sleep', side_effect=Exception("Stop loop"))
    @patch('miner_control_app.MinerControlApp.process_miner')
    @patch('miner_control_app.MinerControlApp.determine_mode')
    @patch('miner_control_app.datetime')
    def test_start_method_single_cycle(self, mock_datetime, mock_determine_mode, mock_process_miner, mock_sleep):
        """Test the start method to ensure it processes miners and sleeps correctly in one cycle."""
        mock_datetime.now.return_value = datetime(2024, 1, 1, 5, 0, 0, tzinfo=timezone.utc)
        mock_determine_mode.return_value = ('normal', 'active', datetime(2024, 1, 1, 6, 0, 0, tzinfo=timezone.utc))

        miner_ips = ["192.168.0.1", "192.168.0.2"]
        app = MinerControlApp(miner_ips, max_workers=2, max_retries=3)

        app.start(cycles=1)  # Run only one cycle for testing

        mock_process_miner.assert_any_call('192.168.0.1')
        mock_process_miner.assert_any_call('192.168.0.2')
        self.assertEqual(mock_process_miner.call_count, 2)

        print("[TEST START METHOD] Passed - Single cycle of the start method executed and verified.")



    def _mock_response(self, status_code, json_data=None):
        """Helper method to create a mock response with a given status code and optional JSON data."""
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        if json_data:
            mock_resp.json.return_value = json_data
        return mock_resp

if __name__ == '__main__':
    unittest.main()
