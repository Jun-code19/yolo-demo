"""检测任务 VLM 管道执行器（单设备 / 分组共用）"""
import json
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import cv2

from src.data_pusher import data_pusher
from src.database import DetectionConfig, DetectionEvent, EventStatus, SaveMode, SessionLocal
from src.inference_pipeline.orchestrator import VlmPipelineRuntime
from src.inference_pipeline.pipeline_config import is_vlm_pipeline_enabled
from src.inference_pipeline.yolo_vlm_stage import (
    pick_verify_candidates,
    run_yolo_analyze,
    run_yolo_verify,
)

logger = logging.getLogger(__name__)


def _model_cache_fingerprint(model_record) -> str:
    params = model_record.parameters or {}
    if isinstance(params, str):
        raw = params
    else:
        raw = json.dumps(params, sort_keys=True, default=str)
    upload_time = getattr(model_record, "upload_time", None)
    return f"{model_record.models_id}:{raw}:{upload_time}"


class DetectionVlmRunner:
    """YOLO 初筛后异步调用 VLM（verify / analyze），确认后入库并推送"""

    def __init__(
        self,
        config_id: str,
        inference_pipeline: dict,
        save_mode,
        target_class: List[str],
        stream_type: str = "main",
        area_coordinates: Optional[dict] = None,
        group_id: Optional[str] = None,
        group_name: Optional[str] = None,
    ):
        self.config_id = config_id
        self.inference_pipeline = inference_pipeline or {}
        self.save_mode = save_mode
        self.target_class = target_class or []
        self.stream_type = stream_type or "main"
        self.area_coordinates = area_coordinates
        self.group_id = group_id
        self.group_name = group_name
        self.vlm_runtime = (
            VlmPipelineRuntime(self.inference_pipeline)
            if is_vlm_pipeline_enabled(self.inference_pipeline)
            else None
        )
        self.vlm_executor = ThreadPoolExecutor(max_workers=1) if self.vlm_runtime else None
        self._vlm_model_record = None
        self._vlm_model_fingerprint = None

    @property
    def enabled(self) -> bool:
        return self.vlm_runtime is not None

    def shutdown(self):
        if self.vlm_executor:
            self.vlm_executor.shutdown(wait=False)

    def invalidate_vlm_model_cache(self):
        self._vlm_model_record = None
        self._vlm_model_fingerprint = None

    def submit(
        self,
        frame,
        detections,
        speed: float = 0.0,
        device_id: str = "",
        device_name: str = "",
        device_ip: str = "",
        push_label: str = "",
    ):
        if not detections or not self.vlm_runtime or not self.vlm_executor:
            return
        self.vlm_executor.submit(
            self._run_worker,
            frame.copy(),
            [dict(d) for d in detections],
            speed,
            device_id,
            device_name,
            device_ip,
            push_label or "",
        )

    def _load_vlm_model(self, force_refresh: bool = False):
        vlm_id = self.inference_pipeline.get("vlm_model_id")
        if not vlm_id:
            return None
        db = SessionLocal()
        try:
            from src.database import DetectionModel

            row = db.query(DetectionModel).filter(DetectionModel.models_id == vlm_id).first()
            if not row or row.models_type != "vlm":
                logger.error("未找到 VLM 模型或类型不正确: %s", vlm_id)
                self.invalidate_vlm_model_cache()
                return None
            if not row.is_active:
                logger.warning("VLM 模型未激活: %s", vlm_id)

            fingerprint = _model_cache_fingerprint(row)
            if (
                not force_refresh
                and self._vlm_model_record is not None
                and self._vlm_model_fingerprint == fingerprint
            ):
                return self._vlm_model_record

            self._vlm_model_record = row
            self._vlm_model_fingerprint = fingerprint
            return row
        finally:
            db.close()

    @staticmethod
    def _is_auth_error(error_text: str) -> bool:
        if not error_text:
            return False
        lower = error_text.lower()
        return any(
            token in lower
            for token in ("api key", "unauthorized", "401", "authentication", "invalid key")
        )

    def _run_worker(
        self,
        frame,
        detections,
        speed,
        device_id,
        device_name,
        device_ip,
        push_label,
    ):
        try:
            if self.vlm_runtime.is_verify:
                self._run_verify_worker(
                    frame, detections, speed, device_id, device_name, device_ip, push_label
                )
            elif self.vlm_runtime.is_analyze:
                self._run_analyze_worker(
                    frame, detections, speed, device_id, device_name, device_ip, push_label
                )
        except Exception as exc:
            logger.error("VLM 管道执行失败: %s", exc)

    def _run_verify_worker(
        self, frame, detections, speed, device_id, device_name, device_ip, push_label
    ):
        candidates = pick_verify_candidates(detections)
        if not candidates:
            return

        for candidate in candidates:
            if not self.vlm_runtime.can_run():
                break

            model = self._load_vlm_model()
            if not model:
                return

            self.vlm_runtime.mark_ran()
            pipeline_result = run_yolo_verify(frame, candidate, model, self.inference_pipeline)
            error_text = pipeline_result.get("error") or ""
            if self._is_auth_error(error_text):
                self.invalidate_vlm_model_cache()
                self._load_vlm_model(force_refresh=True)

            if not pipeline_result.get("ok") or not pipeline_result.get("result", {}).get("verified"):
                logger.debug(
                    "VLM 复检未通过: %s",
                    error_text or pipeline_result.get("result", {}).get("reason"),
                )
                continue

            self._save_event(frame, [candidate], pipeline_result, "yolo_verify", device_id)
            self._push_data(
                [candidate],
                frame,
                speed,
                pipeline_result,
                "yolo_verify",
                device_id,
                device_name,
                device_ip,
                push_label,
            )

    def _run_analyze_worker(
        self, frame, detections, speed, device_id, device_name, device_ip, push_label
    ):
        if not self.vlm_runtime.can_run():
            return

        model = self._load_vlm_model()
        if not model:
            return

        self.vlm_runtime.mark_ran()
        pipeline_result = run_yolo_analyze(frame, detections, model, self.inference_pipeline)
        error_text = pipeline_result.get("error") or ""
        if self._is_auth_error(error_text):
            self.invalidate_vlm_model_cache()
            self._load_vlm_model(force_refresh=True)

        if not pipeline_result.get("ok"):
            logger.warning("VLM 分析失败: %s", error_text)
            return

        vlm_result = pipeline_result.get("result") or {}
        if not vlm_result.get("needs_alert"):
            return

        self._save_event(frame, detections, pipeline_result, "yolo_analyze", device_id)
        self._push_data(
            detections,
            frame,
            speed,
            pipeline_result,
            "yolo_analyze",
            device_id,
            device_name,
            device_ip,
            push_label,
        )

    def _save_event(self, frame, detections, pipeline_result, event_type, device_id):
        try:
            db = SessionLocal()
            event_id = str(uuid.uuid4())
            current_time = datetime.now()

            config = db.query(DetectionConfig).filter(DetectionConfig.config_id == self.config_id).first()
            if not config:
                logger.error("未找到检测配置: %s", self.config_id)
                return

            vlm_result = pipeline_result.get("result") or {}
            max_conf = max([d["confidence"] for d in detections]) if detections else 0.0
            if event_type == "yolo_analyze" and vlm_result.get("findings"):
                max_conf = max(
                    max_conf,
                    max(float(f.get("confidence") or 0) for f in vlm_result["findings"]),
                )

            event = DetectionEvent(
                event_id=event_id,
                config_id=self.config_id,
                device_id=device_id,
                timestamp=current_time,
                event_type=event_type,
                confidence=max_conf,
                bounding_box=detections,
                status=EventStatus.new,
                created_at=current_time,
            )

            summary = vlm_result.get("summary") or vlm_result.get("reason") or ""
            if event_type == "yolo_verify":
                desc = f"VLM 复检通过: {summary or detections[0].get('class_name', '目标')}"
            else:
                labels = vlm_result.get("alert_labels") or []
                desc = summary or f"VLM 分析告警: {', '.join(labels)}"

            meta = {
                "current_count": len(detections),
                "target_class": self.target_class,
                "event_description": desc,
                "pipeline_mode": self.inference_pipeline.get("mode"),
                "vlm": {
                    "model_id": self.inference_pipeline.get("vlm_model_id"),
                    "prompt_id": self.inference_pipeline.get("prompt_id"),
                    "latency_ms": pipeline_result.get("latency_ms") or 0,
                    "result": vlm_result,
                },
                "yolo": {
                    "detections": [
                        {
                            "class_name": d.get("class_name"),
                            "confidence": d.get("confidence"),
                            "bbox": d.get("bbox"),
                        }
                        for d in detections
                    ]
                },
            }
            if self.group_id:
                meta["group_id"] = self.group_id
                meta["group_name"] = self.group_name or ""
            event.meta_data = meta

            if self.save_mode in [SaveMode.screenshot, SaveMode.both]:
                save_dir = Path(f"storage/events/{current_time.strftime('%Y-%m-%d')}/{device_id}")
                save_dir.mkdir(parents=True, exist_ok=True, mode=0o777)
                thumbnail_path = save_dir / f"{event_id}.jpg"
                quality = 100 if self.stream_type == "sub" else 70
                cv2.imwrite(str(thumbnail_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
                event.thumbnail_path = str(thumbnail_path)

            db.add(event)
            db.commit()
            logger.info("已保存 VLM 管道事件: %s (%s) device=%s", event_id, event_type, device_id)
        except Exception as exc:
            logger.error("保存 VLM 事件失败: %s", exc)
            if "db" in locals() and db:
                db.rollback()
        finally:
            if "db" in locals() and db:
                db.close()

    def _push_data(
        self,
        detections,
        frame_rgb,
        speed,
        pipeline_result,
        event_type,
        device_id,
        device_name,
        device_ip,
        push_label,
    ):
        if not data_pusher.push_configs:
            return

        effective_push_label = push_label
        if not effective_push_label and self.area_coordinates:
            effective_push_label = self.area_coordinates.get("pushLabel") or ""

        vlm_result = pipeline_result.get("result") or {}
        push_data = {
            "cameraInfo": f"{device_name}:{device_ip}",
            "deviceId": device_id,
            "stayingCount": len(detections),
            "recordTime": datetime.now().isoformat() + "+08:00",
            "event_description": event_type,
            "pipeline_mode": self.inference_pipeline.get("mode"),
            "vlm_summary": vlm_result.get("summary") or vlm_result.get("reason") or "",
            "vlm_alert_labels": vlm_result.get("alert_labels") or [],
        }
        if self.group_id:
            push_data["groupId"] = self.group_id
            push_data["groupName"] = self.group_name or ""

        tags = [f"device_{device_id}"]
        if self.group_id:
            tags.insert(0, f"group_{self.group_id}")
        if effective_push_label:
            tags.insert(0, effective_push_label)
        data_pusher.push_data(
            data=push_data,
            image=frame_rgb,
            tags=tags,
            config_id=self.config_id,
        )
