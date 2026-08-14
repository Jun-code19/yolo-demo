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
