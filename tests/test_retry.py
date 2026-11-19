import io
import unittest
import urllib.error
from unittest import mock

from harness import retry


def http_error(code, body=b"", headers=None):
    return urllib.error.HTTPError("http://x", code, "err", headers or {},
                                  io.BytesIO(body))


def ok():
    return {"choices": [{"message": {"content": "ok"}}]}


class RetryTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict("os.environ", {
            "LOOP_RETRY_ATTEMPTS": "4", "LOOP_RETRY_BASE_MS": "1",
            "LOOP_RETRY_MAX_MS": "2"}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.sleep = mock.patch.object(retry.time, "sleep").start()
        self.addCleanup(mock.patch.stopall)

    def test_transient_http_then_success(self):
        seen = []
        with mock.patch.object(retry.api, "call",
                               side_effect=[http_error(503), http_error(429), ok()]):
            row = retry.call([], "k", {}, on_retry=lambda *a: seen.append(a))
        self.assertEqual(row["choices"][0]["message"]["content"], "ok")
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[0][1], 503)
        self.assertEqual(seen[1][1], 429)

    def test_auth_error_is_not_retried(self):
        with mock.patch.object(retry.api, "call", side_effect=[http_error(401)]) as call:
            with self.assertRaises(retry.Error) as cm:
                retry.call([], "k", {})
        self.assertEqual(cm.exception.code, 401)
        self.assertEqual(call.call_count, 1)
        self.sleep.assert_not_called()

    def test_context_error_is_raised_for_compaction(self):
        body = b'{"error":{"message":"maximum context length is 8192 tokens"}}'
        with mock.patch.object(retry.api, "call", side_effect=[http_error(400, body)]):
            with self.assertRaises(retry.Error) as cm:
                retry.call([], "k", {})
        self.assertTrue(retry.is_context(cm.exception.text))

    def test_empty_choices_and_network_errors_retry(self):
        with mock.patch.object(retry.api, "call",
                               side_effect=[{"choices": []},
                                            urllib.error.URLError("reset"), ok()]):
            row = retry.call([], "k", {})
        self.assertEqual(row["choices"][0]["message"]["content"], "ok")

    def test_exhaustion_reports_attempts(self):
        with mock.patch.object(retry.api, "call", side_effect=http_error(500)):
            with self.assertRaises(retry.Error) as cm:
                retry.call([], "k", {})
        self.assertEqual(cm.exception.attempts, 4)


if __name__ == "__main__":
    unittest.main()
