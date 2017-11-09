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

import pytest

from ulogger import syslog


EXP_DATE_FORMAT = '%Y-%m-%dT%H:%M:%S'
SYSLOG_DEFAULT_FMT = '%(asctime)s.%(msecs)03dZ foo (%(process)d): %(message)s'
SYSLOG_OSX_FMT = 'foo (%(process)d): %(message)s'
REMOTE_ENV = {
    'SYSLOG_HOST': 'localhost',
    'SYSLOG_PORT': '12345'
}


def test_get_handler(mocker, monkeypatch):
    builder = mocker.MagicMock()
    monkeypatch.setattr('ulogger.syslog.SyslogHandlerBuilder', builder)

    syslog.get_handler('foo')

    builder.assert_called_once_with(
        'foo', address=None, proto=None, facility=None, fmt=None, datefmt=None)
    builder.return_value.get_handler.assert_called_once_with()


@pytest.fixture
def syslog_mock(mocker, monkeypatch):
    syslog_mock = mocker.MagicMock(
        logging.handlers.SysLogHandler, autospec=True)
    monkeypatch.setattr(syslog.logging.handlers, 'SysLogHandler', syslog_mock)


params = [
    # linux env
    ['default', ((syslog.sys, 'platform', 'linux2'),),
     '/dev/log', SYSLOG_DEFAULT_FMT, EXP_DATE_FORMAT],
    # remote/docker/helios env
    ['remote', ((syslog.os, 'environ', REMOTE_ENV),),
     ('localhost', 12345), SYSLOG_DEFAULT_FMT, EXP_DATE_FORMAT],
    # os x env
    ['darwin', ((syslog.sys, 'platform', 'darwin'),
                (syslog.os.path, 'exists', lambda x: True)),
     ('/var/run/syslog'), SYSLOG_OSX_FMT, None]
]
args = 'environ,patches,address,fmt,datefmt'


@pytest.mark.parametrize(args, params)
def test_syslog_handler_builder_env(environ, patches, address, fmt, datefmt,
                                    syslog_mock, mocker, monkeypatch):
    for patch in patches:
        monkeypatch.setattr(patch[0], patch[1], patch[2])

    builder = syslog.SyslogHandlerBuilder('foo')

    assert builder._environ == environ
    assert builder.address == address

    formatter = builder.get_formatter()
    assert formatter._fmt == fmt
    assert formatter.datefmt == datefmt

    formatter_mock = mocker.MagicMock(logging.Formatter, autospec=True)
    monkeypatch.setattr(syslog.logging, 'Formatter', formatter_mock)

    handler = builder.get_handler()
    handler.setFormatter.assert_called_once_with(formatter_mock.return_value)


fmts = [
    # explicit default
    '%(asctime)s.%(msecs)03dZ foo (%(process)d): %(message)s',
    # custom
    '%(created)f %(levelno)d %(message)s',
    # implicit default
    None
]
datefmts = [
    # explicit default
    '%Y-%m-%dT%H:%M:%S',
    # custom
    '%d/%m/%y %H:%M:%S.%f',
    # implicit default
    None
]
args = [(f, d) for f in fmts for d in datefmts]
params = 'fmt,datefmt'


@pytest.mark.parametrize(params, args)
def test_syslog_handler_builder_fmts(fmt, datefmt, monkeypatch):
    monkeypatch.setattr(syslog.sys, 'platform', 'linux2')
    builder = syslog.SyslogHandlerBuilder('foo', fmt=fmt, datefmt=datefmt)

    if not fmt:
        fmt = fmts[0]
    if not datefmt:
        datefmt = datefmts[0]

    formatter = builder.get_formatter()
    assert formatter._fmt == fmt
    assert formatter.datefmt == datefmt


args = [
    (None, 16),
    (None, logging.handlers.SysLogHandler.LOG_LOCAL0),
    (1, 1),
    (logging.handlers.SysLogHandler.LOG_USER, 1),
]

params = 'given,exp'


@pytest.mark.parametrize(params, args)
def test_syslog_handler_builder_facility(given, exp, mocker, monkeypatch):
    monkeypatch.setattr(syslog.sys, 'platform', 'linux2')

    with mocker.patch('socket.socket') as mock_socket:
        mock_socket.return_value.recv.return_value = True
        builder = syslog.SyslogHandlerBuilder('foo', facility=given)

    handler = builder.get_handler()

    assert builder.facility == exp
    assert handler.facility == exp


args = [
    # ((given address), given proto), (exp address), exp proto)
    ((('localhost', 514), 2), (('localhost', 514), 2)),
    ((('localhost', 514), None), (('localhost', 514), 2)),
    ((('10.99.0.1', None), 1), (('10.99.0.1', 514), 1)),
    (('/dev/log', None), ('/dev/log', 2)),
]

params = 'given,exp'


@pytest.mark.parametrize(params, args)
def test_syslog_handler_builder_address(given, exp, mocker, monkeypatch):
    monkeypatch.setattr(syslog.sys, 'platform', 'linux2')

    with mocker.patch('socket.socket') as mock_socket:
        mock_socket.return_value.recv.return_value = True
        builder = syslog.SyslogHandlerBuilder(
            'foo', address=given[0], proto=given[1])

    handler = builder.get_handler()

    assert builder.address == exp[0]
    assert builder.proto == exp[1]
    assert handler.address == exp[0]
    assert handler.socktype == exp[1]


args = [
    (
        (('localhost', 514), 2),  # explicit address/proto set
        (None, None),  # no envs set
        (('localhost', 514), 2)  # expected address/socktype
    ), (
        (None, None),  # no given address/proto
        ('localhost', None),  # host env set
        (('localhost', 514), 2)  # expected address/socktype
    ), (
        (None, None),  # no given address/proto
        ('localhost', 514),  # host and port envs set
        (('localhost', 514), 2)  # expected address/socktype
    ), (
        (None, 1),  # explicit proto set
        ('localhost', 514),  # host and port envs set
        (('localhost', 514), 1)  # expected address/socktype
    ), (
        (('localhost', 514), 2),  # explicit address/proto set
        ('127.0.0.1', 515),  # host and port envs set
        (('localhost', 514), 2)  # expected address/socktype
    )

]

params = 'given,envs,exp'


@pytest.mark.parametrize(params, args)
def test_syslog_handler_builder_address_envs(given, envs, exp,
                                             monkeypatch, mocker):
    monkeypatch.setattr(syslog.sys, 'platform', 'linux2')

    patch = {}
    if envs[0]:
        patch['SYSLOG_HOST'] = envs[0]
    if envs[1]:
        patch['SYSLOG_PORT'] = envs[1]

    if patch:
        monkeypatch.setattr(syslog.os, 'environ', patch)

    with mocker.patch('socket.socket') as mock_socket:
        mock_socket.return_value.recv.return_value = True
        builder = syslog.SyslogHandlerBuilder(
            'foo', address=given[0], proto=given[1])

    handler = builder.get_handler()

    assert builder.address == exp[0]
    assert builder.proto == exp[1]
    assert handler.address == exp[0]
    assert handler.socktype == exp[1]
