"""轻量级数据库字段补丁（create_all 不会自动 ALTER 已有表）"""
import logging
from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)


def ensure_device_rtsp_columns(engine) -> None:
    inspector = inspect(engine)
    if "device" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("device")}
    statements = []

    if "rtsp_url_mode" not in columns:
        statements.append(
            "ALTER TABLE device ADD COLUMN rtsp_url_mode VARCHAR(20) DEFAULT 'dahua'"
        )
    if "rtsp_url" not in columns:
        statements.append("ALTER TABLE device ADD COLUMN rtsp_url TEXT")

    if not statements:
        return

    with engine.begin() as conn:
        for sql in statements:
            conn.execute(text(sql))
            logger.info("已执行数据库补丁: %s", sql)


def ensure_detection_config_stream_type(engine) -> None:
    inspector = inspect(engine)
    if "detection_config" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("detection_config")}
    if "stream_type" in columns:
        return

    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE detection_config ADD COLUMN stream_type VARCHAR(10) DEFAULT 'main'"
            )
        )
        logger.info("已执行数据库补丁: detection_config.stream_type")

        if "device" in inspector.get_table_names():
            conn.execute(
                text(
                    """
                    UPDATE detection_config AS dc
                    SET stream_type = COALESCE(d.stream_type, 'main')
                    FROM device AS d
                    WHERE dc.device_id = d.device_id
                    """
                )
            )
            logger.info("已从 device 回填 detection_config.stream_type")


def ensure_device_group_support(engine) -> None:
    inspector = inspect(engine)
    if "device_group" not in inspector.get_table_names():
        return

    if "device" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("device")}
    if "group_id" not in columns:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE device ADD COLUMN group_id VARCHAR(64) REFERENCES device_group(group_id)"
                )
            )
            logger.info("已执行数据库补丁: device.group_id")


def ensure_detection_config_group_mode(engine) -> None:
    inspector = inspect(engine)
    if "detection_config" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("detection_config")}
    statements = []

    if "config_mode" not in columns:
        statements.append(
            "ALTER TABLE detection_config ADD COLUMN config_mode VARCHAR(20) DEFAULT 'device'"
        )
    if "group_id" not in columns:
        statements.append(
            "ALTER TABLE detection_config ADD COLUMN group_id VARCHAR(64) REFERENCES device_group(group_id)"
        )
    if "group_settings" not in columns:
        statements.append("ALTER TABLE detection_config ADD COLUMN group_settings JSONB")

    with engine.begin() as conn:
        for sql in statements:
            conn.execute(text(sql))
            logger.info("已执行数据库补丁: %s", sql)

        if "device_id" in columns:
            try:
                conn.execute(
                    text(
                        "ALTER TABLE detection_config ALTER COLUMN device_id DROP NOT NULL"
                    )
                )
                logger.info("已执行数据库补丁: detection_config.device_id 允许为空")
            except Exception as exc:
                logger.debug("detection_config.device_id 已为可空或无需修改: %s", exc)


def ensure_crowd_analysis_job_extensions(engine) -> None:
    inspector = inspect(engine)
    if "crowd_analysis_job" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("crowd_analysis_job")}
    statements = []

    if "device_mode" not in columns:
        statements.append(
            "ALTER TABLE crowd_analysis_job ADD COLUMN device_mode VARCHAR(20) DEFAULT 'manual'"
        )
    if "group_id" not in columns:
        statements.append(
            "ALTER TABLE crowd_analysis_job ADD COLUMN group_id VARCHAR(64) REFERENCES device_group(group_id)"
        )
    if "group_settings" not in columns:
        statements.append("ALTER TABLE crowd_analysis_job ADD COLUMN group_settings JSONB")
    if "schedule_config" not in columns:
        statements.append("ALTER TABLE crowd_analysis_job ADD COLUMN schedule_config JSONB")

    if not statements:
        return

    with engine.begin() as conn:
        for sql in statements:
            conn.execute(text(sql))
            logger.info("已执行数据库补丁: %s", sql)


def ensure_detection_log_device_id_nullable(engine) -> None:
    inspector = inspect(engine)
    if "detection_log" not in inspector.get_table_names():
        return

    columns = {col["name"]: col for col in inspector.get_columns("detection_log")}
    if "device_id" not in columns:
        return
    if columns["device_id"].get("nullable"):
        return

    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE detection_log ALTER COLUMN device_id DROP NOT NULL"))
            logger.info("已执行数据库补丁: detection_log.device_id 允许为空")
        except Exception as exc:
            logger.debug("detection_log.device_id 已为可空或无需修改: %s", exc)


