# micropython-loki

[![GitHub Workflow Status](https://img.shields.io/github/workflow/status/olivergregorius/micropython_loki/Python%20Build?label=Python%20Build&logo=github)](https://github.com/olivergregorius/micropython_loki/actions/workflows/build.yml)
[![Python Versions](https://img.shields.io/pypi/pyversions/micropython-loki?label=Python)](https://pypi.org/project/micropython-loki/)
[![GitHub](https://img.shields.io/github/license/olivergregorius/micropython_loki?label=License)](https://github.com/olivergregorius/micropython_loki/blob/HEAD/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/micropython-loki?label=PyPI)](https://pypi.org/project/micropython-loki/)

## Introduction

Micropython library for sending logs to [Loki](https://grafana.com/oss/loki/)

## Installation

The library can be installed using [upip](https://docs.micropython.org/en/latest/reference/glossary.html#term-upip) or
[mip](https://docs.micropython.org/en/latest/reference/packages.html). Ensure that the device is connected to the network.

### Installation using upip (Micropython < 1.19)

```python
import upip
upip.install('micropython-loki')
```

### Installation using mip (Micropython >= 1.19)

```python
import mip
mip.install('github:olivergregorius/micropython_loki/micropython_loki.py')
```

## Usage

This library provides two methods for

1. adding log messages to the stack (`log`) and
2. pushing the logs to a Loki instance (`push_logs`).

**NOTE**: Each log message is applied with the current system's timestamp. Please be sure the RTC of the device is set correctly.

At first the Loki-instance must be initialized providing the Loki base-URL:

```python
from micropython_loki import Loki

loki = Loki('https://loki.example.org:3100')
```

The following additional arguments may be provided:

| Argument          | Description                                                                                                | Default         |
|-------------------|------------------------------------------------------------------------------------------------------------|-----------------|
| log_labels        | List of `LogLabel` instances. Each `LogLabel` is a key-value pair to enrich each log message with a label. | []              |
| default_log_level | Set the default log level. Instance of `LogLevel`.                                                         | `LogLevel.INFO` |
| timeout           | Timeout in seconds for calls against the Loki-API.                                                         | 5               |
| max_stack_size    | Maximum size of the log stack. If the stack size exceeds this value, the 'oldest' log message is dropped.  | 50              |

The following example creates a Loki-instance for calling the Loki-API at 'https://loki.example.org:3100', adding the labels 'app: important-app' and
'version: 1.0.0' to each log message, setting the default log level to 'INFO', setting the timeout to 5 seconds and setting the max stack size to 20.

```python
from micropython_loki import Loki, LogLabel, LogLevel

loki = Loki('https://loki.example.org:3100', [LogLabel('app', 'important-app'), LogLabel('version', '1.0.0')], LogLevel.INFO, 5, 20)
```

To add a log message to the log-stack the method `log` is called, it takes the arguments `message` (required) containing the log message and `log_level`
(optional) for setting the log level for that log message:

```python
...
loki.log('Calling do_something')
result = do_something()

if result == 1:
    loki.log('Something went wrong', LogLevel.WARN)
...
```

The example above adds one log message of level 'INFO' (as set by default during Loki instantiation, the LogLevel can be omitted in the `log` call) and one log
message of level 'WARN' (in case the value of result is 1).

To push the logs to Loki `push_logs` is called, this method takes no arguments:

```python
...
loki.push_logs()
...
```
