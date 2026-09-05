import json
import logging
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse

from growth_service import DifyNotConfigured, GrowthServiceError, generate_growth


ROOT = Path(__file__).resolve().parent
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def load_local_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def write_json(handler: SimpleHTTPRequestHandler, status: int, payload: Dict[str, Any]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/growth":
            write_json(self, 404, {"code": "NOT_FOUND", "message": "接口不存在"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            result = generate_growth(body.get("user_message", ""))
            write_json(self, 200, {"ok": True, **result})
        except DifyNotConfigured:
            write_json(
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
            write_json(self, exc.status, {"ok": False, "code": exc.code, "message": exc.message})
        except (json.JSONDecodeError, UnicodeDecodeError):
            write_json(self, 400, {"ok": False, "code": "INVALID_JSON", "message": "请求格式不正确"})
        except Exception:
            logging.exception("Unexpected local API error")
            write_json(self, 500, {"ok": False, "code": "INTERNAL_ERROR", "message": "服务暂时不可用"})

    def log_message(self, format: str, *args: Any) -> None:
        logging.info("%s - %s", self.address_string(), format % args)


if __name__ == "__main__":
    load_local_env()
    port = int(os.getenv("PORT", "8080"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Proof of Growth running at http://127.0.0.1:{port}/")
    server.serve_forever()

