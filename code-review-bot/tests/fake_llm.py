from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeLLM:
    def __init__(
        self,
        text: str,
        *,
        texts: dict[str, str] | None = None,
        input_tokens: int = 100,
        output_tokens: int = 20,
        host: str = "127.0.0.1",
    ):
        self.text = text
        self.texts = texts or {}
        self.host = host
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.requests: list[dict] = []
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        assert self._server is not None
        host, port = self._server.server_address
        return f"http://{host}:{port}/v1"

    @property
    def container_url(self) -> str:
        assert self._server is not None
        _, port = self._server.server_address
        return f"http://host.docker.internal:{port}/v1"

    def reply_for(self, body: dict) -> str:
        messages = body.get("messages") or []
        system = "\n".join(
            str(message.get("content", ""))
            for message in messages
            if isinstance(message, dict) and message.get("role") == "system"
        )
        if "principal/staff engineer and the final gate" in system:
            return self.texts.get("principal", self.text)
        if "application security engineer" in system:
            return self.texts.get("security", self.text)
        return self.texts.get("senior", self.text)

    def start(self) -> "FakeLLM":
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_: object) -> None:
                return

            def _read(self) -> dict:
                length = int(self.headers.get("Content-Length", "0"))
                return json.loads(self.rfile.read(length) or b"{}")

            def do_GET(self) -> None:  # noqa: N802
                if self.path.rstrip("/").endswith("/models"):
                    data = json.dumps({"object": "list", "data": [{"id": "fast", "object": "model"}]}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                self.send_response(404)
                self.end_headers()

            def do_POST(self) -> None:  # noqa: N802
                body = self._read()
                fake.requests.append(body)
                if not self.path.rstrip("/").endswith("/chat/completions"):
                    self.send_response(404)
                    self.end_headers()
                    return
                reply = fake.reply_for(body)
                model = body.get("model", "fast")
                if body.get("stream"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    chunk = {
                        "id": "chatcmpl-test",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"role": "assistant", "content": reply},
                                "finish_reason": None,
                            }
                        ],
                    }
                    self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                    done = {
                        "id": "chatcmpl-test",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                        "usage": {
                            "prompt_tokens": fake.input_tokens,
                            "completion_tokens": fake.output_tokens,
                            "total_tokens": fake.input_tokens + fake.output_tokens,
                        },
                    }
                    self.wfile.write(f"data: {json.dumps(done)}\n\n".encode())
                    self.wfile.write(b"data: [DONE]\n\n")
                    return
                data = json.dumps(
                    {
                        "id": "chatcmpl-test",
                        "object": "chat.completion",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant", "content": reply},
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {
                            "prompt_tokens": fake.input_tokens,
                            "completion_tokens": fake.output_tokens,
                            "total_tokens": fake.input_tokens + fake.output_tokens,
                        },
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self._server = ThreadingHTTPServer((self.host, 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        if self._thread:
            self._thread.join(timeout=2)

    def __enter__(self) -> "FakeLLM":
        return self.start()

    def __exit__(self, *_: object) -> None:
        self.stop()
