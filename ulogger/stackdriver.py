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

import logging

import requests
from google.cloud import logging as gcl_logging
from google.cloud.logging import handlers as gcl_handlers
from google.cloud.logging import resource as gcl_resource

from ulogger import exceptions


class CloudLoggingHandlerBuilder:
    """Creates instances of `google.cloud.logging.handlers.CloudLoggingHandler`

    Instances of the handler will be configured by retrieving the host's
    metadata. It can send logs to a different GCP project than the host
    is in by providing 'project_id'.

    Example usage:

        import logging
        from ulogging import stackdriver

        logger = logging.getLogger('')
        gcl_handler = stackdriver.CloudLoggingHandlerBuilder().get_handler()
        logger.setLevel(logging.INFO)
        log.info('Test message')

    Args:
        progname (str): Name of program.
        fmt (:obj:`str`, optional): Desired log format if different than
            the default; uses the same formatting string options
            supported in the stdlib's `logging` module.
        datefmt (:obj:`str`, optional): Desired date format if different
            than the default; uses the same formatting string options
            supported in the stdlib's `logging` module.
        project_id (:obj:`str`, optional): Project under which logs will
            be saved in GCL. If not provided, will get it from host's
            metadata.
        credentials (:obj:`obj`, optional): An instance of `google.auth.
            credentials.Credentials`. If not provided, will infer from
            environment.
        debug_thread_worker (:obj:`bool`, optional): Whether the
            background logging thread should emit DEBUG messages. If
            `False`, thread logger level is set to INFO.
    """
    METADATA_ENDPOINT = ('http://metadata.google.internal/computeMetadata/v1/'
                         '{data_type}/{key}')

    def __init__(self,
                 progname,
                 fmt=None,
                 datefmt=None,
                 project_id=None,
                 credentials=None,
                 debug_thread_worker=False):
        if project_id:
            self.project_id = project_id
        else:
            self.project_id = self._get_metadata(
                data_type='project', key='project-id')

        self.progname = progname
        self.fmt = fmt
        self.datefmt = datefmt
        self.credentials = credentials
        self.debug_thread_worker = debug_thread_worker
        self.hostname = self._get_metadata(data_type='instance', key='name')
        self.instance_id = self._get_metadata(data_type='instance', key='id')
        zone_str = self._get_metadata(data_type='instance', key='zone')
        self.zone = zone_str.split('/')[-1]
        self.resource = self._create_gcl_resource()

    def _get_metadata(self, data_type, key, timeout=5):
        """Get host instance metadata (only works on GCP hosts).

        More details about instance metadata:
        https://cloud.google.com/compute/docs/storing-retrieving-metadata

        Args:
            data_type (str): Type of metadata to fetch. Eg. project,
                instance
            key (str): Key of metadata to fetch
            timeout (int, optional): HTTP request timeout in seconds.
                Default is 5 seconds.
        Returns:
            (str): Plain text value of metadata entry
        Raises:
            GoogleCloudError: when request to metadata endpoint fails
        """
        endpoint_url = self.METADATA_ENDPOINT.format(
            data_type=data_type, key=key)
        try:
            rsp = requests.get(
                endpoint_url,
                headers={'Metadata-Flavor': 'Google'},
                timeout=timeout)
            rsp.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise exceptions.GoogleCloudError(
                'Could not fetch "{key}" from "{type}" metadata using "{url}".'
                'Error: {e}'.format(
                    key=key, type=data_type, url=endpoint_url, e=e))
        metadata_value = rsp.text
        if metadata_value.strip() == '':
            raise exceptions.GoogleCloudError(
                'Error when fetching metadata from "{url}": server returned '
                'an empty value.'.format(url=endpoint_url))
        return metadata_value

    def _create_gcl_resource(self):
        """Create a configured Resource object.

        The logging.resource.Resource object enables GCL to filter and
        bucket incoming logs according to which resource (host) they're
        coming from.

        Returns:
            (obj): Instance of `google.cloud.logging.resource.Resource`
        """

        return gcl_resource.Resource('gce_instance', {
            'project_id': self.project_id,
            'instance_id': self.instance_id,
            'zone': self.zone
        })

    def get_formatter(self):
        """Create a fully configured `logging.Formatter`

        Example of formatted log message:
        2017-08-27T20:19:24.424 cpm-example-gew1 progname (23123): hello

        Returns:
            (obj): Instance of `logging.Formatter`
        """
        if not self.fmt:
            self.fmt = ('%(asctime)s.%(msecs)03d {host} {progname} '
                        '(%(process)d): %(message)s').format(
                        host=self.hostname, progname=self.progname)
        if not self.datefmt:
            self.datefmt = '%Y-%m-%dT%H:%M:%S'
        return logging.Formatter(fmt=self.fmt, datefmt=self.datefmt)

    def _set_worker_thread_level(self):
        """Sets logging level of the background logging thread to DEBUG or INFO
        """
        bthread_logger = logging.getLogger(
            'google.cloud.logging.handlers.transports.background_thread')
        if self.debug_thread_worker:
            bthread_logger.setLevel(logging.DEBUG)
        else:
            bthread_logger.setLevel(logging.INFO)

    def get_handler(self):
        """Create a fully configured CloudLoggingHandler.

        Returns:
            (obj): Instance of `google.cloud.logging.handlers.
                                CloudLoggingHandler`
        """

        gcl_client = gcl_logging.Client(
            project=self.project_id, credentials=self.credentials)
        handler = gcl_handlers.CloudLoggingHandler(
            gcl_client,
            resource=self.resource,
            labels={
                'resource_id': self.instance_id,
                'resource_project': self.project_id,
                'resource_zone': self.zone,
                'resource_host': self.hostname
            })
        handler.setFormatter(self.get_formatter())
        self._set_worker_thread_level()
        return handler


def get_handler(progname, fmt=None, datefmt=None, project_id=None,
                credentials=None, debug_thread_worker=False, **_):
    """Helper function to create a Stackdriver handler.

    See `ulogger.stackdriver.CloudLoggingHandlerBuilder` for arguments
    and supported keyword arguments.

    Returns:
        (obj): Instance of `google.cloud.logging.handlers.
                            CloudLoggingHandler`
    """
    builder = CloudLoggingHandlerBuilder(
        progname, fmt=fmt, datefmt=datefmt, project_id=project_id,
        credentials=credentials, debug_thread_worker=debug_thread_worker)
    return builder.get_handler()
