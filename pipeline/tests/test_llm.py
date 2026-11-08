import json
import unittest
from unittest import mock

from pipeline import llm
from pipeline.config import Settings


class _Resp:
    def __init__(self, status, body, headers=None):
        self.status_code = status
        self._body = body
        self.headers = headers or {}
        self.text = json.dumps(body)

    def json(self):
        return self._body


class LLMBackendTests(unittest.TestCase):
    def test_strip_fences_and_extract(self):
        self.assertEqual(llm.extract_json('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(llm.extract_json('Sure! {"a": {"b": 2}} done'), {"a": {"b": 2}})
        with self.assertRaises(llm.LLMError):
            llm.extract_json("no json here")

    def test_litellm_backend(self):
        s = Settings(llm_base_url="http://litellm:4000/v1", llm_api_key="k", llm_model_copy="copy-model")
        body = {"choices": [{"message": {"content": '```json\n{"headline": "Ahoj"}\n```'}}]}
        with mock.patch("pipeline.llm.requests.post", return_value=_Resp(200, body)) as post:
            out = llm.chat_json("sys", "user", "copy", settings=s)
        self.assertEqual(out, {"headline": "Ahoj"})
        url = post.call_args.args[0]
        payload = post.call_args.kwargs["json"]
        headers = post.call_args.kwargs["headers"]
        self.assertEqual(url, "http://litellm:4000/v1/chat/completions")
        self.assertEqual(payload["model"], "copy-model")
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertEqual(headers["Authorization"], "Bearer k")
        self.assertEqual(post.call_args.kwargs["timeout"], 60)

    def test_litellm_retry_on_429(self):
        s = Settings(llm_base_url="http://litellm:4000/v1", llm_api_key="k")
        ok = {"choices": [{"message": {"content": '{"x": 1}'}}]}
        with mock.patch("pipeline.llm.time.sleep"), \
             mock.patch("pipeline.llm.requests.post", side_effect=[_Resp(429, {}, {"Retry-After": "0"}), _Resp(200, ok)]) as post:
            out = llm.chat_json("s", "u", "classify", settings=s)
        self.assertEqual(out, {"x": 1})
        self.assertEqual(post.call_count, 2)

    def test_anthropic_backend(self):
        s = Settings(llm_api_key=None, anthropic_api_key="ant", anthropic_model="claude-sonnet-5-5")
        body = {"content": [{"type": "text", "text": '{"headline": "Hello"}'}]}
        with mock.patch("pipeline.llm.requests.post", return_value=_Resp(200, body)) as post:
            out = llm.chat_json("sys", "user", "copy", settings=s)
        self.assertEqual(out, {"headline": "Hello"})
        url = post.call_args.args[0]
        headers = post.call_args.kwargs["headers"]
        payload = post.call_args.kwargs["json"]
        self.assertEqual(url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(headers["x-api-key"], "ant")
        self.assertEqual(headers["anthropic-version"], "2023-06-01")
        self.assertEqual(payload["model"], "claude-sonnet-5-5")
        self.assertEqual(payload["messages"][0]["role"], "user")

    def test_unavailable(self):
        s = Settings(llm_api_key=None, anthropic_api_key=None)
        with self.assertRaises(llm.LLMUnavailable):
            llm.chat_json("s", "u", settings=s)
        self.assertEqual(llm.backend_name(s), "none")

    def test_http_error_raises_llmerror(self):
        s = Settings(llm_base_url="http://litellm:4000/v1", llm_api_key="k")
        with mock.patch("pipeline.llm.requests.post", return_value=_Resp(400, {"error": "bad"})):
            with self.assertRaises(llm.LLMError):
                llm.chat_json("s", "u", settings=s)


if __name__ == "__main__":
    unittest.main()
