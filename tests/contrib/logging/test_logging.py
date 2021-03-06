import logging

import ddtrace
from ddtrace.constants import ENV_KEY, VERSION_KEY
from ddtrace.compat import StringIO
from ddtrace.contrib.logging import patch, unpatch
from ddtrace.vendor import wrapt

from ...base import BaseTracerTestCase


logger = logging.getLogger()
logger.level = logging.INFO

DEFAULT_FORMAT = (
    "%(message)s - dd.service=%(dd.service)s dd.version=%(dd.version)s dd.env=%(dd.env)s"
    " dd.trace_id=%(dd.trace_id)s dd.span_id=%(dd.span_id)s"
)


def current_span(tracer=None):
    if not tracer:
        tracer = ddtrace.tracer
    return tracer.current_span()


def capture_function_log(func, fmt=DEFAULT_FORMAT):
    # add stream handler to capture output
    out = StringIO()
    sh = logging.StreamHandler(out)

    try:
        formatter = logging.Formatter(fmt)
        sh.setFormatter(formatter)
        logger.addHandler(sh)
        result = func()
    finally:
        logger.removeHandler(sh)

    return out.getvalue().strip(), result


class LoggingTestCase(BaseTracerTestCase):
    def setUp(self):
        patch()
        super(LoggingTestCase, self).setUp()

    def tearDown(self):
        unpatch()
        super(LoggingTestCase, self).tearDown()

    def test_patch(self):
        """
        Confirm patching was successful
        """
        log = logging.getLogger()
        self.assertTrue(isinstance(log.makeRecord, wrapt.BoundFunctionWrapper))

        unpatch()
        log = logging.getLogger()
        self.assertFalse(isinstance(log.makeRecord, wrapt.BoundFunctionWrapper))

    def _test_logging(self, create_span, version="", env=""):
        def func():
            span = create_span()
            logger.info("Hello!")
            if span:
                span.finish()
            return span

        with self.override_config("logging", dict(tracer=self.tracer)):
            # with format string for trace info
            output, span = capture_function_log(func)
            trace_id = 0
            span_id = 0
            service = ddtrace.config.service or ""
            if span:
                trace_id = span.trace_id
                span_id = span.span_id

            assert output == "Hello! - dd.service={} dd.version={} dd.env={} dd.trace_id={} dd.span_id={}".format(
                service, version, env, trace_id, span_id
            )

            # without format string
            output, _ = capture_function_log(func, fmt="%(message)s")
            assert output == "Hello!"

    def test_log_trace(self):
        """
        Check logging patched and formatter including trace info
        """

        def create_span():
            return self.tracer.trace("test.logging")

        self._test_logging(create_span=create_span)

        with self.override_global_config(dict(version="global.version", env="global.env")):
            self._test_logging(create_span=create_span, version="global.version", env="global.env")

    def test_log_trace_service(self):
        """
        Check logging patched and formatter including trace info
        """

        def create_span():
            return self.tracer.trace("test.logging", service="logging")

        self._test_logging(create_span=create_span)

        with self.override_global_config(dict(version="global.version", env="global.env")):
            self._test_logging(create_span=create_span, version="global.version", env="global.env")

    def test_log_trace_version(self):
        """
        Check logging patched and formatter including trace info
        """

        def create_span():
            span = self.tracer.trace("test.logging")
            span.set_tag(VERSION_KEY, "manual.version")
            return span

        self._test_logging(create_span=create_span, version="")

        # Setting global config version and overriding with span specific value
        # We always want the globals in the logs
        with self.override_global_config(dict(version="global.version", env="global.env")):
            self._test_logging(create_span=create_span, version="global.version", env="global.env")

    def test_log_trace_env(self):
        """
        Check logging patched and formatter including trace info
        """

        def create_span():
            span = self.tracer.trace("test.logging")
            span.set_tag(ENV_KEY, "manual.env")
            return span

        self._test_logging(create_span=create_span, env="")

        # Setting global config env and overriding with span specific value
        # We always want the globals in the logs
        with self.override_global_config(dict(version="global.version", env="global.env")):
            self._test_logging(create_span=create_span, version="global.version", env="global.env")

    def test_log_no_trace(self):
        """
        Check traced funclogging patched and formatter not including trace info
        """

        def create_span():
            return None

        self._test_logging(create_span=create_span)

        with self.override_global_config(dict(version="global.version", env="global.env")):
            self._test_logging(create_span=create_span, version="global.version", env="global.env")
