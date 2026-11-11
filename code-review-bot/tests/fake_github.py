from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse


class FakeGitHub:
    def __init__(self, host: str = "127.0.0.1"):
        self.host = host
        self.pull = {
            "title": "Add order lookup",
            "body": "Adds a new order lookup path.\n\nCloses #2",
            "state": "open",
            "base": {"ref": "main", "sha": "base-sha"},
            "head": {"sha": "head-sha"},
            "labels": [],
            "html_url": "https://example.test/acme/service/pull/1",
        }
        self.files = [
            {"filename": "src/main/java/com/acme/OrderController.java", "additions": 4, "deletions": 2},
            {"filename": "src/main/java/com/acme/UserService.java", "additions": 2, "deletions": 1},
        ]
        self.issue_comments: list[dict] = []
        self.review_comments: list[dict] = []
        self.reviews: list[dict] = []
        self.labels: list[dict] = []
        self._next_comment = 1
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        assert self._server is not None
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    @property
    def container_url(self) -> str:
        assert self._server is not None
        _, port = self._server.server_address
        return f"http://host.docker.internal:{port}"

    def start(self) -> "FakeGitHub":
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_: object) -> None:
                return

            def _body(self) -> dict:
                length = int(self.headers.get("Content-Length", "0"))
                return json.loads(self.rfile.read(length) or b"{}")

            def _json(self, status: int, value: object) -> None:
                data = json.dumps(value).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _path(self) -> tuple[str, str]:
                parsed = urlparse(self.path)
                return parsed.path, parsed.query

            def do_GET(self) -> None:  # noqa: N802
                path, _ = self._path()
                if path == "/repos/acme/service/pulls/1":
                    return self._json(200, fake.pull)
                if path == "/repos/acme/service/pulls/1/files":
                    return self._json(200, fake.files)
                if path == "/repos/acme/service/issues/1/comments":
                    return self._json(200, fake.issue_comments)
                if path == "/repos/acme/service/pulls/1/comments":
                    return self._json(200, fake.review_comments)
                if path == "/repos/acme/service/issues/1":
                    return self._json(200, {"number": 1, "labels": fake.pull["labels"]})
                if path == "/repos/acme/service/issues/2":
                    return self._json(200, {"number": 2, "title": "Order ownership", "body": "Only owners may read orders."})
                if path == "/repos/acme/service/labels":
                    return self._json(200, fake.labels)
                if path.startswith("/repos/acme/service/labels/"):
                    name = unquote(path.rsplit("/", 1)[-1])
                    for label in fake.labels:
                        if label["name"] == name:
                            return self._json(200, label)
                    return self._json(404, {"message": "Not Found"})
                return self._json(404, {"message": f"unhandled GET {path}"})

            def do_POST(self) -> None:  # noqa: N802
                path, _ = self._path()
                body = self._body()
                if path == "/repos/acme/service/issues/1/comments":
                    comment = {
                        "id": fake._next_comment,
                        "body": body.get("body", ""),
                        "html_url": f"https://example.test/comment/{fake._next_comment}",
                    }
                    fake._next_comment += 1
                    fake.issue_comments.append(comment)
                    return self._json(201, comment)
                if path == "/repos/acme/service/pulls/1/reviews":
                    review = {
                        "id": len(fake.reviews) + 1,
                        "body": body.get("body", ""),
                        "comments": body.get("comments", []),
                    }
                    fake.reviews.append(review)
                    for item in body.get("comments", []):
                        fake.review_comments.append(
                            {
                                "id": fake._next_comment,
                                "body": item.get("body", ""),
                                "path": item.get("path"),
                                "line": item.get("line"),
                                "start_line": item.get("start_line"),
                                "side": item.get("side"),
                            }
                        )
                        fake._next_comment += 1
                    return self._json(201, review)
                if path == "/repos/acme/service/labels":
                    label = {
                        "name": body.get("name"),
                        "color": body.get("color"),
                        "description": body.get("description"),
                    }
                    fake.labels.append(label)
                    return self._json(201, label)
                if path == "/repos/acme/service/issues/1/labels":
                    for name in body.get("labels", []):
                        if name not in [item["name"] for item in fake.pull["labels"]]:
                            fake.pull["labels"].append({"name": name})
                    return self._json(200, fake.pull["labels"])
                return self._json(404, {"message": f"unhandled POST {path}"})

            def do_PATCH(self) -> None:  # noqa: N802
                path, _ = self._path()
                body = self._body()
                if path.startswith("/repos/acme/service/issues/comments/"):
                    cid = int(path.rsplit("/", 1)[-1])
                    for comment in fake.issue_comments:
                        if comment["id"] == cid:
                            comment["body"] = body.get("body", comment["body"])
                            return self._json(200, comment)
                return self._json(404, {"message": f"unhandled PATCH {path}"})

            def do_DELETE(self) -> None:  # noqa: N802
                path, _ = self._path()
                if path.startswith("/repos/acme/service/issues/1/labels/"):
                    name = unquote(path.rsplit("/", 1)[-1])
                    fake.pull["labels"] = [item for item in fake.pull["labels"] if item["name"] != name]
                    self.send_response(204)
                    self.end_headers()
                    return None
                return self._json(404, {"message": f"unhandled DELETE {path}"})

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

    def __enter__(self) -> "FakeGitHub":
        return self.start()

    def __exit__(self, *_: object) -> None:
        self.stop()
