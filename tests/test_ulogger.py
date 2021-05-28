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
import sys
from types import ModuleType

import pytest

from ulogger import exceptions
from ulogger import ulogger


@pytest.fixture
def logging_mock(mocker, monkeypatch):
    logging_module = mocker.MagicMock(logging, autospec=True)
    monkeypatch.setattr(ulogger, 'logging', logging_module)
    return logging_module


@pytest.fixture
def import_module_mock(mocker, monkeypatch):
    import_module = mocker.MagicMock('importlib.import_module', autospec=True)
    module_mock = mocker.MagicMock()
    handler = mocker.MagicMock()
    module_mock.get_handler = mocker.MagicMock()
    module_mock.get_handler.return_value = handler
    import_module_mock.return_value = module_mock
    monkeypatch.setattr(ulogger, 'import_module', import_module)
    return import_module


@pytest.fixture
def setup_default_handler_mock(mocker, monkeypatch):
    default = mocker.MagicMock(logging.StreamHandler, autospec=True)
    monkeypatch.setattr(ulogger, '_setup_default_handler', default)
    return default


args = 'handler,level'
params = [
    ('syslog', 'INFO'),
    ('stream', 'DEBUG')
]


@pytest.mark.parametrize(args, params)
def test_setup_logging(handler, level, logging_mock, import_module_mock,
                       setup_default_handler_mock):
    ulogger.setup_logging('foo', level, [handler])

    if handler == 'stream':
        handler_mock = setup_default_handler_mock.return_value
    else:
        module_path = 'ulogger.{}'.format(handler)
        import_module_mock.assert_called_once_with(
            module_path, package='ulogger')
        handler_mock = import_module_mock.return_value.get_handler.return_value

    logging_mock.getLevelName.assert_called_once_with(level)
    logging_mock.getLogger.assert_called_with('')
    assert logging_mock.getLogger.call_count == 2

    get_logger = logging_mock.getLogger.return_value
    get_logger.addHandler.assert_called_once_with(handler_mock)
    get_logger.setLevel.assert_called_once_with(
        logging_mock.getLevelName(level))


def test_setup_logging_multiple_handlers(import_module_mock,
                                         setup_default_handler_mock):
    handlers = ['stream', 'syslog']
    ulogger.setup_logging('tests', 'INFO', handlers)
    logger = logging.getLogger('')
    actual_handlers = [h for h in logger.handlers if h.level != logging.NOTSET]
    assert len(actual_handlers) == len(handlers)


def test_setup_logging_raises():
    with pytest.raises(exceptions.ULoggerError) as e:
        ulogger.setup_logging('tests', 'INFO', ['notahandler'])

    assert e.match('Unsupported log handler: "notahandler".')


def test_setup_logging_raises_not_implemented():
    module_name = 'fake_handler'
    # Create a 'virtual' module that lacks the expected function
    fake_module = ModuleType(module_name)
    sys.modules['ulogger.{}'.format(module_name)] = fake_module

    with pytest.raises(exceptions.ULoggerError) as e:
        ulogger.setup_logging('tests', 'INFO', [module_name])

    assert e.match(
        '"get_handler" function not implemented for "{}"'.format(module_name))


fmts = [
    # explicit default
    '%(asctime)s.%(msecs)03dZ foo (%(process)d) %(levelname)s: %(message)s',
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
def test_setup_default_handler(mocker, monkeypatch, fmt, datefmt):
    handler_mock = mocker.MagicMock(logging.StreamHandler, autospec=True)
    monkeypatch.setattr(ulogger.logging, 'StreamHandler', handler_mock)
    logging_mock = mocker.MagicMock(logging, autospec=True)
    monkeypatch.setattr(ulogger, 'logging', logging_mock)

    ret_handler = ulogger._setup_default_handler('foo', fmt, datefmt)

    if not fmt:
        fmt = fmts[0]
    if not datefmt:
        datefmt = datefmts[0]

    logging_mock.Formatter.assert_called_once_with(
        fmt=fmt, datefmt=datefmt)

    ret_handler.setFormatter.assert_called_once_with(
        logging_mock.Formatter.return_value)
