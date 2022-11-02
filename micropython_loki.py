from enum import Enum
from uuid import UUID, uuid4

import urequests
import utime


class LogLevel(Enum):
    DEBUG = 'debug'
    INFO = 'info'
    WARN = 'warn'
    ERROR = 'error'


class LogMessage:
    _id: UUID
    _timestamp_ns: str
    _message: str
    _log_level: LogLevel

    def __init__(self, timestamp_ns: str, message: str, log_level: LogLevel):
        self._id = uuid4()
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
    _default_log_level: LogLevel
    _log_messages: list[LogMessage]
    _max_stack_size: int

    def __init__(self, url: str, log_labels: list[LogLabel] = None, default_log_level=LogLevel.INFO, timeout=5, max_stack_size=50):
        self._url = url
        self._timeout = timeout
        self._log_labels = log_labels if log_labels is not None else []
        self._default_log_level = default_log_level
        self._log_messages = list()
        self._max_stack_size = max_stack_size

    def log(self, message: str, log_level: LogLevel = None) -> None:
        if log_level is None:
            log_level = self._default_log_level

        # Some Microcontrollers don't have nanoseconds support, thus, we take the seconds and append nine 0s to get the nanosecond timestamp
        timestamp_ns = f'{int(utime.time())}000000000'
        self._log_messages.append(LogMessage(timestamp_ns, message, log_level))

        # If the max stack size is exceeded the 'oldest' log is removed from the stack
        if len(self._log_messages) > self._max_stack_size:
            oldest_log_message = sorted(self._log_messages, key=lambda log_message: log_message.timestamp_ns, reverse=True).pop()
            self._log_messages.remove(oldest_log_message)

    def __get_labels(self, log_level: LogLevel) -> dict:
        labels = {'level': log_level.value}
        labels.update({lbl.key: lbl.value for lbl in self._log_labels})

        return labels

    def __get_log_messages(self, log_level: LogLevel) -> (list[list[str, str]], list[UUID]):
        filtered_messages = list(filter(lambda log_message: log_message.log_level == log_level, self._log_messages))

        loki_messages = list([log_message.timestamp_ns, log_message.message] for log_message in filtered_messages)
        log_message_ids = [filtered_message.id for filtered_message in filtered_messages]

        return loki_messages, log_message_ids

    def __get_loki_streams_object(self) -> (list[dict], list[UUID]):
        loki_streams_object = list()
        collected_log_message_ids = list()

        for log_level in LogLevel:
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
            with urequests.post(f'{self._url}/loki/api/v1/push', json=request_body, headers={'Content-Type': 'application/json'}, timeout=self._timeout) as response:
                if response.status_code == 204:
                    # All successfully pushed log messages are removed from the stack
                    pushed_log_messages = list(filter(lambda log_message: log_message.id in collected_log_message_ids, self._log_messages))
                    for pushed_log_message in pushed_log_messages:
                        self._log_messages.remove(pushed_log_message)
        # Failures during log pushing should not affect the main application, thus ignore all errors
        except BaseException:
            pass
