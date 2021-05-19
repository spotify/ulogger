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

import pytest
import requests

from ulogger import exceptions
from ulogger import stackdriver


@pytest.fixture
def mock_requests_get(mocker):
    mock = mocker.Mock()
    project_id_rsp = mocker.Mock()
    project_id_rsp.text = 'test-project'
    host_rsp = mocker.Mock()
    host_rsp.text = 'cpm-guc99-hostname-1a'
    instance_id_rsp = mocker.Mock()
    instance_id_rsp.text = '123123'
    zone_rsp = mocker.Mock()
    zone_rsp.text = 'projects/192472736367/zones/us-central1-f'
    # Ordering matters and reflects calls in CloudLoggingHandlerBuilder.__init__
    mock.side_effect = [
        project_id_rsp, host_rsp, instance_id_rsp, zone_rsp,
    ]
    mocker.patch('ulogger.stackdriver.requests.get', mock)
    return mock


@pytest.fixture
def mock_cloud_handler(mocker):
    mock = mocker.Mock(
        stackdriver.CloudLoggingHandlerBuilder, autospec=True)
    mocker.patch('ulogger.stackdriver.CloudLoggingHandlerBuilder', mock)
    return mock


@pytest.fixture
def mock_logging_resource(mocker):
    mock_resource = mocker.Mock()
    mocker.patch('ulogger.stackdriver.gcl_resource.Resource', mock_resource)
    return mock_resource


@pytest.fixture
def mock_get_logger(mocker):
    mock_logger = mocker.Mock()
    mock_get_logger = mocker.Mock(return_value=mock_logger)
    mocker.patch('ulogger.stackdriver.logging.getLogger', mock_get_logger)
    return mock_get_logger, mock_logger


@pytest.fixture
def mock_gcl_client(mocker, mock_get_logger):
    _, mock_logger = mock_get_logger
    mock_client = mocker.MagicMock()
    mock_client_class = mocker.Mock(return_value=mock_client)
    mocker.patch(
        'ulogger.stackdriver.gcl_logging.Client',
        mock_client_class)
    return mock_client, mock_client_class


@pytest.fixture
def mock_gcl_handler(mocker):
    mock_handler = mocker.Mock()
    mock_cloud_handler = mocker.Mock(
        stackdriver.gcl_handlers.CloudLoggingHandler,
        autospec=True, return_value=mock_handler)
    mocker.patch('ulogger.stackdriver.gcl_handlers.CloudLoggingHandler',
                 mock_cloud_handler)
    return mock_handler, mock_cloud_handler


def test_get_handler(mocker):
    builder = mocker.Mock()
    mocker.patch('ulogger.stackdriver.CloudLoggingHandlerBuilder', builder)

    stackdriver.get_handler(
        'test-progname', project_id='example-project', credentials=None)

    builder.assert_called_once_with(
            'test-progname', project_id='example-project', credentials=None,
            fmt=None, datefmt=None, debug_thread_worker=False)


def test_builder_create_gcl_resource(mocker, mock_requests_get,
                                     mock_logging_resource):
    stackdriver.CloudLoggingHandlerBuilder('test-progname')

    expected_args = ['gce_instance', {
        'project_id': 'test-project',
        'instance_id': '123123',
        'zone': 'us-central1-f'}]

    mock_logging_resource.assert_called_once_with(*expected_args)


builder_kwargs = [
    {'project_id': None, 'credentials': None},
    {'project_id': 'example-project', 'credentials': 'example-credentials'}
]


@pytest.mark.parametrize('project_id,credentials', builder_kwargs)
def test_builder_get_handler(mocker, mock_requests_get, mock_logging_resource,
                             project_id, credentials, mock_get_logger,
                             mock_gcl_client, mock_gcl_handler):

    mock_client, mock_client_class = mock_gcl_client
    mock_handler, mock_cloud_handler = mock_gcl_handler
    mock_formatter = mocker.Mock()
    mocker.patch('ulogger.stackdriver.CloudLoggingHandlerBuilder.get_formatter',
                 mocker.Mock(return_value=mock_formatter))

    get_logger, logger = mock_get_logger
    get_logger.reset_mock()

    factory = stackdriver.CloudLoggingHandlerBuilder(
            'test-program', project_id=project_id, credentials=credentials)
    factory.get_handler()

    expected_labels = {
        'resource_id': factory.instance_id,
        'resource_project': factory.project_id,
        'resource_zone': factory.zone,
        'resource_host': factory.hostname}
    mock_cloud_handler.assert_called_once_with(
        mock_client,
        resource=factory.resource,
        labels=expected_labels)
    expected_project_id = project_id if project_id else factory.project_id
    mock_client_class.assert_called_once_with(
        project=expected_project_id, credentials=credentials)
    mock_handler.setFormatter.assert_called_once_with(mock_formatter)
    get_logger.assert_called_once_with(
        'google.cloud.logging.handlers.transports.background_thread')
    logger.setLevel.assert_called_once_with(logging.INFO)


def test_builder_get_metadata(mock_requests_get):
    gapi_endpoint = ('http://metadata.google.internal/computeMetadata'
                     '/v1/{0}/{1}')
    stackdriver.CloudLoggingHandlerBuilder('test-progname')

    expected_gapi_headers = {'Metadata-Flavor': 'Google'}
    expected_url_params = [
        ('instance', 'id'),
        ('instance', 'zone'),
        ('project', 'project-id'),
    ]
    for data_type, key in expected_url_params:
        mock_requests_get.assert_any_call(
            gapi_endpoint.format(data_type, key),
            headers=expected_gapi_headers,
            timeout=5)


def test_builder_get_metadata_network_error(mock_requests_get):
    mock_requests_get.side_effect = requests.exceptions.RequestException(
        'Network error!')

    with pytest.raises(exceptions.GoogleCloudError):
        stackdriver.CloudLoggingHandlerBuilder('test-progname')


def test_builder_get_metadata_raises_on_empty_rsp(mocker, mock_requests_get):
    mock_rsp = mocker.Mock()
    mock_rsp.text = ''
    mock_requests_get.side_effect = [mock_rsp]

    with pytest.raises(exceptions.GoogleCloudError):
        stackdriver.CloudLoggingHandlerBuilder('test-progname')


fmts = [
    # explicit default
    ('%(asctime)s.%(msecs)03d cpm-guc99-hostname-1a test-progname '
     '(%(process)d): %(message)s'),
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
def test_builder_get_formatter(mocker, mock_requests_get, fmt, datefmt):
    builder = stackdriver.CloudLoggingHandlerBuilder(
        'test-progname', fmt, datefmt)
    formatter = builder.get_formatter()

    if not fmt:
        fmt = fmts[0]
    if not datefmt:
        datefmt = datefmts[0]

    assert formatter._fmt == fmt
    assert formatter.datefmt == datefmt


def test_set_worker_thread_level_to_debug(mock_requests_get, mock_get_logger,
                                          mock_gcl_handler, mock_gcl_client):
    get_logger, logger = mock_get_logger
    get_logger.reset_mock()

    stackdriver.CloudLoggingHandlerBuilder(
        'test-progname', debug_thread_worker=True).get_handler()

    get_logger.assert_called_once_with(
        'google.cloud.logging.handlers.transports.background_thread')
    logger.setLevel.assert_called_once_with(logging.DEBUG)
