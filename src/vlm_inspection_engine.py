"""VLM 巡检引擎：定时截图 → Qwen-VL 分析"""
import logging
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from src.database import (
    SessionLocal,
    Device,
    DetectionModel,
    VlmInspectionJob,
    VlmInspectionRun,
    VlmInspectionFinding,
    VlmInspectionAlertCooldown,
)
from src.detection_runtime import extract_runtime_config, is_within_active_period
from src.data_pusher import data_pusher
from src.frame_acquisition import frame_acquisition
from src.inference_pipeline.payload_builder import save_snapshot
from src.inference_pipeline.vlm_only_stage import run_vlm_only_inspection
from src.vlm_inspection_job_utils import (
    normalize_group_settings,
    normalize_vlm_config,
    resolve_inspection_devices,
)

logger = logging.getLogger(__name__)


class VlmInspectionEngine:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.inspection_jobs: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.RLock()
        self._running_jobs: Dict[str, str] = {}

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("VLM 巡检调度器已启动")

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("VLM 巡检调度器已停止")

    def get_inspection_jobs(self):
        with self.lock:
            return list(self.inspection_jobs.values())

    def is_job_running(self, job_id: str) -> bool:
        with self.lock:
            return job_id in self._running_jobs

    def _try_acquire_run(self, job_id: str, run_id: str) -> bool:
        with self.lock:
            if job_id in self._running_jobs:
                return False
            self._running_jobs[job_id] = run_id
            return True

    def _release_run(self, job_id: str, run_id: str) -> None:
        with self.lock:
            if self._running_jobs.get(job_id) == run_id:
                del self._running_jobs[job_id]

    def add_inspection_job(self, job_id: str):
        db = SessionLocal()
        try:
            job = db.query(VlmInspectionJob).filter(VlmInspectionJob.job_id == job_id).first()
            if not job:
                logger.error("未找到 VLM 巡检任务: %s", job_id)
                return None

            interval = job.interval or 300
            self.scheduler.add_job(
                self.run_inspection,
                trigger=IntervalTrigger(seconds=interval),
                args=[job_id],
                id=job_id,
                replace_existing=True,
            )

            job_details = {
                "job_id": job_id,
                "job_name": job.job_name,
                "interval": interval,
                "status": "scheduled",
                "last_run": None,
                "last_result": None,
                "last_error": None,
            }
            with self.lock:
                self.inspection_jobs[job_id] = job_details
            logger.info("VLM 巡检任务已加入调度: %s", job_id)
            return job_details
        finally:
            db.close()

    def remove_inspection_job(self, job_id: str):
        try:
            self.scheduler.remove_job(job_id)
        except Exception:
            pass
        with self.lock:
            if job_id in self.inspection_jobs:
                self.inspection_jobs[job_id]["status"] = "paused"
                del self.inspection_jobs[job_id]
        logger.info("VLM 巡检任务已移除: %s", job_id)
        return True

    def run_inspection(self, job_id: str, manual: bool = False) -> Optional[Dict[str, Any]]:
        """执行一轮巡检（定时/手动统一入口，同 job 互斥）"""
        run_id = str(uuid.uuid4())
        if not self._try_acquire_run(job_id, run_id):
            if manual:
                return {"ok": False, "error": "already_running"}
            logger.info("VLM 巡检跳过（同任务仍在执行）: %s", job_id)
            return None
        try:
            return self._run_inspection(job_id, manual, run_id)
        finally:
            self._release_run(job_id, run_id)

    def _is_job_stopped(self, db: Session, job_id: str) -> bool:
        job = db.query(VlmInspectionJob).filter(VlmInspectionJob.job_id == job_id).first()
        if not job or not job.is_active:
            return True
        with self.lock:
            return job_id not in self.inspection_jobs

    def _run_inspection(self, job_id: str, manual: bool, run_id: str):
        db = SessionLocal()
        run = None
        stopped_early = False
        success_count = 0
        fail_count = 0
        alert_count = 0
        device_ids = []

        try:
            job = db.query(VlmInspectionJob).filter(VlmInspectionJob.job_id == job_id).first()
            if not job:
                logger.error("未找到 VLM 巡检任务: %s", job_id)
                return None

            if not manual and self._is_job_stopped(db, job_id):
                return None

            runtime = extract_runtime_config(job.schedule_config)
            if not manual and not is_within_active_period(datetime.now(), runtime):
                with self.lock:
                    if job_id in self.inspection_jobs:
                        self.inspection_jobs[job_id]["status"] = "scheduled"
                return None

            device_ids = resolve_inspection_devices(db, job)
            if not device_ids:
                self._set_job_error(db, job_id, "没有可用的监控设备")
                return None

            model = db.query(DetectionModel).filter(DetectionModel.models_id == job.vlm_model_id).first()
            if not model:
                self._set_job_error(db, job_id, f"未找到 VLM 模型: {job.vlm_model_id}")
                return None

            group_settings = normalize_group_settings(job.group_settings)
            vlm_config = normalize_vlm_config(job.vlm_config)
            device_interval = float(group_settings.get("device_interval_sec") or 0)
            alert_labels = job.alert_labels or []
            min_confidence = job.min_confidence or 0.7
            cooldown_sec = float((vlm_config.get("rate_limit") or {}).get("cooldown_after_alert_sec") or 0)

            run = VlmInspectionRun(
                run_id=run_id,
                job_id=job_id,
                started_at=datetime.now(),
                device_total=len(device_ids),
                status="running",
            )
            db.add(run)
            db.commit()

            with self.lock:
                if job_id in self.inspection_jobs:
                    self.inspection_jobs[job_id]["status"] = "running"
                    self.inspection_jobs[job_id]["last_run"] = datetime.now()

            for index, device_id in enumerate(device_ids):
                if not manual and self._is_job_stopped(db, job_id):
                    logger.info("VLM 巡检已停止，中断本轮: %s", job_id)
                    stopped_early = True
                    break

                if index > 0 and device_interval > 0:
                    time.sleep(device_interval)

                device = db.query(Device).filter(Device.device_id == device_id).first()
                finding_id = str(uuid.uuid4())
                finding = VlmInspectionFinding(
                    finding_id=finding_id,
                    run_id=run_id,
                    job_id=job_id,
                    device_id=device_id,
                    timestamp=datetime.now(),
                    vlm_model_id=job.vlm_model_id,
                    prompt_id=job.prompt_id,
                )

                if not device:
                    finding.error = "设备不存在"
                    fail_count += 1
                    db.add(finding)
                    db.commit()
                    continue

                frame = frame_acquisition.get_frame(device, group_settings)
                if frame is None:
                    finding.error = "取帧失败"
                    fail_count += 1
                    db.add(finding)
                    db.commit()
                    continue

                if vlm_config.get("save_snapshot", True):
                    finding.snapshot_path = save_snapshot(frame, job_id, finding_id)

                inspection = run_vlm_only_inspection(
                    frame=frame,
                    model_record=model,
                    prompt_id=job.prompt_id or "general_patrol_v1",
                    alert_labels=alert_labels,
                    min_confidence=min_confidence,
                    prompt_override=job.prompt_override,
                    vlm_config=vlm_config,
                )

                finding.latency_ms = inspection.get("latency_ms") or 0
                finding.raw_response = {
                    "raw_text": (inspection.get("raw_text") or "")[:4000],
                    "raw_parsed": inspection.get("raw_parsed"),
                }
                finding.findings = inspection.get("result", {}).get("findings") or []
                finding.summary = inspection.get("result", {}).get("summary") or ""

                if inspection.get("error"):
                    finding.error = inspection["error"]
                    fail_count += 1
                else:
                    success_count += 1
                    result = inspection.get("result") or {}
                    needs_alert = bool(result.get("needs_alert"))
                    if needs_alert and self._in_cooldown(db, job_id, device_id, cooldown_sec):
                        needs_alert = False
                    finding.needs_alert = needs_alert
                    finding.alert_labels = result.get("alert_labels") or []
                    if needs_alert:
                        alert_count += 1
                        self._mark_cooldown(db, job_id, device_id)
                        self._push_vlm_alert(job, device, finding, frame, result)

                db.add(finding)
                db.commit()

            self._finalize_run(
                db,
                run,
                job_id,
                device_ids,
                success_count,
                fail_count,
                alert_count,
                stopped_early,
            )
            return run.summary
        except Exception as exc:
            logger.exception("VLM 巡检任务异常: %s", job_id)
            self._set_job_error(db, job_id, str(exc))
            if run is not None:
                run.status = "error"
                run.finished_at = datetime.now()
                run.device_success = success_count
                run.device_failed = fail_count
                run.alert_count = alert_count
                run.summary = {
                    "device_total": len(device_ids),
                    "device_success": success_count,
                    "device_failed": fail_count,
                    "alert_count": alert_count,
                    "error": str(exc)[:500],
                }
                db.commit()
            return None
        finally:
            db.close()

    def _finalize_run(
        self,
        db: Session,
        run: VlmInspectionRun,
        job_id: str,
        device_ids,
        success_count: int,
        fail_count: int,
        alert_count: int,
        stopped_early: bool,
    ):
        run.device_success = success_count
        run.device_failed = fail_count
        run.alert_count = alert_count
        run.finished_at = datetime.now()
        run.summary = {
            "device_total": len(device_ids),
            "device_success": success_count,
            "device_failed": fail_count,
            "alert_count": alert_count,
            "stopped_early": stopped_early,
        }

        if stopped_early:
            run.status = "cancelled"
        elif fail_count == 0:
            run.status = "completed"
        elif success_count:
            run.status = "partial"
        else:
            run.status = "error"

        job_row = db.query(VlmInspectionJob).filter(VlmInspectionJob.job_id == job_id).first()
        if job_row:
            job_row.last_run = datetime.now()
            job_row.last_result = run.summary
            job_row.last_error = None
            if stopped_early:
                job_row.status = "paused" if not job_row.is_active else "scheduled"
            else:
                job_row.status = "completed"
        db.commit()

        with self.lock:
            if job_id in self.inspection_jobs:
                mem_status = "cancelled" if stopped_early else "completed"
                self.inspection_jobs[job_id]["status"] = mem_status
                self.inspection_jobs[job_id]["last_result"] = run.summary
                self.inspection_jobs[job_id]["last_error"] = None
                if not stopped_early and job_row and job_row.is_active:
                    self.inspection_jobs[job_id]["status"] = "scheduled"

        logger.info(
            "VLM 巡检完成 %s [%s]: 成功 %s 失败 %s 告警 %s",
            job_id,
            run.status,
            success_count,
            fail_count,
            alert_count,
        )

    def _set_job_error(self, db: Session, job_id: str, error: str):
        job_row = db.query(VlmInspectionJob).filter(VlmInspectionJob.job_id == job_id).first()
        if job_row:
            job_row.last_error = error[:500]
            job_row.status = "error"
            db.commit()
        with self.lock:
            if job_id in self.inspection_jobs:
                self.inspection_jobs[job_id]["status"] = "error"
                self.inspection_jobs[job_id]["last_error"] = error[:500]

    def _in_cooldown(self, db: Session, job_id: str, device_id: str, cooldown_sec: float) -> bool:
        if cooldown_sec <= 0:
            return False
        row = (
            db.query(VlmInspectionAlertCooldown)
            .filter(
                VlmInspectionAlertCooldown.job_id == job_id,
                VlmInspectionAlertCooldown.device_id == device_id,
            )
            .first()
        )
        if not row or not row.last_alert_at:
            return False
        elapsed = (datetime.now() - row.last_alert_at).total_seconds()
        return elapsed < cooldown_sec

    def _mark_cooldown(self, db: Session, job_id: str, device_id: str):
        now = datetime.now()
        row = (
            db.query(VlmInspectionAlertCooldown)
            .filter(
                VlmInspectionAlertCooldown.job_id == job_id,
                VlmInspectionAlertCooldown.device_id == device_id,
            )
            .first()
        )
        if row:
            row.last_alert_at = now
        else:
            db.add(
                VlmInspectionAlertCooldown(
                    job_id=job_id,
                    device_id=device_id,
                    last_alert_at=now,
                )
            )
        db.commit()

    def _build_push_tags(self, job: VlmInspectionJob, device_id: str) -> list:
        tags = [str(t) for t in (job.tags or []) if t]
        for extra in ("vlm_inspection", "vlm_alert", f"device_{device_id}", f"job_{job.job_id}"):
            if extra not in tags:
                tags.append(extra)
        return tags

    def _push_vlm_alert(
        self,
        job: VlmInspectionJob,
        device: Device,
        finding: VlmInspectionFinding,
        frame,
        result: Dict[str, Any],
    ) -> None:
        if not data_pusher.push_configs:
            return
        try:
            alert_labels = finding.alert_labels or result.get("alert_labels") or []
            label_text = "、".join(alert_labels) if alert_labels else "异常"
            push_payload = {
                "event_type": "vlm_inspection_alert",
                "job_id": job.job_id,
                "job_name": job.job_name,
                "finding_id": finding.finding_id,
                "deviceId": device.device_id,
                "cameraInfo": f"{device.device_name}:{device.ip_address or ''}",
                "location": device.location or "",
                "recordTime": datetime.now().isoformat() + "+08:00",
                "alert_labels": alert_labels,
                "summary": finding.summary or result.get("summary") or "",
                "findings": finding.findings or result.get("findings") or [],
                "prompt_id": job.prompt_id,
                "vlm_model_id": job.vlm_model_id,
                "latency_ms": finding.latency_ms or 0,
                "event_description": f"VLM巡检告警: {label_text}",
            }
            data_pusher.push_data(
                data=push_payload,
                image=frame,
                tags=self._build_push_tags(job, device.device_id),
            )
            logger.info(
                "VLM 巡检告警已推送: job=%s device=%s labels=%s",
                job.job_id,
                device.device_id,
                alert_labels,
            )
        except Exception as exc:
            logger.error("VLM 巡检告警推送失败: %s", exc)

    def load_all_active_jobs(self):
        db = SessionLocal()
        try:
            jobs = db.query(VlmInspectionJob).filter(VlmInspectionJob.is_active.is_(True)).all()
            for job in jobs:
                self.add_inspection_job(job.job_id)
                logger.info("已加载 VLM 巡检任务: %s", job.job_name)
            self._recover_stale_runs(db)
        except Exception as exc:
            logger.error("加载 VLM 巡检任务失败: %s", exc)
        finally:
            db.close()

    def _recover_stale_runs(self, db: Session):
        """detect-server 重启后，将遗留的 running 状态修正为 cancelled"""
        stale_runs = (
            db.query(VlmInspectionRun)
            .filter(VlmInspectionRun.status == "running")
            .all()
        )
        if not stale_runs:
            return
        now = datetime.now()
        for run in stale_runs:
            run.status = "cancelled"
            run.finished_at = now
            run.summary = {
                **(run.summary or {}),
                "recovered_after_restart": True,
                "device_success": run.device_success or 0,
                "device_failed": run.device_failed or 0,
                "alert_count": run.alert_count or 0,
            }
        db.commit()
        logger.warning("已修正 %s 条因服务重启遗留的 running 巡检记录", len(stale_runs))


vlm_inspection_engine = VlmInspectionEngine()
