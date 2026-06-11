import asyncio
import queue
import time
import unittest

from app.api.sse import _make_sse_stream, _queue_get_with_timeout


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


if __name__ == "__main__":
    unittest.main()
