import json
import os
from http.server import BaseHTTPRequestHandler
from typing import Any, Dict

from growth_service import DifyNotConfigured, GrowthServiceError, generate_growth


def send_json(handler: BaseHTTPRequestHandler, status: int, payload: Dict[str, Any]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


class handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            result = generate_growth(body.get("user_message", ""))
            send_json(self, 200, {"ok": True, **result})
        except DifyNotConfigured:
            send_json(
                self,
                503,
                {
                    "ok": False,
                    "fallback": True,
                    "code": "DIFY_API_KEY_NOT_CONFIGURED",
                    "message": "未配置 DIFY_API_KEY，请使用本地模拟数据",
                },
            )
        except GrowthServiceError as exc:
            send_json(self, exc.status, {"ok": False, "code": exc.code, "message": exc.message})
        except (json.JSONDecodeError, UnicodeDecodeError):
            send_json(self, 400, {"ok": False, "code": "INVALID_JSON", "message": "请求格式不正确"})
        except Exception:
            send_json(self, 500, {"ok": False, "code": "INTERNAL_ERROR", "message": "服务暂时不可用"})

    def do_GET(self) -> None:
        send_json(self, 405, {"ok": False, "code": "METHOD_NOT_ALLOWED", "message": "请使用 POST"})

