import sys
import time
import unittest
from unittest.mock import Mock, patch

sys.modules['urequests'] = Mock()
sys.modules['utime'] = __import__('time')

from micropython_loki import Loki, LogLabel, LogLevel, LogMessage
from mocks import urequests_mock


class TestMicropythonLoki(unittest.TestCase):

    def setUp(self) -> None:
        self.loki = Loki('http://localhost:3100', [LogLabel('app', 'testapp'), LogLabel('version', '1.0.0')], max_stack_size=5)

    def test_calling_log_adds_log_messages_to_stack(self):
        self.loki.log('First DEBUG message - will be dropped due to exceeded max stack size', LogLevel.DEBUG)
        # Ensure first log message has another timestamp than the following by waiting for 1s
        time.sleep(1)
        self.loki.log('Testmessage DEBUG', LogLevel.DEBUG)
        self.loki.log('Testmessage INFO - default log level')
        self.loki.log('Testmessage INFO', LogLevel.INFO)
        self.loki.log('Testmessage WARN', LogLevel.WARN)
        self.loki.log('Testmessage ERROR', LogLevel.ERROR)

        self.assertEqual(5, len(self.loki._log_messages))

        # DEBUG
        debug_log_messages = list(filter(lambda log_message: log_message.log_level == LogLevel.DEBUG, self.loki._log_messages))
        self.assertEqual(1, len(debug_log_messages))
        for log_message in debug_log_messages:
            self.assertIsNotNone(log_message.id)
            self.assertIsNotNone(log_message.timestamp_ns)
            self.assertIn(log_message.message, ['Testmessage DEBUG'])

        # INFO
        info_log_messages = list(filter(lambda log_message: log_message.log_level == LogLevel.INFO, self.loki._log_messages))
        self.assertEqual(2, len(info_log_messages))
        for log_message in info_log_messages:
            self.assertIsNotNone(log_message.id)
            self.assertIsNotNone(log_message.timestamp_ns)
            self.assertIn(log_message.message, ['Testmessage INFO - default log level', 'Testmessage INFO'])

        # WARN
        warn_log_messages = list(filter(lambda log_message: log_message.log_level == LogLevel.WARN, self.loki._log_messages))
        self.assertEqual(1, len(warn_log_messages))
        for log_message in warn_log_messages:
            self.assertIsNotNone(log_message.id)
            self.assertIsNotNone(log_message.timestamp_ns)
            self.assertIn(log_message.message, ['Testmessage WARN'])

        # ERROR
        error_log_messages = list(filter(lambda log_message: log_message.log_level == LogLevel.ERROR, self.loki._log_messages))
        self.assertEqual(1, len(error_log_messages))
        for log_message in error_log_messages:
            self.assertIsNotNone(log_message.id)
            self.assertIsNotNone(log_message.timestamp_ns)
            self.assertIn(log_message.message, ['Testmessage ERROR'])

    def test_calling_push_logs_successfully_removes_send_logs_from_stack(self):
        with patch('urequests.post') as post_mock:
            post_mock.return_value.__enter__.return_value = urequests_mock.mock_post(204)

            self.loki._log_messages = [
                LogMessage('1667343504000000000', 'Testmessage DEBUG', LogLevel.DEBUG),
                LogMessage('1667343505000000000', 'Testmessage INFO - default log level', LogLevel.INFO)
            ]

            self.loki.push_logs()

            self.assertEqual(0, len(self.loki._log_messages))

    def test_calling_push_logs_failing_does_not_remove_logs_from_stack(self):
        with patch('urequests.post') as post_mock:
            post_mock.return_value.__enter__.return_value = urequests_mock.mock_post(503)

            self.loki._log_messages = [
                LogMessage('1667343504000000000', 'Testmessage DEBUG', LogLevel.DEBUG),
                LogMessage('1667343505000000000', 'Testmessage INFO - default log level', LogLevel.INFO)
            ]

            self.loki.push_logs()

            self.assertEqual(2, len(self.loki._log_messages))

    def test_request_body_matches_accepted_format(self):
        with patch('urequests.post') as post_mock:
            self.loki._log_messages = [
                LogMessage('1667343504000000000', 'Testmessage DEBUG', LogLevel.DEBUG),
                LogMessage('1667343505000000000', 'Testmessage INFO - default log level', LogLevel.INFO)
            ]

            self.loki.push_logs()

            expected_request_body = {
                'streams': [
                    {
                        'stream': {
                            'app': 'testapp',
                            'version': '1.0.0',
                            'level': 'debug'
                        },
                        'values': [
                            ['1667343504000000000', 'Testmessage DEBUG']
                        ]
                    },
                    {
                        'stream': {
                            'app': 'testapp',
                            'version': '1.0.0',
                            'level': 'info'
                        },
                        'values': [
                            ['1667343505000000000', 'Testmessage INFO - default log level']
                        ]
                    }
                ]
            }

            post_mock.assert_called_with('http://localhost:3100/loki/api/v1/push',
                                         json=expected_request_body,
                                         headers={'Content-Type': 'application/json'},
                                         timeout=5)

    def test_calling_push_logs_when_no_logs_are_available_no_api_call_is_performed(self):
        with patch('urequests.post') as post_mock:
            self.loki._log_messages = []

            self.loki.push_logs()

            post_mock.assert_not_called()
