import json
import logging
import os
import re
from typing import Any, Dict

import requests


LOGGER = logging.getLogger("proof_of_growth.dify")
DIFY_WORKFLOW_URL = "https://api.dify.ai/v1/workflows/run"
REQUIRED_FIELDS = ("emotion", "reply", "growth_title", "growth_summary")


class DifyNotConfigured(Exception):
    pass


class GrowthServiceError(Exception):
    def __init__(self, code: str, message: str, status: int = 502):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _safe_text(value: Any, limit: int = 1200) -> str:
    """Keep upstream diagnostics useful without ever logging credentials."""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = re.sub(
        r"(?i)(authorization|api[-_ ]?key|access[-_ ]?token|secret|password)"
        r"\s*[:=]\s*[^,\s}\]]+",
        r"\1=[REDACTED]",
        text,
    )
    return text[:limit]


def _log_upstream_failure(response: requests.Response) -> None:
    details: Dict[str, Any] = {"status": response.status_code}
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        for key in ("code", "message", "error", "status", "title"):
            if key in payload:
                details[key] = _safe_text(payload[key], 500)
    details["body"] = _safe_text(response.text)
    LOGGER.error("Dify request failed: %s", json.dumps(details, ensure_ascii=False))


def _read_result(payload: Dict[str, Any]) -> Dict[str, str]:
    data = payload.get("data") or {}
    outputs = data.get("outputs") or {}
    result = outputs.get("result")

    # Keep compatibility with workflows that expose the same JSON under text.
    if result is None:
        result = outputs.get("text")
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError as exc:
            raise GrowthServiceError(
                "DIFY_RESULT_INVALID",
                "Dify result is not valid JSON",
            ) from exc

    if not isinstance(result, dict):
        raise GrowthServiceError(
            "DIFY_RESULT_INVALID",
            "Dify result must be a JSON object",
        )

    missing = [field for field in REQUIRED_FIELDS if not isinstance(result.get(field), str)]
    if missing:
        raise GrowthServiceError(
            "DIFY_RESULT_FIELDS_INVALID",
            "Dify result is missing required fields: " + ", ".join(missing),
        )
    return {field: result[field].strip() for field in REQUIRED_FIELDS}


def generate_growth(user_message: str) -> Dict[str, str]:
    if not isinstance(user_message, str) or not user_message.strip():
        raise GrowthServiceError("USER_MESSAGE_REQUIRED", "请输入今天发生的内容", 400)

    api_key = os.getenv("DIFY_API_KEY", "").strip()
    if not api_key:
        raise DifyNotConfigured()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Proof-of-Growth/1.0",
    }
    body = {
        "inputs": {"user_message": user_message.strip()},
        "response_mode": "blocking",
        "user": "level1-demo-user",
    }

    session = requests.Session()
    try:
        response = session.post(
            DIFY_WORKFLOW_URL,
            headers=headers,
            json=body,
            timeout=45,
        )
    except requests.RequestException as exc:
        LOGGER.error("Dify request failed before response: %s", _safe_text(str(exc), 500))
        raise GrowthServiceError("DIFY_NETWORK_ERROR", "暂时无法连接 AI 服务", 502) from exc

    if not 200 <= response.status_code < 300:
        _log_upstream_failure(response)
        try:
            upstream = response.json()
        except ValueError:
            upstream = {}
        code = upstream.get("code") if isinstance(upstream, dict) else None
        message = upstream.get("message") if isinstance(upstream, dict) else None
        safe_message = _safe_text(message or f"Dify HTTP {response.status_code}", 300)
        raise GrowthServiceError(
            str(code or "DIFY_UPSTREAM_ERROR"),
            safe_message,
            response.status_code if response.status_code < 500 else 502,
        )

    try:
        response_payload = response.json()
    except ValueError as exc:
        raise GrowthServiceError("DIFY_RESPONSE_INVALID", "Dify 返回的不是 JSON", 502) from exc
    return _read_result(response_payload)

