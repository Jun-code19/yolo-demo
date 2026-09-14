"""Prompt 模板：内置 registry.json + 可写 registry.custom.json"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
BUILTIN_REGISTRY_PATH = PROMPTS_DIR / "registry.json"
CUSTOM_REGISTRY_PATH = Path(
    os.getenv("PROMPT_REGISTRY_CUSTOM_PATH", str(PROMPTS_DIR / "registry.custom.json"))
)

PROMPT_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
DEFAULT_SCOPES = ["vlm_inspection", "detection_pipeline"]
PROMPT_BODY_KEYS = (
    "name",
    "description",
    "default_alert_labels",
    "system",
    "user_template",
    "scopes",
)


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(path)


def load_builtin_registry() -> Dict[str, Any]:
    return _read_json(BUILTIN_REGISTRY_PATH)


def load_custom_registry() -> Dict[str, Any]:
    return _read_json(CUSTOM_REGISTRY_PATH)


def load_prompt_registry() -> Dict[str, Any]:
    """合并内置与自定义，同 id 时自定义覆盖。"""
    merged = dict(load_builtin_registry())
    merged.update(load_custom_registry())
    return merged


def is_builtin_prompt(prompt_id: str) -> bool:
    return prompt_id in load_builtin_registry()


def _normalize_scopes(meta: Dict[str, Any]) -> List[str]:
    scopes = meta.get("scopes")
    if isinstance(scopes, list) and scopes:
        return [str(s) for s in scopes]
    return list(DEFAULT_SCOPES)


def _prompt_matches_scope(meta: Dict[str, Any], scope: Optional[str]) -> bool:
    if not scope:
        return True
    return scope in _normalize_scopes(meta)


def _public_list_item(prompt_id: str, meta: Dict[str, Any], include_detail: bool) -> Dict[str, Any]:
    item = {
        "prompt_id": prompt_id,
        "name": meta.get("name") or prompt_id,
        "description": meta.get("description") or "",
        "default_alert_labels": meta.get("default_alert_labels") or [],
        "scopes": _normalize_scopes(meta),
        "builtin": is_builtin_prompt(prompt_id),
        "editable": not is_builtin_prompt(prompt_id),
    }
    if include_detail:
        item["system"] = meta.get("system") or ""
        item["user_template"] = meta.get("user_template") or ""
    return item


def list_prompt_templates(scope: Optional[str] = None, include_detail: bool = False) -> List[Dict[str, Any]]:
    registry = load_prompt_registry()
    items = []
    for prompt_id, meta in registry.items():
        if not isinstance(meta, dict):
            continue
        if not _prompt_matches_scope(meta, scope):
            continue
        items.append(_public_list_item(prompt_id, meta, include_detail))
    items.sort(key=lambda x: (not x["builtin"], x["name"]))
    return items


def get_prompt_template(prompt_id: str) -> Dict[str, Any]:
    registry = load_prompt_registry()
    meta = registry.get(prompt_id)
    if not meta or not isinstance(meta, dict):
        raise KeyError(prompt_id)
    return _public_list_item(prompt_id, meta, include_detail=True)


def validate_prompt_id(prompt_id: str) -> None:
    if not PROMPT_ID_PATTERN.match(prompt_id):
        raise ValueError(
            "prompt_id 须为小写字母开头，仅含 a-z、0-9、下划线，长度 3~64"
        )


def validate_prompt_body(body: Dict[str, Any]) -> Dict[str, Any]:
    name = (body.get("name") or "").strip()
    if not name:
        raise ValueError("name 不能为空")
    system = (body.get("system") or "").strip()
    user_template = (body.get("user_template") or "").strip()
    if not system or not user_template:
        raise ValueError("system 与 user_template 不能为空")
    labels = body.get("default_alert_labels")
    if labels is None:
        labels = []
    if not isinstance(labels, list):
        raise ValueError("default_alert_labels 须为数组")
    scopes = body.get("scopes")
    if scopes is None:
        scopes = list(DEFAULT_SCOPES)
    if not isinstance(scopes, list) or not scopes:
        raise ValueError("scopes 须为非空数组")
    for s in scopes:
        if s not in ("vlm_inspection", "detection_pipeline"):
            raise ValueError("scopes 仅支持 vlm_inspection、detection_pipeline")
    return {
        "name": name,
        "description": (body.get("description") or "").strip(),
        "default_alert_labels": [str(x).strip() for x in labels if str(x).strip()],
        "system": system,
        "user_template": user_template,
        "scopes": scopes,
    }


def create_custom_prompt(prompt_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    validate_prompt_id(prompt_id)
    if is_builtin_prompt(prompt_id):
        raise ValueError("与内置模板 id 冲突，请更换 prompt_id")
    custom = load_custom_registry()
    if prompt_id in custom:
        raise ValueError("prompt_id 已存在")
    custom[prompt_id] = validate_prompt_body(body)
    _write_json(CUSTOM_REGISTRY_PATH, custom)
    return get_prompt_template(prompt_id)


def update_custom_prompt(prompt_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    if is_builtin_prompt(prompt_id):
        raise ValueError("内置模板不可修改，请复制为新 id 后编辑")
    custom = load_custom_registry()
    if prompt_id not in custom:
        raise KeyError(prompt_id)
    custom[prompt_id] = validate_prompt_body(body)
    _write_json(CUSTOM_REGISTRY_PATH, custom)
    return get_prompt_template(prompt_id)


def delete_custom_prompt(prompt_id: str) -> None:
    if is_builtin_prompt(prompt_id):
        raise ValueError("内置模板不可删除")
    custom = load_custom_registry()
    if prompt_id not in custom:
        raise KeyError(prompt_id)
    del custom[prompt_id]
    _write_json(CUSTOM_REGISTRY_PATH, custom)


def export_custom_registry() -> Dict[str, Any]:
    return load_custom_registry()


def import_custom_registry(payload: Dict[str, Any], merge: bool = True) -> int:
    if not isinstance(payload, dict):
        raise ValueError("导入内容须为 JSON 对象")
    custom = load_custom_registry() if merge else {}
    count = 0
    for prompt_id, meta in payload.items():
        if not isinstance(meta, dict):
            continue
        validate_prompt_id(prompt_id)
        if is_builtin_prompt(prompt_id):
            continue
        custom[prompt_id] = validate_prompt_body(meta)
        count += 1
    _write_json(CUSTOM_REGISTRY_PATH, custom)
    return count
