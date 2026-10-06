"""Deterministic Fake OpenAI-Compatible HTTP Server Fixture for Unit & Integration Tests.

Runs an in-process Python HTTP server on an ephemeral localhost port.
Allows deterministic testing of:
- Standard chat completions
- Structured JSON outputs
- Discovery success and failure (404)
- Authentication failure (401)
- Rate limiting (429 with Retry-After)
- Service unavailable (503)
- Corrupt JSON output
"""

import http.server
import json
import threading
import time
from typing import Optional, Tuple


class FakeOpenAIHandler(http.server.BaseHTTPRequestHandler):
    """Handler supporting customizable response scenarios."""

    # Configurable test scenario overrides
    scenario: str = "normal"  # "normal", "auth_fail", "rate_limit", "server_error", "corrupt_json", "no_models"
    retry_after: int = 1

    def log_message(self, format, *args):
        # Suppress standard HTTP server logging during test runs
        pass

    def do_GET(self):
        """Handles GET requests (e.g. /models or /api/tags)."""
        if self.path.endswith("/models"):
            if self.scenario == "no_models":
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Not Found")
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "object": "list",
                "data": [
                    {"id": "test-mock-model", "object": "model"},
                    {"id": "llama3.1:8b", "object": "model"},
                    {"id": "gpt-4o-mini", "object": "model"},
                ]
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        if self.path.endswith("/api/tags"):
            if self.scenario == "no_models":
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Not Found")
                return

            # Ollama tags simulation
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "models": [
                    {"name": "llama3.1:8b", "size": 4700000000},
                    {"name": "qwen2.5:7b", "size": 4400000000},
                ]
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        """Handles POST requests (/chat/completions)."""
        content_len = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_len) if content_len > 0 else b"{}"

        # 1. Auth failure check
        auth_header = self.headers.get("Authorization", "")
        if self.scenario == "auth_fail" or auth_header == "Bearer invalid_key":
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": {"message": "Invalid API key", "type": "invalid_request_error"}}).encode("utf-8"))
            return

        # 2. Rate limit check
        if self.scenario == "rate_limit":
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.send_header("Retry-After", str(self.retry_after))
            self.end_headers()
            self.wfile.write(json.dumps({"error": {"message": "Rate limit reached", "type": "rate_limit_error"}}).encode("utf-8"))
            return

        # 3. Server error check
        if self.scenario == "server_error":
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": {"message": "Overloaded", "type": "server_error"}}).encode("utf-8"))
            return

        # 4. Corrupt JSON
        if self.scenario == "corrupt_json":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"<html>This is not JSON</html>")
            return

        # 5. Normal chat completion or structured output
        try:
            req_data = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            req_data = {}

        messages = req_data.get("messages", [])
        prompt_content = messages[-1].get("content", "") if messages else ""
        system_content = messages[0].get("content", "") if messages and messages[0].get("role") == "system" else ""

        # Check if structured JSON was requested
        is_structured = "JSON" in system_content or "schema" in prompt_content.lower() or req_data.get("response_format", {}).get("type") == "json_object"

        if is_structured:
            if "malformed_output" in prompt_content:
                reply = "```json\n{ key_with_missing_quotes: true }\n```"
            else:
                reply = json.dumps({
                    "semantic_score": 85,
                    "additional_positive_reasons": ["Solid experience", "Strong skills"],
                    "additional_negative_reasons": [],
                    "semantic_summary": "Candidate matches requirements well."
                })
        else:
            if "ping" in prompt_content.lower():
                reply = "OK"
            else:
                reply = "Simulated AI completion response."

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        resp = {
            "id": "chatcmpl-mock-12345",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": req_data.get("model", "test-mock-model"),
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": reply,
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 15,
                "completion_tokens": 20,
                "total_tokens": 35
            }
        }
        self.wfile.write(json.dumps(resp).encode("utf-8"))


class FakeOpenAIServer:
    """Manager to spin up and tear down the background test HTTP server."""

    def __init__(self, port: int = 0):
        self.server = http.server.HTTPServer(("127.0.0.1", port), FakeOpenAIHandler)
        self.port = self.server.server_port
        self.base_url = f"http://127.0.0.1:{self.port}/v1"
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        if self._thread:
            self._thread.join(timeout=1.0)

    def set_scenario(self, scenario: str, retry_after: int = 1):
        FakeOpenAIHandler.scenario = scenario
        FakeOpenAIHandler.retry_after = retry_after