def ensure_vlm_inspection_tables(engine) -> None:
    """VLM 巡检相关表（create_all 未覆盖的环境补建 + 告警冷却表）"""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    statements = []
    if "vlm_inspection_job" not in tables:
        statements.extend([
            """
            CREATE TABLE IF NOT EXISTS vlm_inspection_job (
                job_id VARCHAR(64) PRIMARY KEY,
                job_name VARCHAR(128) NOT NULL,
                device_mode VARCHAR(20) DEFAULT 'manual',
                group_id VARCHAR(64) REFERENCES device_group(group_id),
                group_settings JSONB,
                schedule_config JSONB,
                device_ids VARCHAR(64)[],
                vlm_model_id VARCHAR(64) NOT NULL REFERENCES detection_model(models_id),
                prompt_id VARCHAR(64) DEFAULT 'general_patrol_v1',
                prompt_override TEXT,
                vlm_config JSONB,
                alert_labels VARCHAR(64)[],
                min_confidence DOUBLE PRECISION DEFAULT 0.7,
                interval INTEGER DEFAULT 300,
                tags VARCHAR(64)[],
                description VARCHAR(512),
                is_active BOOLEAN DEFAULT FALSE,
                status VARCHAR(32) DEFAULT 'created',
                last_run TIMESTAMP,
                last_result JSONB,
                last_error VARCHAR(512),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS vlm_inspection_run (
                run_id VARCHAR(64) PRIMARY KEY,
                job_id VARCHAR(64) NOT NULL REFERENCES vlm_inspection_job(job_id),
                started_at TIMESTAMP DEFAULT NOW(),
                finished_at TIMESTAMP,
                device_total INTEGER DEFAULT 0,
                device_success INTEGER DEFAULT 0,
                device_failed INTEGER DEFAULT 0,
                alert_count INTEGER DEFAULT 0,
                status VARCHAR(32) DEFAULT 'running',
                summary JSONB
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS vlm_inspection_finding (
                finding_id VARCHAR(64) PRIMARY KEY,
                run_id VARCHAR(64) NOT NULL REFERENCES vlm_inspection_run(run_id),
                job_id VARCHAR(64) NOT NULL REFERENCES vlm_inspection_job(job_id),
                device_id VARCHAR(64) NOT NULL REFERENCES device(device_id),
                timestamp TIMESTAMP DEFAULT NOW(),
                vlm_model_id VARCHAR(64),
                prompt_id VARCHAR(64),
                latency_ms INTEGER DEFAULT 0,
                raw_response JSONB,
                findings JSONB,
                needs_alert BOOLEAN DEFAULT FALSE,
                alert_labels VARCHAR(64)[],
                snapshot_path TEXT,
                summary TEXT,
                error TEXT
            )
            """,
        ])

    if "vlm_inspection_alert_cooldown" not in tables:
        statements.append(
            """
            CREATE TABLE IF NOT EXISTS vlm_inspection_alert_cooldown (
                job_id VARCHAR(64) NOT NULL REFERENCES vlm_inspection_job(job_id),
                device_id VARCHAR(64) NOT NULL REFERENCES device(device_id),
                last_alert_at TIMESTAMP NOT NULL DEFAULT NOW(),
                PRIMARY KEY (job_id, device_id)
            )
            """
        )

    if not statements:
        return

    with engine.begin() as conn:
        for sql in statements:
            conn.execute(text(sql.strip()))
            logger.info("已执行 VLM 巡检表补丁")


def ensure_data_push_log_table(engine) -> None:
    """推送执行记录表"""
    from sqlalchemy import inspect

    insp = inspect(engine)
    if "data_push_log" in insp.get_table_names():
        return

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS data_push_log (
                    log_id VARCHAR(64) PRIMARY KEY,
                    push_id VARCHAR(64) NOT NULL REFERENCES data_push_config(push_id),
                    push_name VARCHAR(255),
                    push_method VARCHAR(32),
                    status VARCHAR(20) NOT NULL,
                    target_summary VARCHAR(500),
                    message TEXT,
                    tags TEXT[],
                    config_id VARCHAR(64),
                    duration_ms INTEGER,
                    payload_preview JSONB,
                    is_test BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_data_push_log_push_id ON data_push_log(push_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_data_push_log_status ON data_push_log(status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_data_push_log_created_at ON data_push_log(created_at DESC)"))
    logger.info("已创建 data_push_log 表")


def ensure_edge_server_platform_columns(engine) -> None:
    """边缘节点平台类型与 URL 字段"""
    inspector = inspect(engine)
    if "edge_servers" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("edge_servers")}
    statements = []

    if "platform_type" not in columns:
        statements.append(
            "ALTER TABLE edge_servers ADD COLUMN platform_type VARCHAR(20) DEFAULT 'maisi' NOT NULL"
        )
    if "admin_url" not in columns:
        statements.append("ALTER TABLE edge_servers ADD COLUMN admin_url VARCHAR(512)")
    if "dashboard_url" not in columns:
        statements.append("ALTER TABLE edge_servers ADD COLUMN dashboard_url VARCHAR(512)")
    if "health_check_url" not in columns:
        statements.append("ALTER TABLE edge_servers ADD COLUMN health_check_url VARCHAR(512)")

    if not statements:
        return

    with engine.begin() as conn:
        for sql in statements:
            conn.execute(text(sql))
            logger.info("已执行数据库补丁: %s", sql)


def ensure_device_monitor_method(engine) -> None:
    inspector = inspect(engine)
    if "device" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("device")}
    if "monitor_method" in columns:
        return

    with engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE device ADD COLUMN monitor_method VARCHAR(32) DEFAULT 'auto'")
        )
        logger.info("已执行数据库补丁: device.monitor_method")

