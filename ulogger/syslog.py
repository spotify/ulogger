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


import logging
import logging.handlers
import os
import sys


class SyslogHandlerBuilder:
    """Creates a Syslog handler based on current environment.

    Example usage:

        import logging
        from ulogger import syslog

        logger = logging.getLogger('')
        syslog_handler = syslog.get_handler('foo_program')
        logger.addHandler(syslog_handler)

    Args:
        progname (str): Name of program.
        address (:obj:`tuple(str, int)` or :obj:`str`, optional):
            Address to send logs as either (host, port) or filepath.
            Defaults to `/dev/log` on Linux, and `/var/run/syslog` on
            OS X. Builder will also pick up environment variables
            `SYSLOG_HOST` and `SYSLOG_PORT`, but will prefer explicitly
            given addresses.
        proto (:obj:`int`, optional): Protocol for the address if
            `(host, port)` is given. Options: `1` for TCP
            (`socket.SOCK_STREAM`), or `2` for UDP (`socket.SOCK_DGRAM`).
            Defaults to `2`.
        facility (:obj:`int`, optional): desired facility with which to
            log. Can be either an `int` or a constant from
            `logging.handlers.SysLogHandler`. Default is `16` (local0).
        fmt (:obj:`str`, optional): Desired log format if different than
            the default; uses the same formatting string options
            supported in the stdlib's `logging` module.
        datefmt (:obj:`str`, optional): Desired date format if different
            than the default; uses the same formatting string options
            supported in the stdlib's `logging` module.
    """

    FACILITY = logging.handlers.SysLogHandler.LOG_LOCAL0

    def __init__(self, progname, address=None, proto=None, facility=None,
                 fmt=None, datefmt=None):
        self.progname = progname
        self._environ = self._get_environ()
        self.fmt = fmt
        self.datefmt = datefmt
        self.facility = facility or self.FACILITY
        self.address = self._get_address(address)
        self.proto = proto or 2  # 2 = socket.SOCK_DGRAM

    def _get_environ(self):
        syslog_host = os.environ.get('SYSLOG_HOST', None)
        if syslog_host:
            return 'remote'
        if (sys.platform.startswith('darwin') and
                os.path.exists('/var/run/syslog')):
            return 'darwin'
        return 'default'

    def _get_address(self, address):
        if address:
            # python 2/3 compatibility
            try:
                basestring
            except NameError:
                basestring = str

            if not isinstance(address, basestring):
                if len(address) == 2:
                    if address[1] is None:
                        address = (address[0], logging.handlers.SYSLOG_UDP_PORT)
                    else:
                        address = (address[0], int(address[1]))
            return address

        address = {
            'default': '/dev/log',
            'darwin': '/var/run/syslog',
            'remote': (os.environ.get('SYSLOG_HOST'),
                       os.environ.get('SYSLOG_PORT',
                                      logging.handlers.SYSLOG_UDP_PORT))
        }[self._environ]
        if self._environ == 'remote':
            return (address[0], int(address[1]))
        return address

    def _get_osx_formatter(self):
        if not self.fmt:
            # MMM DD HH:MM:SS <host> <progname> (<PID>): <msg>
            # ex: Aug 25 13:00:51 foo.example.com bar (16911): hello
            self.fmt = self.progname + ' (%(process)d): %(message)s'
        return logging.Formatter(fmt=self.fmt)

    def _get_default_formatter(self):
        if not self.fmt:
            # e.g. 2017-08-25T14:47:44.968+00:00 <host> <progname>[<PID>]: <msg>
            prefix = '%(asctime)s.%(msecs)03dZ '
            suffix = ' (%(process)d): %(message)s'

            self.fmt = prefix + self.progname + suffix

        if not self.datefmt:
            self.datefmt = '%Y-%m-%dT%H:%M:%S'
        return logging.Formatter(fmt=self.fmt, datefmt=self.datefmt)

    def get_formatter(self):
        if self._environ == 'darwin':
            formatter = self._get_osx_formatter()
        else:
            formatter = self._get_default_formatter()
        return formatter

    def get_handler(self):
        handler = logging.handlers.SysLogHandler(
            address=self.address, facility=self.facility, socktype=self.proto)
        formatter = self.get_formatter()
        handler.setFormatter(formatter)
        return handler


def get_handler(progname, address=None, proto=None, facility=None,
                fmt=None, datefmt=None, **_):
    """Helper function to create a Syslog handler.

    See `ulogger.syslog.SyslogHandlerBuilder` for arguments and
    supported keyword arguments.

    Returns:
        (obj): Instance of `logging.SysLogHandler`
    """
    builder = SyslogHandlerBuilder(
        progname, address=address, proto=proto, facility=facility,
        fmt=fmt, datefmt=datefmt)
    return builder.get_handler()
