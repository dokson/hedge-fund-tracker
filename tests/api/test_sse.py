import asyncio
import io
import queue
import time
import unittest

from tenacity import retry, stop_after_attempt

from app.api.sse import (
    _ContextAwareStdout,
    _make_sse_stream,
    _queue_get_with_timeout,
    _request_log_q,
    _run_sse_target,
)
from app.utils.logger import request_id_var


class TestQueueGetWithTimeout(unittest.TestCase):
    def test_returns_item_when_available(self):
        """
        An enqueued item is returned immediately.
        """
        q: queue.SimpleQueue = queue.SimpleQueue()
        q.put(("log", "hello"))
        self.assertEqual(_queue_get_with_timeout(q), ("log", "hello"))

    def test_returns_none_on_empty_queue(self):
        """
        An empty queue yields None after the poll timeout instead of blocking
        forever, so executor threads are released when a client disconnects.
        """
        q: queue.SimpleQueue = queue.SimpleQueue()
        started = time.monotonic()
        self.assertIsNone(_queue_get_with_timeout(q))
        self.assertLess(time.monotonic() - started, 5)


class TestRetryErrorMessage(unittest.TestCase):
    def test_exhausted_retries_report_the_last_failure(self):
        """
        A RetryError surfaces the last attempt's message, not tenacity's Future repr.
        """

        @retry(stop=stop_after_attempt(1))
        def target():
            """
            Fail every attempt.
            """
            raise ValueError("AI returned invalid weight values")

        q: queue.SimpleQueue = queue.SimpleQueue()
        _run_sse_target(target, q)

        kind, payload = q.get_nowait()
        self.assertEqual(kind, "error")
        self.assertIn("AI returned invalid weight values", payload)
        self.assertNotIn("Future", payload)


class TestMakeSseStream(unittest.TestCase):
    def _collect(self, response):
        """
        Drains the StreamingResponse body iterator into a list of SSE lines.
        """

        async def _run():
            chunks = []
            async for chunk in response.body_iterator:
                chunks.append(chunk)
            return chunks

        return asyncio.run(_run())

    def test_streams_logs_then_result(self):
        """
        Prints from the target function arrive as log events, followed by a
        terminal result event.
        """

        def target():
            print("working")
            return {"ok": True}

        chunks = self._collect(_make_sse_stream(target))

        self.assertTrue(any('"type": "log"' in c and "working" in c for c in chunks))
        self.assertIn('"type": "result"', chunks[-1])

    def test_slow_target_still_delivers_result(self):
        """
        A target outliving the queue poll timeout still terminates the stream
        with its result (the consumer loops on empty polls).
        """

        def target():
            time.sleep(1.5)
            return "done"

        chunks = self._collect(_make_sse_stream(target))

        self.assertIn('"type": "result"', chunks[-1])
        self.assertIn("done", chunks[-1])

    def test_exception_yields_error_event(self):
        """
        An exception in the target function terminates the stream with an
        error event instead of hanging the consumer.
        """

        def target():
            raise ValueError("boom")

        chunks = self._collect(_make_sse_stream(target))

        self.assertIn('"type": "error"', chunks[-1])
        self.assertIn("boom", chunks[-1])


class TestRateLimitErrorMessage(unittest.TestCase):
    def test_yahoo_rate_limit_is_reported_readably(self):
        """
        A Yahoo rate limit ends the stream with an error naming the rate limit.
        """
        from yfinance.exceptions import YFRateLimitError

        def target():
            """
            Fail like a rate-limited price sweep.
            """
            raise YFRateLimitError()

        q: queue.SimpleQueue = queue.SimpleQueue()
        _run_sse_target(target, q)

        kind, payload = q.get_nowait()
        self.assertEqual(kind, "error")
        self.assertIn("Yahoo Finance rate limit", payload)


class TestCaptureContext(unittest.TestCase):
    def test_capturing_reflects_the_bound_queue(self):
        """
        The wrapper reports capturing only while a request queue is bound.
        """
        fallback = io.StringIO()
        wrapper = _ContextAwareStdout(fallback)

        self.assertFalse(wrapper.capturing)
        token = _request_log_q.set(queue.SimpleQueue())
        try:
            self.assertTrue(wrapper.capturing)
        finally:
            _request_log_q.reset(token)
        self.assertIs(wrapper.fallback, fallback)

    def test_stream_thread_inherits_the_request_id(self):
        """
        The worker thread sees the request id bound by the HTTP middleware.
        """
        token = request_id_var.set("req-sse")
        try:
            response = _make_sse_stream(request_id_var.get)
        finally:
            request_id_var.reset(token)

        chunks = TestMakeSseStream()._collect(response)

        self.assertIn("req-sse", chunks[-1])


if __name__ == "__main__":
    unittest.main()
