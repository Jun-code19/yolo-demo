"""Qwen-VL（DashScope OpenAI 兼容接口）"""
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen-vl-plus"


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
    return None


def _resolve_api_key(parameters: Optional[Dict[str, Any]]) -> str:
    params = parameters or {}
    api_key = (params.get("api_key") or "").strip()
    if api_key.startswith("env:"):
        api_key = os.getenv(api_key.split(":", 1)[1], "").strip()
    if not api_key:
        api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    return api_key


def _infer_supports_vision(base_url: str, explicit: Optional[bool] = None) -> bool:
    if explicit is False:
        return False
    if "deepseek.com" in (base_url or "").lower():
        return False
    return True


def _vision_unsupported_message(base_url: str) -> str:
    if "deepseek.com" in (base_url or "").lower():
        return (
            "DeepSeek 官方 API（deepseek-chat / deepseek-v4 等）仅支持纯文本，不支持 image_url 传图。"
            "VLM 巡检请改用 Qwen-VL、GPT-4o、GLM-4V 或本地 Ollama（llava）等视觉模型。"
        )
    return "该接口不支持多模态 image_url 传图，请更换支持视觉的 VLM 模型。"


def _supports_vision(parameters: Optional[Dict[str, Any]]) -> bool:
    params = parameters or {}
    return _infer_supports_vision(params.get("base_url") or "", params.get("supports_vision"))


def _format_http_error(status_code: int, text: str, base_url: str) -> str:
    lower = (text or "").lower()
    if status_code == 400 and ("image_url" in lower or "unknown variant" in lower):
        return _vision_unsupported_message(base_url)
    return f"HTTP {status_code}: {(text or '')[:500]}"


def is_api_key_configured(parameters: Optional[Dict[str, Any]]) -> bool:
    params = parameters or {}
    if params.get("api_key_required") is False:
        return True
    return bool(_resolve_api_key(parameters))


class QwenVlProvider:
    def __init__(self, model_record):
        self.model_record = model_record
        params = model_record.parameters or {}
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except json.JSONDecodeError:
                params = {}
        self.parameters = params
        self.base_url = (params.get("base_url") or DEFAULT_BASE_URL).rstrip("/")
        self.model_name = params.get("model_name") or model_record.models_name or DEFAULT_MODEL
        self.timeout_sec = int(params.get("timeout_sec") or 60)

    def inspect_image(
        self,
        image_base64: str,
        system_prompt: str,
        user_prompt: str,
    ) -> Dict[str, Any]:
        api_key = _resolve_api_key(self.parameters)
        api_key_required = self.parameters.get("api_key_required", True)
        if api_key_required is not False and not api_key:
            return {
                "ok": False,
                "error": "未配置 API Key 或模型 parameters.api_key（本地 Ollama 可设 api_key_required=false）",
                "latency_ms": 0,
                "parsed": None,
                "raw_text": "",
            }

        if not _supports_vision(self.parameters):
            return {
                "ok": False,
                "error": _vision_unsupported_message(self.base_url),
                "latency_ms": 0,
                "parsed": None,
                "raw_text": "",
            }

        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                        },
                        {"type": "text", "text": user_prompt},
                    ],
                },
            ],
            "temperature": float(self.parameters.get("temperature") or 0.2),
        }

        start = time.time()
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout_sec)
            latency_ms = int((time.time() - start) * 1000)
            if resp.status_code != 200:
                return {
                    "ok": False,
                    "error": _format_http_error(resp.status_code, resp.text, self.base_url),
                    "latency_ms": latency_ms,
                    "parsed": None,
                    "raw_text": resp.text[:2000],
                }

            data = resp.json()
            choices = data.get("choices") or []
            content = ""
            if choices:
                message = choices[0].get("message") or {}
                content = message.get("content") or ""
            parsed = _extract_json(content)
            return {
                "ok": parsed is not None,
                "error": None if parsed is not None else "VLM 返回无法解析为 JSON",
                "latency_ms": latency_ms,
                "parsed": parsed,
                "raw_text": content,
            }
        except requests.Timeout:
            return {
                "ok": False,
                "error": f"VLM 请求超时 ({self.timeout_sec}s)",
                "latency_ms": int((time.time() - start) * 1000),
                "parsed": None,
                "raw_text": "",
            }
        except Exception as exc:
            logger.exception("Qwen-VL 调用失败")
            return {
                "ok": False,
                "error": str(exc),
                "latency_ms": int((time.time() - start) * 1000),
                "parsed": None,
                "raw_text": "",
            }


def get_vlm_provider(model_record):
    params = model_record.parameters or {}
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except json.JSONDecodeError:
            params = {}
    provider = (params.get("provider") or "qwen_vl").lower()
    if provider in ("qwen_vl", "openai_compatible", "dashscope"):
        return QwenVlProvider(model_record)
    return QwenVlProvider(model_record)
