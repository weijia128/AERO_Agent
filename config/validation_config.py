"""
交叉验证系统配置

控制规则引擎 + LLM 交叉验证的行为和参数。
"""
from typing import Dict, Any
from config.settings import settings


class ValidationConfig:
    """交叉验证配置类"""

    # ============================================================
    # 功能开关
    # ============================================================
    # 启用交叉验证（设为 False 时回退到纯规则引擎）
    ENABLE_CROSS_VALIDATION = settings.ENABLE_CROSS_VALIDATION if hasattr(settings, 'ENABLE_CROSS_VALIDATION') else True

    # ============================================================
    # LLM 配置（验证专用）
    # ============================================================
    # 低温度确保稳定输出
    VALIDATION_TEMPERATURE = 0.1

    # 最大 token 数（验证输出不需要太长）
    VALIDATION_MAX_TOKENS = 500

    # 超时时间（秒）
    VALIDATION_TIMEOUT = 5

    # ============================================================
    # 置信度阈值
    # ============================================================
    # LLM 输出置信度阈值（低于此值忽略 LLM 结果）
    CONFIDENCE_THRESHOLD = 0.75

    # 高置信度阈值（用于冲突解决）
    HIGH_CONFIDENCE_THRESHOLD = 0.85

    # ============================================================
    # 冲突解决策略
    # ============================================================
    # 风险等级差异阈值（R1 vs R3 = 2级差异）
    RISK_LEVEL_DIFF_THRESHOLD = 2

    # 当冲突时是否采用更严格的评级（保守策略）
    USE_STRICTER_ON_CONFLICT = True

    # 是否启用人工复核标记（冲突时标记为需要人工复核）
    ENABLE_MANUAL_REVIEW_FLAG = True

    # ============================================================
    # 验证范围
    # ============================================================
    # 启用风险评估验证
    VALIDATE_RISK_ASSESSMENT = True

    # 启用清理时间验证
    VALIDATE_CLEANUP_TIME = False  # Phase 2

    # 启用消防通知验证
    VALIDATE_FIRE_NOTIFICATION = False  # Phase 2

    # 启用跑道封闭验证
    VALIDATE_RUNWAY_CLOSURE = False  # Phase 2

    # ============================================================
    # 采样率控制（成本优化）
    # ============================================================
    # 采样率（1.0 = 100% 验证，0.1 = 10% 随机验证）
    SAMPLING_RATE = 1.0

    # ============================================================
    # 监控配置
    # ============================================================
    # 记录所有验证结果（用于监控和审计）
    LOG_ALL_VALIDATIONS = True

    # 记录冲突案例（用于闭环改进）
    LOG_CONFLICTS = True

    # 冲突告警阈值（冲突率超过此值时触发告警）
    CONFLICT_ALERT_THRESHOLD = 0.15

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """导出配置为字典"""
        return {
            "enable_cross_validation": cls.ENABLE_CROSS_VALIDATION,
            "validation_temperature": cls.VALIDATION_TEMPERATURE,
            "validation_max_tokens": cls.VALIDATION_MAX_TOKENS,
            "validation_timeout": cls.VALIDATION_TIMEOUT,
            "confidence_threshold": cls.CONFIDENCE_THRESHOLD,
            "high_confidence_threshold": cls.HIGH_CONFIDENCE_THRESHOLD,
            "risk_level_diff_threshold": cls.RISK_LEVEL_DIFF_THRESHOLD,
            "use_stricter_on_conflict": cls.USE_STRICTER_ON_CONFLICT,
            "enable_manual_review_flag": cls.ENABLE_MANUAL_REVIEW_FLAG,
            "validate_risk_assessment": cls.VALIDATE_RISK_ASSESSMENT,
            "validate_cleanup_time": cls.VALIDATE_CLEANUP_TIME,
            "validate_fire_notification": cls.VALIDATE_FIRE_NOTIFICATION,
            "validate_runway_closure": cls.VALIDATE_RUNWAY_CLOSURE,
            "sampling_rate": cls.SAMPLING_RATE,
            "log_all_validations": cls.LOG_ALL_VALIDATIONS,
            "log_conflicts": cls.LOG_CONFLICTS,
            "conflict_alert_threshold": cls.CONFLICT_ALERT_THRESHOLD,
        }

    @classmethod
    def summary(cls) -> str:
        """返回配置摘要"""
        return f"""
交叉验证配置:
  - 功能启用: {cls.ENABLE_CROSS_VALIDATION}
  - 验证范围: 风险评估={cls.VALIDATE_RISK_ASSESSMENT}, 清理时间={cls.VALIDATE_CLEANUP_TIME}
  - 置信度阈值: {cls.CONFIDENCE_THRESHOLD}
  - 采样率: {cls.SAMPLING_RATE * 100}%
  - 冲突策略: {'采用更严格评级' if cls.USE_STRICTER_ON_CONFLICT else '保留规则结果'}
        """.strip()


# 导出配置实例
validation_config = ValidationConfig()
