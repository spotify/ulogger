# -*- coding: utf-8 -*-
#
# Copyright 2017 Spotify AB
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from __future__ import absolute_import

from importlib import import_module
import logging

from ulogger import exceptions


def _setup_default_handler(progname, fmt=None, datefmt=None, **_):
    """Create a Stream handler (default handler).

    Args:
        progname (str): Name of program.
        fmt (:obj:`str`, optional): Desired log format if different than
            the default; uses the same formatting string options
            supported in the stdlib's `logging` module.
        datefmt (:obj:`str`, optional): Desired date format if different
            than the default; uses the same formatting string options
            supported in the stdlib's `logging` module.

    Returns:
        (obj): Instance of `logging.StreamHandler`
    """
    handler = logging.StreamHandler()

    if not fmt:
        # ex: 2017-08-26T14:47:44.968+00:00 <progname> (<PID>) INFO: <msg>
        fmt_prefix = '%(asctime)s.%(msecs)03dZ '
        fmt_suffix = ' (%(process)d) %(levelname)s: ' + '%(message)s'
        fmt = fmt_prefix + progname + fmt_suffix
    if not datefmt:
        datefmt = '%Y-%m-%dT%H:%M:%S'

    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)
    handler.setFormatter(formatter)
    return handler


def setup_logging(progname, level, handlers, **kwargs):
    """Setup logging to stdout (stream), syslog, or stackdriver.

    Attaches handler(s) and sets log level to the root logger.

    Example usage:

        import logging
        from ulogger import setup_logging

        setup_logging('my_awesome_program', 'INFO', ['stream'])

        logging.info('ohai')

    Args:
        progname (str): Name of program.
        level (str): Threshold for when to log.
        handlers (list): Desired handlers, default 'stream',
            supported: 'syslog', 'stackdriver', 'stream'.
        **kwargs (optional): Keyword arguments to pass to handlers. See
            handler documentation for more information on available
            kwargs.
    """
    for h in handlers:
        if h == 'stream':
            handler = _setup_default_handler(progname, **kwargs)
        else:
            handler_module_path = 'ulogger.{}'.format(h)
            try:
                handler_module = import_module(
                    handler_module_path, package='ulogger')
            except ImportError:
                msg = 'Unsupported log handler: "{}".'.format(h)
                raise exceptions.ULoggerError(msg)

            try:
                get_handler = getattr(handler_module, 'get_handler')
            except AttributeError:
                msg = '"get_handler" function not implemented for "{}".'
                raise exceptions.ULoggerError(msg.format(h))

            handler = get_handler(progname, **kwargs)
        logging.getLogger('').addHandler(handler)

    level = logging.getLevelName(level)
    logging.getLogger('').setLevel(level)
