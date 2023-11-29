# ulogger

[![Build Status](https://github.com/spotify/ulogger/actions/workflows/main.yml/badge.svg)](https://github.com/spotify/ulogger/actions/workflows/main.yml) [![Test Coverage](https://codecov.io/github/spotify/ulogger/branch/master/graph/badge.svg)](https://codecov.io/github/spotify/ulogger)

A micro Python logging library.

Supported handlers:

* stream (stdout)
* syslog
* [stackdriver](https://cloud.google.com/logging/) (_optional_)

## Requirements

* Python 3.7. Tests also pass on Python 3.8.  PyPy support has been removed due to upstream issues with the grpcio module.
* Support for Linux & OS X

## To Use

    ```sh
    (env) $ pip install ulogger
    # To use the stackdriver handler, you need to specify an extra dependency:
    (env) $ pip install "ulogger[stackdriver]"
    ```

    ```python
    import logging
    from ulogger import setup_logging

    # one handler
    setup_logging('my_program', 'INFO', ['syslog'])

    # multiple handlers
    setup_logging('my_program', 'INFO', ['syslog', 'stream'])

    # use a different logging facility for syslog (default 16/LOG_LOCAL0)
    setup_logging('my_program', 'INFO', ['syslog'], facility=1)
    setup_logging('my_program', 'INFO', ['syslog'], facility=logging.handlers.SysLogHandler.LOG_USER)

    # then log messages normally
    logging.info('ohai')
    ```

To just setup a specific handler, e.g. Syslog:

    ```python
    import logging
    from ulogger import syslog

    logger = logging.getLogger('my_logger')
    handler = syslog.get_handler('my_program')
    logger.addHandler(handler)
    ```

To setup a Syslog handler with a specific address:

    ```python
    import logging
    from ulogger import syslog

    logger = logging.getLogger('my_logger')

    syslog_addr = ('10.99.0.1', 9514)  # (host, port) tuple
    # if just a host is given, the default port 514 is used
    syslog_addr = ('localhost', None)  # (host, port)
    # filepath is supported
    syslog_addr = '/dev/log'

    handler = syslog.get_handler('my_program', address=syslog_addr)

    # env vars are also supported, but will be overwritten if `address` is explicitly given
    os.environ['SYSLOG_HOST'] = 'localhost'
    os.environ['SYSLOG_PORT'] = 325
    handler = syslog.get_handler('my_program')

    # TCP & UDP are supported
    proto = 1  # TCP
    proto = socket.SOCK_STREAM  # TCP
    proto = 2  # UDP - default
    proto = socket.SOCK_DGRAM  #  UDP - default

    handler = syslog.get_handler('my_program', address=syslog_addr, proto=proto)
    logger.addHandler(handler)
    ```

### Formatting

#### Default

The default date format for all handlers is the following: `'%Y-%m-%dT%H:%M:%S'` (example `2017-11-02T09:51:33.792`).

The default log format is slightly different depending on the handler you select:

##### Stream Handler Log Format

    ```python
    '%(asctime)s.%(msecs)03dZ <PROGNAME> (%(process)d) %(levelname)s: %(message)s'
    ```

Example:

    ```text
    2017-11-02T09:51:33.792Z my_awesome_program (63079) INFO: Beginning awesome program v3.
    ```

##### Syslog Handler Log Format on Linux

    ```python
    '%(asctime)s.%(msecs)03dZ <PROGNAME> (%(process)d): %(message)s'
    ```

Example:

    ```text
    2017-11-02T09:51:33.792Z my_awesome_program (63079): Beginning awesome program v3.
    ```

##### Syslog Handler Log Format on OS X

    ```python
    '<PROGNAME> (%(process)d): %(message)s'
    ```

Example:

    ```text
    Aug 25 13:00:51 my-host.example.net my_awesome_program (63079): Beginning awesome program v3.
    ```

**NOTE**: Default syslog on OS X appends the date and hostname to the log record.

##### Stackdriver Handler Log Format

    ```python
    '%(asctime)s.%(msecs)03d <HOST> <PROGNAME> (%(process)d): %(message)s'
    ```

Example:

    ```text
    2017-11-02T19:00:55.850 my-gcp-host my_awesome_program (63079): Beginning awesome program v3"
    ```

#### Custom

To add your custom log and/or date formatter:

    ```python
    import logging
    from ulogger import setup_logging

    log_fmt = '%(created)f %(levelno)d %(message)s'
    log_date_fmt = '%Y-%m-%dT%H:%M:%S'

    setup_logging('my_program', 'INFO', ['syslog'], log_fmt, log_date_fmt)
    ```

## Development

For development and running tests, your system must have all supported versions of Python installed. We suggest using [pyenv](https://github.com/yyuu/pyenv).

### Setup

    ```sh
    $ git clone git@github.com:spotify/ulogger.git && cd ulogger
    # make a virtualenv
    (env) $ pip install -r dev-requirements.txt
    ```

### Running tests

To run the entire test suite:

    ```sh
    # outside of the virtualenv
    # if tox is not yet installed
    $ pip install tox
    $ tox
    ```

If you want to run the test suite for a specific version of Python:

    ```sh
    # outside of the virtualenv
    $ tox -e py37
    ```

To run an individual test, call `pytest` directly:

    ```sh
    # inside virtualenv
    (env) $ pytest tests/test_syslog.py
    ```

## Code of Conduct

This project adheres to the [Open Code of Conduct][code-of-conduct]. By participating, you are expected to honor this code.

[code-of-conduct]: https://github.com/spotify/code-of-conduct/blob/master/code-of-conduct.md
