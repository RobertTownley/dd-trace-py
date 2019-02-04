import mock
import re
import warnings

from unittest import TestCase
from nose.tools import eq_, ok_

from tests.test_tracer import get_dummy_tracer
from ddtrace.api import API, Response
from ddtrace.compat import iteritems, httplib


class ResponseMock:
    def __init__(self, content, status=200):
        self.status = status
        self.content = content

    def read(self):
        return self.content


class APITests(TestCase):

    def setUp(self):
        # DEV: Mock here instead of in tests, before we have patched `httplib.HTTPConnection`
        self.conn = mock.MagicMock(spec=httplib.HTTPConnection)
        self.api = API('localhost', 8126)

    def tearDown(self):
        del self.api
        del self.conn

    @mock.patch('logging.Logger.debug')
    def test_parse_response_json(self, log):
        tracer = get_dummy_tracer()
        tracer.debug_logging = True

        test_cases = {
            'OK': dict(
                js=None,
                log='Cannot parse Datadog Agent response, please make sure your Datadog Agent is up to date',
            ),
            'OK\n': dict(
                js=None,
                log='Cannot parse Datadog Agent response, please make sure your Datadog Agent is up to date',
            ),
            'error:unsupported-endpoint': dict(
                js=None,
                log='Unable to parse Datadog Agent JSON response: .*? \'error:unsupported-endpoint\'',
            ),
            42: dict(  # int as key to trigger TypeError
                js=None,
                log='Unable to parse Datadog Agent JSON response: .*? 42',
            ),
            '{}': dict(js={}),
            '[]': dict(js=[]),

            # Priority sampling "rate_by_service" response
            ('{"rate_by_service": '
             '{"service:,env:":0.5, "service:mcnulty,env:test":0.9, "service:postgres,env:test":0.6}}'): dict(
                js=dict(
                    rate_by_service={
                        'service:,env:': 0.5,
                        'service:mcnulty,env:test': 0.9,
                        'service:postgres,env:test': 0.6,
                    },
                ),
            ),
            ' [4,2,1] ': dict(js=[4, 2, 1]),
        }

        for k, v in iteritems(test_cases):
            log.reset_mock()

            r = Response.from_http_response(ResponseMock(k))
            js = r.get_json()
            eq_(v['js'], js)
            if 'log' in v:
                log.assert_called_once()
                msg = log.call_args[0][0] % log.call_args[0][1:]
                ok_(re.match(v['log'], msg), msg)

    @mock.patch('ddtrace.compat.httplib.HTTPConnection')
    def test_put_connection_close(self, HTTPConnection):
        """
        When calling API._put
            we close the HTTPConnection we create
        """
        HTTPConnection.return_value = self.conn

        with warnings.catch_warnings(record=True) as w:
            self.api._put('/test', '<test data>', 1)

            self.assertEqual(len(w), 0, 'Test raised unexpected warnings: {0!r}'.format(w))

        self.conn.request.assert_called_once()
        self.conn.close.assert_called_once()

    @mock.patch('ddtrace.compat.httplib.HTTPConnection')
    def test_put_connection_close_exception(self, HTTPConnection):
        """
        When calling API._put raises an exception
            we close the HTTPConnection we create
        """
        HTTPConnection.return_value = self.conn
        # Ensure calling `request` raises an exception
        self.conn.request.side_effect = Exception

        with warnings.catch_warnings(record=True) as w:
            with self.assertRaises(Exception):
                self.api._put('/test', '<test data>', 1)

            self.assertEqual(len(w), 0, 'Test raised unexpected warnings: {0!r}'.format(w))

        self.conn.request.assert_called_once()
        self.conn.close.assert_called_once()
