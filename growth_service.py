import json
import logging
import os
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


def _log_upstream_failure(response: requests.Response) -> None:
    # Never log upstream bodies, messages, headers or exception strings.
    LOGGER.error("Dify request failed: HTTP %s", response.status_code)


def _read_result(payload: Dict[str, Any]) -> Dict[str, str]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise GrowthServiceError("DIFY_RESULT_INVALID", "AI 返回格式不正确")
    data = payload["data"]
    outputs = data.get("outputs") or {}
    if not isinstance(outputs, dict):
        raise GrowthServiceError("DIFY_RESULT_INVALID", "AI 返回格式不正确")
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

    missing = [field for field in REQUIRED_FIELDS if not isinstance(result.get(field), str) or not result[field].strip()]
    if missing:
        raise GrowthServiceError(
            "DIFY_RESULT_FIELDS_INVALID",
            "Dify result is missing required fields: " + ", ".join(missing),
        )
    return {field: result[field].strip() for field in REQUIRED_FIELDS}


def generate_growth(user_message: str) -> Dict[str, str]:
    if not isinstance(user_message, str) or not user_message.strip():
        raise GrowthServiceError("USER_MESSAGE_REQUIRED", "请输入今天发生的内容", 400)

    if len(user_message) > 2000:
        raise GrowthServiceError("USER_MESSAGE_TOO_LONG", "请控制在 2000 字以内", 400)

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
        LOGGER.error("Dify request failed before response")
        raise GrowthServiceError("DIFY_NETWORK_ERROR", "暂时无法连接 AI 服务", 502) from exc
    finally:
        session.close()

    if not 200 <= response.status_code < 300:
        _log_upstream_failure(response)
        raise GrowthServiceError("DIFY_UPSTREAM_ERROR", "AI 服务暂时不可用，请稍后再试", 502)

    try:
        response_payload = response.json()
    except ValueError as exc:
        raise GrowthServiceError("DIFY_RESPONSE_INVALID", "Dify 返回的不是 JSON", 502) from exc
    result = _read_result(response_payload)
    return {field: value.replace(api_key, "[REDACTED]") for field, value in result.items()}

