import random

import urequests
import utime


class LogLevel:
    DEBUG = 'debug'
    INFO = 'info'
    WARN = 'warn'
    ERROR = 'error'

    @staticmethod
    def values() -> list[str]:
        return [
            LogLevel.DEBUG,
            LogLevel.INFO,
            LogLevel.WARN,
            LogLevel.ERROR
        ]

    @staticmethod
    def validate_log_level(log_level: str) -> None:
        if log_level not in LogLevel.values():
            raise ValueError('Invalid log level given, allowed values are "debug", "info", "warn" and "error"')

    @staticmethod
    def get_relevant_log_levels(min_log_level: str) -> list[str]:
        LogLevel.validate_log_level(min_log_level)
        if min_log_level == LogLevel.DEBUG:
            return [LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARN, LogLevel.ERROR]
        elif min_log_level == LogLevel.INFO:
            return [LogLevel.INFO, LogLevel.WARN, LogLevel.ERROR]
        elif min_log_level == LogLevel.WARN:
            return [LogLevel.WARN, LogLevel.ERROR]
        else:
            return [LogLevel.ERROR]


class LogMessage:
    _id: str
    _timestamp_ns: str
    _message: str
    _log_level: str

    def __init__(self, timestamp_ns: str, message: str, log_level: str):
        LogLevel.validate_log_level(log_level)
        self._id = self.__generate_id()
        self._timestamp_ns = timestamp_ns
        self._message = message
        self._log_level = log_level

    @property
    def id(self):
        return self._id

    @property
    def timestamp_ns(self):
        return self._timestamp_ns

    @property
    def message(self):
        return self._message

    @property
    def log_level(self):
        return self._log_level

    @staticmethod
    def __generate_id():
        characters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        return ''.join(random.choice(characters) for _ in range(8))


class LogLabel:
    _key: str
    _value: str

    def __init__(self, key: str, value: str):
        self._key = key
        self._value = value

    @property
    def key(self):
        return self._key

    @property
    def value(self):
        return self._value


class Loki:
    _url: str
    _timeout: int
    _log_labels: list[LogLabel]
    _default_log_level: str
    _log_messages: list[LogMessage]
    _max_stack_size: int
    _min_push_log_level: str

    def __init__(self, url: str, log_labels: list[LogLabel] = None, default_log_level=LogLevel.INFO, timeout=5, max_stack_size=50, min_push_log_level=LogLevel.DEBUG):
        LogLevel.validate_log_level(min_push_log_level)
        self._url = url
        self._timeout = timeout
        self._log_labels = log_labels if log_labels is not None else []
        self._default_log_level = default_log_level
        self._log_messages = list()
        self._max_stack_size = max_stack_size
        self._min_push_log_level = min_push_log_level

    def log(self, message: str, log_level: str = None) -> None:
        if log_level is None:
            log_level = self._default_log_level
        LogLevel.validate_log_level(log_level)

        # Drop the log message if log level is below minimum push log level to avoid filling up the stack
        if log_level not in LogLevel.get_relevant_log_levels(self._min_push_log_level):
            return

        # Some Microcontrollers don't have nanoseconds support, thus, we take the seconds and append nine 0s to get the nanosecond timestamp
        timestamp_ns = f'{int(utime.time())}000000000'
        self._log_messages.append(LogMessage(timestamp_ns, message, log_level))

        # If the max stack size is exceeded the 'oldest' log is removed from the stack
        if len(self._log_messages) > self._max_stack_size:
            oldest_log_message = sorted(self._log_messages, key=lambda log_message: log_message.timestamp_ns, reverse=True).pop()
            self._log_messages.remove(oldest_log_message)

    def debug(self, message: str) -> None:
        self.log(message, LogLevel.DEBUG)

    def info(self, message: str) -> None:
        self.log(message, LogLevel.INFO)

    def warn(self, message: str) -> None:
        self.log(message, LogLevel.WARN)

    def error(self, message: str) -> None:
        self.log(message, LogLevel.ERROR)

    def __get_labels(self, log_level: str) -> dict:
        labels = {'level': log_level}
        labels.update({lbl.key: lbl.value for lbl in self._log_labels})

        return labels

    def __get_log_messages(self, log_level: str) -> (list[list[str, str]], list[str]):
        filtered_messages = list(filter(lambda log_message: log_message.log_level == log_level, self._log_messages))

        loki_messages = list([log_message.timestamp_ns, log_message.message] for log_message in filtered_messages)
        log_message_ids = [filtered_message.id for filtered_message in filtered_messages]

        return loki_messages, log_message_ids

    def __get_loki_streams_object(self) -> (list[dict], list[str]):
        loki_streams_object = list()
        collected_log_message_ids = list()

        for log_level in LogLevel.values():
            loki_messages, log_message_ids = self.__get_log_messages(log_level)
            if len(loki_messages) > 0:
                loki_streams_object.append(
                    {
                        'stream': self.__get_labels(log_level),
                        'values': loki_messages
                    }
                )
                collected_log_message_ids.extend(log_message_ids)

        return loki_streams_object, collected_log_message_ids

    def push_logs(self) -> None:
        # Only send logs if there are some
        if len(self._log_messages) == 0:
            return

        loki_streams_object, collected_log_message_ids = self.__get_loki_streams_object()
        request_body = {
            'streams': loki_streams_object
        }
        try:
            response = urequests.post(f'{self._url}/loki/api/v1/push', json=request_body, headers={'Content-Type': 'application/json'}, timeout=self._timeout)
            response_status_code = response.status_code
            response.close()
            if response_status_code == 204:
                # All successfully pushed log messages are removed from the stack
                pushed_log_messages = list(filter(lambda log_message: log_message.id in collected_log_message_ids, self._log_messages))
                for pushed_log_message in pushed_log_messages:
                    self._log_messages.remove(pushed_log_message)
        # Failures during log pushing should not affect the main application, thus ignore all errors
        except BaseException:
            pass
