import unittest

from workbuddy_openai.upstream import ensure_system, parse_sse_objects, resolve_model


class EnsureSystemTests(unittest.TestCase):
    def test_injects_when_missing(self):
        out = ensure_system([{"role": "user", "content": "hi"}])
        self.assertEqual(out[0]["role"], "system")
        self.assertEqual(out[1]["content"], "hi")

    def test_keeps_existing(self):
        msgs = [{"role": "system", "content": "x"}, {"role": "user", "content": "y"}]
        self.assertIs(ensure_system(msgs)[0]["content"], "x")


class SseParseTests(unittest.TestCase):
    def test_assembles_content_and_usage(self):
        lines = [
            'data: {"id":"cmb-1","model":"default-model","choices":[{"delta":{"role":"assistant","content":""}}]}\n',
            'data: {"choices":[{"delta":{"content":"32"}}]}\n',
            'data: {"choices":[{"delta":{"content":"3"},"finish_reason":"stop"}],"usage":{"credit":0,"total_tokens":10}}\n',
            "data: [DONE]\n",
        ]
        out = parse_sse_objects(lines)
        self.assertEqual(out["choices"][0]["message"]["content"], "323")
        self.assertEqual(out["choices"][0]["finish_reason"], "stop")
        self.assertEqual(out["model"], "default-model")
        self.assertEqual(out["usage"]["credit"], 0)

    def test_reasoning_kept_separate(self):
        lines = [
            'data: {"choices":[{"delta":{"reasoning_content":"think "}}]}\n',
            'data: {"choices":[{"delta":{"reasoning_content":"more","content":"ok"},"finish_reason":"stop"}]}\n',
        ]
        out = parse_sse_objects(lines)
        msg = out["choices"][0]["message"]
        self.assertEqual(msg["content"], "ok")
        self.assertEqual(msg["reasoning_content"], "think more")


class AliasTests(unittest.TestCase):
    def test_catalog_aliases(self):
        cfg = {"models": [{"id": "fast-model", "name": "Fast"}, {"id": "default-model", "name": "Default"}]}
        self.assertEqual(resolve_model("fast", cfg), "fast-model")
        self.assertEqual(resolve_model("", cfg), "default-model")
        self.assertEqual(resolve_model("auto", cfg), "default-model")


if __name__ == "__main__":
    unittest.main()
