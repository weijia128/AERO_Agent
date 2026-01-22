"""
日志配置模块

支持 text 和 JSON 两种格式，适用于开发和生产环境。
"""
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Optional

from config.settings import settings


class JSONFormatter(logging.Formatter):
    """JSON 格式日志格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # 添加额外字段
        if hasattr(record, "extra_data"):
            log_obj.update(record.extra_data)

        # 添加异常信息
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """文本格式日志格式化器（开发环境）"""

    def __init__(self):
        super().__init__(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def setup_logging(
    level: Optional[str] = None,
    format_type: Optional[str] = None,
    log_file: Optional[str] = None,
) -> None:
    """
    配置应用日志

    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
        format_type: 日志格式 (text, json)
        log_file: 日志文件路径 (可选)
    """
    # 使用参数或默认配置
    log_level = getattr(logging, (level or settings.LOG_LEVEL).upper(), logging.INFO)
    log_format = format_type or settings.LOG_FORMAT

    # 选择格式化器
    formatter: logging.Formatter
    if log_format == "json":
        formatter = JSONFormatter()
    else:
        formatter = TextFormatter()

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # 配置根日志
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 清除已有处理器
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)

    # 文件处理器 (可选)
    file_path = log_file or settings.LOG_FILE
    if file_path:
        file_handler = logging.FileHandler(str(file_path), encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # 降低第三方库日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    获取带有模块名的 logger

    Args:
        name: 模块名称，通常使用 __name__

    Returns:
        配置好的 Logger 实例
    """
    return logging.getLogger(name)
