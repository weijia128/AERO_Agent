"""
输出生成节点

职责：
1. 汇总所有分析结果
2. 调用 LLM 基于 SKILL 规范生成检查单报告
3. 格式化最终输出
"""
from typing import Dict, Any, List
from datetime import datetime

from agent.state import AgentState, FSMState, RiskLevel
from config.llm_config import get_llm_client


def generate_event_summary(state: AgentState) -> str:
    """生成事件摘要"""
    incident = state.get("incident", {})
    
    parts = []
    
    # 时间和位置
    parts.append(f"事件时间: {incident.get('report_time', '未知')}")
    if incident.get("position"):
        parts.append(f"事件位置: {incident['position']}")
    
    # 航班信息
    if incident.get("flight_no"):
        parts.append(f"航班号: {incident['flight_no']}")

    # 事件描述
    desc_parts = []
    if incident.get("fluid_type"):
        fluid_map = {"FUEL": "燃油", "HYDRAULIC": "液压油", "OIL": "滑油"}
        desc_parts.append(f"{fluid_map.get(incident['fluid_type'], incident['fluid_type'])}泄漏")
    if incident.get("leak_size"):
        size_map = {"LARGE": "大面积", "MEDIUM": "中等面积", "SMALL": "小面积"}
        desc_parts.append(size_map.get(incident['leak_size'], incident['leak_size']))
    if incident.get("continuous"):
        desc_parts.append("持续滴漏中")
    if incident.get("engine_status") == "RUNNING":
        desc_parts.append("发动机运转中")
    
    if desc_parts:
        parts.append(f"事件描述: {', '.join(desc_parts)}")
    
    return "\n".join(parts)


def generate_handling_process(state: AgentState) -> List[str]:
    """生成处置过程"""
    actions = state.get("actions_taken", [])
    process = []
    
    for action in actions:
        action_name = action.get("action", "")
        result = action.get("result", "")
        timestamp = action.get("timestamp", "")
        
        # 格式化动作描述
        action_map = {
            "ask_for_detail": "信息确认",
            "assess_risk": "风险评估",
            "calculate_impact_zone": "影响范围分析",
            "notify_department": "通知相关部门",
            "search_regulations": "规程检索",
        }
        
        action_desc = action_map.get(action_name, action_name)
        if result:
            process.append(f"[{timestamp}] {action_desc}: {result}")
        else:
            process.append(f"[{timestamp}] {action_desc}")
    
    return process


def generate_checklist_items(state: AgentState) -> List[Dict[str, Any]]:
    """生成检查单项目"""
    incident = state.get("incident", {})
    risk = state.get("risk_assessment", {})
    mandatory = state.get("mandatory_actions_done", {})
    
    items = []
    
    # 信息收集检查项
    items.append({
        "category": "信息收集",
        "items": [
            {"item": "油液类型确认", "status": "✓" if incident.get("fluid_type") else "✗"},
            {"item": "泄漏面积确认", "status": "✓" if incident.get("leak_size") else "✗"},
            {"item": "持续状态确认", "status": "✓" if incident.get("continuous") is not None else "✗"},
            {"item": "发动机状态确认", "status": "✓" if incident.get("engine_status") else "✗"},
            {"item": "位置确认", "status": "✓" if incident.get("position") else "✗"},
        ]
    })
    
    # 风险评估检查项
    items.append({
        "category": "风险评估",
        "items": [
            {"item": "风险等级评定", "status": "✓" if risk.get("level") else "✗"},
            {"item": "风险因素识别", "status": "✓" if risk.get("factors") else "✗"},
        ]
    })
    
    # 通知协调检查项
    items.append({
        "category": "通知协调",
        "items": [
            {"item": "消防部门通知", "status": "✓" if mandatory.get("fire_dept_notified") else "✗"},
            {"item": "塔台通知", "status": "✓" if mandatory.get("atc_notified") else "○"},  # ○ 表示可选
        ]
    })
    
    return items


def generate_operational_impact(state: AgentState) -> Dict[str, Any]:
    """生成运行影响评估"""
    spatial = state.get("spatial_analysis", {})
    flight_impact = state.get("flight_impact_prediction", {})

    impact = {
        "affected_areas": [],
        "affected_flights": [],
        "estimated_delay": "",
        "recommendations": [],
    }

    # 受影响区域
    if spatial.get("isolated_nodes"):
        impact["affected_areas"].extend(spatial["isolated_nodes"])
    if spatial.get("affected_taxiways"):
        impact["affected_areas"].extend([f"滑行道{t}" for t in spatial["affected_taxiways"]])
    if spatial.get("affected_runways"):
        impact["affected_areas"].extend([f"跑道{r}" for r in spatial["affected_runways"]])

    # 受影响航班（优先使用航班影响预测结果）
    if flight_impact and flight_impact.get("affected_flights"):
        # 使用预测结果
        affected_flights = flight_impact["affected_flights"]
        for flight_info in affected_flights:
            callsign = flight_info.get("callsign", "UNKNOWN")
            delay = flight_info.get("estimated_delay_minutes", 0)
            reason = flight_info.get("delay_reason", "")
            impact["affected_flights"].append(
                f"{callsign}: 预计延误 {delay} 分钟 ({reason})"
            )
    else:
        # 回退到 spatial_analysis 中的简单结果
        affected_flights = spatial.get("affected_flights", {})
        for flight, delay in affected_flights.items():
            impact["affected_flights"].append(f"{flight}: 预计延误{delay}")

    # 估算延误
    if flight_impact and flight_impact.get("statistics"):
        stats = flight_impact["statistics"]
        total = stats.get("total_affected_flights", 0)
        avg_delay = stats.get("average_delay_minutes", 0)
        if total > 0:
            impact["estimated_delay"] = f"预计影响 {total} 架次，平均延误 {avg_delay:.0f} 分钟"

    # 建议
    if spatial.get("affected_runways"):
        impact["recommendations"].append("建议启用备用跑道")
    if len(impact["affected_areas"]) > 3:
        impact["recommendations"].append("建议发布机场通告(NOTAM)")

    return impact


def generate_recommendations(state: AgentState) -> List[str]:
    """生成建议措施"""
    risk = state.get("risk_assessment", {})
    spatial = state.get("spatial_analysis", {})
    incident = state.get("incident", {})
    flight_impact = state.get("flight_impact_prediction", {})

    recommendations = []

    # 根据风险等级生成建议
    risk_level = risk.get("level", "")
    if risk_level == RiskLevel.HIGH.value:
        recommendations.append("立即执行应急响应程序")
        recommendations.append("保持与消防部门的持续联络")
        if incident.get("engine_status") == "RUNNING":
            recommendations.append("要求机组关闭发动机")
    elif risk_level == RiskLevel.MEDIUM.value:
        recommendations.append("持续监控泄漏情况")
        recommendations.append("准备应急物资")

    # 根据空间分析生成建议
    if spatial.get("affected_runways"):
        recommendations.append("协调进离港航班使用备用跑道")
    if spatial.get("isolated_nodes"):
        recommendations.append(f"隔离区域: {', '.join(spatial['isolated_nodes'])}")

    # 根据航班影响预测生成建议
    if flight_impact and flight_impact.get("statistics"):
        stats = flight_impact["statistics"]
        total = stats.get("total_affected_flights", 0)
        avg_delay = stats.get("average_delay_minutes", 0)

        if total > 0:
            recommendations.append(f"预计影响航班: {total} 架次")
            recommendations.append(f"预计平均延误: {avg_delay:.0f} 分钟")

            # 根据延误严重程度给出建议
            if avg_delay >= 60:
                recommendations.append("延误严重，建议发布机场通告(NOTAM)")
                recommendations.append("建议启动航班大面积延误应急预案")
            elif avg_delay >= 30:
                recommendations.append("延误较重，建议向旅客及时发布延误信息")

            # 根据严重程度分布给出建议
            severity = stats.get("severity_distribution", {})
            if severity.get("high", 0) > 0:
                recommendations.append(f"高严重航班 {severity['high']} 架次，建议重点关注")
            if severity.get("medium", 0) > 5:
                recommendations.append("中等影响航班较多，建议优化调度")

    # 通用建议
    recommendations.append("事件结束后进行复盘总结")
    recommendations.append("更新应急处置经验库")

    return recommendations


def generate_coordination_units(state: AgentState) -> List[Dict[str, Any]]:
    """生成需协调单位列表（详细记录格式）"""
    risk = state.get("risk_assessment", {})
    spatial = state.get("spatial_analysis", {})
    notifications = state.get("notifications_sent", [])
    mandatory = state.get("mandatory_actions_done", {})

    units = []

    # 已通知的单位映射
    notified_map = {}
    for n in notifications:
        dept = n.get("department")
        notified_map[dept] = {
            "notified": True,
            "time": n.get("timestamp", ""),
            "priority": n.get("priority", "normal"),
            "message": n.get("message", ""),
        }

    # 定义所有可能需要协调的单位（与SKILL模板完全一致）
    all_units = [
        {
            "name": "机务",
            "required": risk.get("level") in [RiskLevel.MEDIUM.value, "MEDIUM_HIGH", RiskLevel.HIGH.value],
            "contact": "内线8200",
            "role": "航空器故障排查与维修",
        },
        {
            "name": "清污/场务",
            "required": True,  # 始终需要清污
            "contact": "内线8400",
            "role": "油污清理与环境恢复",
        },
        {
            "name": "消防",
            "required": risk.get("level") == RiskLevel.HIGH.value or risk.get("level") == "MEDIUM_HIGH",
            "contact": "119/内线8119",
            "role": "应急救援及火灾风险防控",
        },
        {
            "name": "机场运行指挥",
            "required": True,
            "contact": "内线8000",
            "role": "整体运行协调与信息发布",
        },
        {
            "name": "安全监察",
            "required": False,
            "contact": "内线8500",
            "role": "安全监督与事件调查",
        },
    ]

    for unit in all_units:
        dept = unit["name"]

        # 检查是否已通知
        is_notified = False
        notify_time = ""
        priority = "normal"

        # 根据部门名称匹配通知状态
        if dept == "机务":
            is_notified = mandatory.get("maintenance_notified", False)
            notify_time = notified_map.get("机务", {}).get("time", "")
            priority = notified_map.get("机务", {}).get("priority", "normal")
        elif dept == "清污/场务":
            is_notified = mandatory.get("cleaning_notified", False)
            notify_time = notified_map.get("清洗", {}).get("time", "") or notified_map.get("清污", {}).get("time", "")
            priority = notified_map.get("清洗", {}).get("priority", "normal")
        elif dept == "消防":
            is_notified = mandatory.get("fire_dept_notified", False)
            notify_time = notified_map.get("消防", {}).get("time", "")
            priority = notified_map.get("消防", {}).get("priority", "normal")
        elif dept == "机场运行指挥":
            is_notified = mandatory.get("operations_notified", False)
            notify_time = notified_map.get("运控", {}).get("time", "") or notified_map.get("运行指挥", {}).get("time", "")
            priority = notified_map.get("运控", {}).get("priority", "normal")
        elif dept == "安全监察":
            is_notified = mandatory.get("safety_notified", False)
            notify_time = notified_map.get("安全监察", {}).get("time", "")
            priority = notified_map.get("安全监察", {}).get("priority", "normal")

        # 如果有通知记录但状态未同步，尝试从通知列表获取
        if not is_notified:
            for n in notifications:
                n_dept = n.get("department", "")
                if dept in n_dept or n_dept in dept:
                    is_notified = True
                    notify_time = n.get("timestamp", "")
                    priority = n.get("priority", "normal")
                    break

        units.append({
            "name": dept,
            "required": unit["required"],
            "contact": unit["contact"],
            "role": unit["role"],
            "notified": is_notified,
            "notify_time": notify_time,
            "priority": priority if priority else "normal",
        })

    return units


def generate_notifications_summary(state: AgentState) -> Dict[str, Any]:
    """生成通知记录汇总"""
    notifications = state.get("notifications_sent", [])
    risk = state.get("risk_assessment", {})

    summary = {
        "total_notifications": len(notifications),
        "notifications": [],
        "risk_based_required": [],
    }

    # 统计通知
    for n in notifications:
        summary["notifications"].append({
            "department": n.get("department"),
            "time": n.get("timestamp"),
            "priority": n.get("priority"),
            "status": n.get("status"),
        })

    # 根据风险等级确定应该通知的单位
    risk_level = risk.get("level", "")
    if risk_level == RiskLevel.HIGH.value:
        summary["risk_based_required"] = ["消防", "塔台", "机务", "运控"]
    elif risk_level == "MEDIUM_HIGH":
        summary["risk_based_required"] = ["消防", "机务", "运控"]
    elif risk_level == RiskLevel.MEDIUM.value:
        summary["risk_based_required"] = ["机务", "运控"]
    elif risk_level == RiskLevel.LOW.value:
        summary["risk_based_required"] = ["清洗", "运控"]

    return summary


def output_generator_node(state: AgentState) -> Dict[str, Any]:
    """
    输出生成节点

    调用 LLM 基于 SKILL 规范和知识库生成结构化的机坪特情处置检查单报告
    """
    # 构建事件数据
    incident = state.get("incident", {})
    risk = state.get("risk_assessment", {})
    spatial = state.get("spatial_analysis", {})
    actions = state.get("actions_taken", [])

    # 获取检索到的知识库内容
    knowledge = state.get("retrieved_knowledge", {})

    # 生成协调单位详细记录
    coordination_units = generate_coordination_units(state)
    notifications_summary = generate_notifications_summary(state)

    # 使用确定性模板生成报告，保证结构完整
    final_answer = _render_checklist_report(state, coordination_units, notifications_summary)

    # 构建结构化报告（供 API 返回）
    recent_actions = [a.get("action", "") for a in actions[-5:]]
    execution_summary = {
        "session_id": state.get("session_id", ""),
        "fsm_state": state.get("fsm_state", ""),
        "actions_total": len(actions),
        "recent_actions": recent_actions,
    }
    final_report = {
        "title": "机坪特情处置检查单",
        "event_summary": generate_event_summary(state),
        "risk_level": risk.get("level", "未评估"),
        "risk_score": risk.get("score", 0),
        "handling_process": generate_handling_process(state),
        "checklist_items": generate_checklist_items(state),
        "coordination_units": coordination_units,
        "notifications_summary": notifications_summary,
        "recommendations": generate_recommendations(state),
        "operational_impact": generate_operational_impact(state),
        "execution_summary": execution_summary,
        "generated_at": datetime.now().isoformat(),
        "fsm_final_state": state.get("fsm_state", ""),
        "llm_generated": False,
    }

    return {
        "final_report": final_report,
        "final_answer": final_answer,
        "is_complete": True,
        "fsm_state": FSMState.COMPLETED.value,
    }


def _render_checklist_report(state: AgentState, coordination_units: List[Dict[str, Any]], notifications_summary: Dict[str, Any]) -> str:
    """生成完整的检查单 Markdown（确定性模板）"""
    incident = state.get("incident", {})
    risk = state.get("risk_assessment", {})
    spatial = state.get("spatial_analysis", {})
    knowledge = state.get("retrieved_knowledge", {})
    flight_impact = state.get("flight_impact_prediction", {})
    position_impact = state.get("position_impact_analysis", {})
    actions = state.get("actions_taken", [])
    session_id = state.get("session_id", "") or "——"
    fsm_state = state.get("fsm_state", "") or "——"
    recent_actions = [a.get("action", "") for a in actions[-5:] if a.get("action")]
    recent_actions_text = "、".join(recent_actions) if recent_actions else "——"

    # 事件编号与时间
    event_id = f"TQCZ-{datetime.now().strftime('%Y%m%d')}-{datetime.now().strftime('%H%M')}"
    report_time = incident.get("report_time") or datetime.now().isoformat()
    report_time_str = report_time[:19].replace("T", " ")

    # 航班号
    flight_no_display = incident.get("flight_no_display") or incident.get("flight_no") or ""
    aircraft_display = flight_no_display or "——"

    # 字段映射
    fluid_map = {"FUEL": "航空燃油(Jet Fuel)", "HYDRAULIC": "液压油", "OIL": "发动机滑油"}
    oil_type = fluid_map.get(incident.get("fluid_type"), incident.get("fluid_type", "——"))
    size_map = {"LARGE": ">5㎡", "MEDIUM": "1-5㎡", "SMALL": "<1㎡", "UNKNOWN": "待评估"}
    leak_area = size_map.get(incident.get("leak_size"), "待评估")
    engine_status = "运行中" if incident.get("engine_status") == "RUNNING" else "关闭"
    is_continuous = "是" if incident.get("continuous") else "否"
    risk_level = risk.get("level", "未评估")
    risk_score = risk.get("score", 0)

    # 协同单位通知记录表
    notifications_table = ""
    for unit in coordination_units:
        name = unit.get("name", "")
        notified_status = "☑ 是  ☐ 否" if unit.get("notified") else "☐ 是  ☐ 否"
        notify_time = unit.get("notify_time", "——") or "——"
        if notify_time and len(notify_time) > 19:
            notify_time = notify_time[11:19]
        notifications_table += f"| {name} | {notified_status} | {notify_time} | |\n"

    # 影响区域
    affected_areas = []
    if spatial.get("isolated_nodes"):
        affected_areas.extend(spatial["isolated_nodes"])
    if spatial.get("affected_taxiways"):
        affected_areas.extend([f"滑行道{t}" for t in spatial["affected_taxiways"]])
    if spatial.get("affected_runways"):
        affected_areas.extend([f"跑道{r}" for r in spatial["affected_runways"]])
    affected_area_text = ", ".join(affected_areas) if affected_areas else "——"

    # 运行影响
    flight_delay_text = "——"
    if flight_impact and flight_impact.get("statistics"):
        stats = flight_impact["statistics"]
        total = stats.get("total_affected_flights", 0)
        avg_delay = stats.get("average_delay_minutes", 0)
        if total > 0:
            flight_delay_text = f"预计影响 {total} 架次，平均延误 {avg_delay:.0f} 分钟"

    runway_adjust_text = "——"
    if spatial.get("affected_taxiways") or spatial.get("affected_runways"):
        runway_adjust_text = "建议调整滑行路线/跑道运行"

    # 处置建议（取前三条）
    recommendations = generate_recommendations(state)
    if not recommendations:
        recommendations = [
            "加强机坪巡查频次与质量，提升特情早期发现能力。",
            "优化应急响应流程，缩短从发现到现场处置的响应时间。",
            "定期组织相关单位进行联合演练，提升协同处置效率。",
        ]
    recommendations = recommendations[:3]

    # 处置效果评估
    notified_units = [n.get("department") for n in state.get("notifications_sent", [])]
    notified_text = "、".join(notified_units) if notified_units else "暂无记录"
    effect_text = f"已完成事件确认与风险评估，已通知：{notified_text}。后续处置待开展。"

    # 清理方式（取知识库第一个）
    cleanup_method = "——"
    regs = knowledge.get("regulations", []) if knowledge else []
    if regs and regs[0].get("cleanup_method"):
        cleanup_method = regs[0].get("cleanup_method")

    return f"""# 机坪特情处置检查单

**适用范围**：机坪航空器漏油、油污、渗漏等特情事件的识别、处置与闭环记录

## 1. 事件基本信息
| 项目 | 记录 |
|-----|------|
| 事件编号 | {event_id} |
| 航班号/航空器注册号 | {aircraft_display} |
| 事件触发时间 | {report_time_str} |
| 上报方式 | {incident.get('discovery_method', '巡查') or '巡查'} |
| 报告人 | {incident.get('reported_by', '——') or '——'} |
| 发现位置 | {incident.get('position', '——')} |
| 风险等级 | {risk_level} (风险分数: {risk_score}) |

### 1.1 执行轨迹摘要
| 项目 | 记录 |
|-----|------|
| 会话ID | {session_id} |
| FSM 状态 | {fsm_state} |
| 工具执行次数 | {len(actions)} |
| 最近动作 | {recent_actions_text} |

## 2. 特情初始确认
### 2.1 漏油基本情况
| 关键项 | 选择/填写 |
|-------|---------|
| 油液类型 | {oil_type} |
| 是否持续滴漏 | {is_continuous} |
| 发动机/APU状态 | {engine_status} |
| 泄漏面积评估 | {leak_area} |
| 漏油形态 | 滴漏 |
| 现场气象条件 | —— |

## 3. 初期风险控制措施
检查项（勾选已执行项）：

- {"☑" if engine_status == "关闭" else "☐"} 已要求机组关车或保持关车
- ☐ 已禁止航空器滑行
- ☐ 已设置安全警戒区域
- ☐ 已排除现场点火源
- ☐ 已向周边航空器发布注意通告

## 4. 协同单位通知记录

| 单位 | 是否通知 | 通知时间 | 备注 |
|-----|---------|---------|------|
{notifications_table}## 5. 区域隔离与现场检查
### 5.1 隔离与运行限制
| 项目 | 是/否 | 备注 |
|-----|------|-----|
| 隔离区域已明确划定 | ☐ 是  ☐ 否 | |
| 滑行道关闭执行 | ☐ 是  ☐ 否 | |
| 停机位暂停使用 | ☐ 是  ☐ 否 | |
| 跑道运行受影响 | ☐ 是  ☐ 否 | |

### 5.2 现场检查要点

- ☐ 地面油污范围已确认
- ☐ 周边设施未受污染
- ☐ 无二次泄漏风险
- ☐ 无新增安全隐患

## 6. 清污处置执行情况
| 项目 | 记录 |
|-----|------|
| 清污车辆到场时间 | —— |
| 作业开始时间 | —— |
| 作业结束时间 | —— |
| 清理方式 | {cleanup_method} |
| 是否符合环保要求 | —— |

## 7. 处置结果确认
| 检查项 | 结果 | 备注 |
|-------|------|-----|
| 泄漏已停止 | ☐ 是  ☐ 否 | |
| 地面无残留油污 | ☐ 是  ☐ 否 | |
| 表面摩擦系数符合要求 | ☐ 是  ☐ 否 | |
| 现场检查合格 | ☐ 是  ☐ 否 | |

## 8. 区域恢复与运行返还
检查项（勾选已完成项）：

- ☐ 已解除现场警戒
- ☐ 已恢复滑行道使用
- ☐ 已恢复停机位使用
- ☐ 已通知管制/运控运行恢复

## 9. 运行影响评估
| 影响项 | 说明 |
|-------|-----|
| 航班延误情况 | {flight_delay_text} |
| 航班调整/取消 | —— |
| 机坪运行影响 | {affected_area_text} |
| 跑道/滑行路线调整 | {runway_adjust_text} |

## 10. 事件总结与改进建议
**事件经过简述：**
{incident.get('position', '机坪某区域')}发生约{leak_area}的{oil_type}泄漏，{'泄漏持续' if is_continuous == '是' else '泄漏已停止'}，{'发动机处于运转状态，存在火灾风险' if engine_status == '运行中' else '发动机已关闭'}。经风险评估，危险等级为{risk_level}。

**处置效果评估：**
{effect_text}

**后续改进建议：**
1. {recommendations[0] if len(recommendations) > 0 else '——'}
2. {recommendations[1] if len(recommendations) > 1 else '——'}
3. {recommendations[2] if len(recommendations) > 2 else '——'}

## 11. 签字与存档
| 角色 | 姓名 | 签字 | 时间 |
|-----|------|-----|------|
| 现场负责人 | | | |
| 机务代表 | | | |
| 清洗/场务代表 | | | |
| 消防代表 | | | |
| 机场运行指挥 | | | |

---
**说明**：本检查单应随事件处置过程同步填写，事件关闭后统一归档，用于运行复盘与安全审计。

报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""


def _build_skill_prompt(incident: Dict, risk: Dict, spatial: Dict, actions: List, knowledge: Dict = None, coordination_units: List[Dict] = None) -> str:
    """构建基于 SKILL 规范的 LLM prompt"""

    # 生成事件编号
    event_id = f"TQCZ-{datetime.now().strftime('%Y%m%d')}-{datetime.now().strftime('%H%M')}"

    # 格式化油液类型
    fluid_map = {"FUEL": "航空燃油(Jet Fuel)", "HYDRAULIC": "液压油", "OIL": "发动机滑油"}
    oil_type = fluid_map.get(incident.get("fluid_type"), incident.get("fluid_type", "不明"))

    # 格式化面积
    size_map = {"LARGE": ">5㎡", "MEDIUM": "1-5㎡", "SMALL": "<1㎡"}
    leak_area = size_map.get(incident.get("leak_size"), "待评估")

    # 格式化发动机状态
    engine_status = "运行中" if incident.get("engine_status") == "RUNNING" else "关闭"

    # 格式化持续性
    is_continuous = "是" if incident.get("continuous") else "否"

    # 风险等级
    risk_level = risk.get("level", "未评估")
    risk_score = risk.get("score", 0)
    risk_factors = ", ".join(risk.get("factors", [])) if risk.get("factors") else "无"

    # 受影响区域
    affected_areas = []
    if spatial.get("isolated_nodes"):
        affected_areas.extend(spatial["isolated_nodes"])
    if spatial.get("affected_taxiways"):
        affected_areas.extend([f"滑行道{t}" for t in spatial["affected_taxiways"]])
    if spatial.get("affected_runways"):
        affected_areas.extend([f"跑道{r}" for r in spatial["affected_runways"]])

    # 构建协同单位通知记录表格（与模板格式完全一致）
    notifications_table = ""
    if coordination_units:
        for unit in coordination_units:
            name = unit.get("name", "")
            # 使用模板格式：☐ 是  ☐ 否
            notified_status = "☐ 是  ☐ 否"
            if unit.get("notified"):
                notified_status = "☑ 是  ☐ 否"
            notify_time = unit.get("notify_time", "——")
            if notify_time and len(notify_time) > 19:
                notify_time = notify_time[11:19]  # 只显示时间部分
            # 不显示优先级，只保留单位和备注
            notifications_table += f"| {name} | {notified_status} | {notify_time} | |\n"
    else:
        # 默认表格（模板格式）
        notifications_table = "| 机务 | ☐ 是  ☐ 否 | —— | |\n| 清污/场务 | ☐ 是  ☐ 否 | —— | |\n| 消防 | ☐ 是  ☐ 否 | —— | |\n| 机场运行指挥 | ☐ 是  ☐ 否 | —— | |\n| 安全监察 | ☐ 是  ☐ 否 | —— | |\n"

    # 构建知识库内容
    knowledge_section = ""
    if knowledge:
        regulations = knowledge.get("regulations", [])
        cases = knowledge.get("cases", [])

        if regulations:
            knowledge_section += "\n## 参考规程\n"
            for reg in regulations:
                risk_info = ""
                if reg.get("risk_level"):
                    risk_info = f"【风险等级: {reg.get('risk_level')}】"
                if reg.get("risk_features"):
                    risk_info += f"【风险特征: {reg.get('risk_features')}】"
                knowledge_section += f"\n### {reg.get('title', '未知规程')} {risk_info}\n"
                knowledge_section += f"来源: {reg.get('source', '未知')}\n"
                knowledge_section += f"清理方式: {reg.get('cleanup_method', '未指定')}\n"
                knowledge_section += f"处置步骤:\n{reg.get('content', '')}\n"

        if cases:
            knowledge_section += "\n## 参考案例\n"
            for case in cases:
                knowledge_section += f"\n### {case.get('title', '未知案例')}\n"
                knowledge_section += f"摘要: {case.get('summary', '')}\n"
                knowledge_section += f"处置: {case.get('handling', '')}\n"
                knowledge_section += f"经验: {case.get('lessons', '')}\n"

    prompt = f"""你是机场机坪管制员，负责记录和汇总机坪特情处置过程。你已通过与机长的对话完成信息收集，现在需要生成标准化的处置检查单。

**重要**：你必须直接输出完整的 Markdown 格式检查单，不要有任何对话式的前言或解释。直接以 "# 机坪特情处置检查单" 开始输出。

## 事件信息
- 事件编号：{event_id}
- 航班号：{incident.get('flight_no', '待填写')}
- 事件时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}
- 发现位置：{incident.get('position', '待填写')}
- 油液类型：{oil_type}
- 泄漏面积：{leak_area}
- 发动机/APU状态：{engine_status}
- 是否持续滴漏：{is_continuous}
- 风险等级：{risk_level} (风险分数: {risk_score})
- 风险因素：{risk_factors}
- 受影响区域：{', '.join(affected_areas) if affected_areas else '无'}
- 已执行动作：{', '.join([a.get('action', '') for a in actions[-5:]]) if actions else '无'}

{knowledge_section}

## SKILL 规范要求

### 检查单结构（必须包含以下11个章节）
1. 事件基本信息
2. 特情初始确认（漏油基本情况）
3. 初期风险控制措施
4. 协同单位通知记录
5. 区域隔离与现场检查
6. 清污处置执行情况
7. 处置结果确认
8. 区域恢复与运行返还
9. 运行影响评估
10. 事件总结与改进建议
11. 签字与存档

### 生成要求
1. 使用中文专业术语
2. 复选框使用 "☑" 表示已执行，"☐" 表示未执行
3. 未知信息用 "——" 表示
4. 报告应包含完整的签字存档区域
5. 符合民航安全审计要求
6. 格式清晰、结构完整
7. **协同单位通知记录必须根据实际通知情况填充表格**

## 输出要求

**你必须按照以下格式生成完整的检查单，包含所有11个章节**，不得省略任何章节。直接输出 Markdown 文本，从标题开始：

---
# 机坪特情处置检查单

**适用范围**：机坪航空器漏油、油污、渗漏等特情事件的识别、处置与闭环记录

## 1. 事件基本信息
| 项目 | 记录 |
|-----|------|
| 事件编号 | {event_id} |
| 航班号/航空器注册号 | {incident.get('flight_no', '——')} |
| 事件触发时间 | {datetime.now().strftime('%Y-%m-%d %H:%M')} |
| 上报方式 | 巡查 |
| 报告人 | —— |
| 发现位置 | {incident.get('position', '——')} |
| 风险等级 | {risk_level} (风险分数: {risk_score}) |

## 2. 特情初始确认
### 2.1 漏油基本情况
| 关键项 | 选择/填写 |
|-------|---------|
| 油液类型 | {oil_type} |
| 是否持续滴漏 | {is_continuous} |
| 发动机/APU状态 | {engine_status} |
| 泄漏面积评估 | {leak_area} |
| 漏油形态 | 滴漏 |
| 现场气象条件 | 晴 |

## 3. 初期风险控制措施
检查项（勾选已执行项）：

- ☐ 已要求机组关车或保持关车
- ☐ 已禁止航空器滑行
- ☐ 已设置安全警戒区域
- ☐ 已排除现场点火源
- ☐ 已向周边航空器发布注意通告

## 4. 协同单位通知记录

| 单位 | 是否通知 | 通知时间 | 备注 |
|-----|---------|---------|------|
{notifications_table}
## 5. 区域隔离与现场检查
### 5.1 隔离与运行限制
| 项目 | 是/否 | 备注 |
|-----|------|-----|
| 隔离区域已明确划定 | ☐ 是  ☐ 否 | |
| 滑行道关闭执行 | ☐ 是  ☐ 否 | |
| 停机位暂停使用 | ☐ 是  ☐ 否 | |
| 跑道运行受影响 | ☐ 是  ☐ 否 | |

### 5.2 现场检查要点

- ☐ 地面油污范围已确认
- ☐ 周边设施未受污染
- ☐ 无二次泄漏风险
- ☐ 无新增安全隐患

## 6. 清污处置执行情况
| 项目 | 记录 |
|-----|------|
| 清污车辆到场时间 | —— |
| 作业开始时间 | —— |
| 作业结束时间 | —— |
| 清理方式 | 吸附 / 化学清洗 / 吸取 / 其他 |
| 是否符合环保要求 | 是 / 否 |

## 7. 处置结果确认
| 检查项 | 结果 | 备注 |
|-------|------|-----|
| 泄漏已停止 | ☐ 是  ☐ 否 | |
| 地面无残留油污 | ☐ 是  ☐ 否 | |
| 表面摩擦系数符合要求 | ☐ 是  ☐ 否 | |
| 现场检查合格 | ☐ 是  ☐ 否 | |

## 8. 区域恢复与运行返还
检查项（勾选已完成项）：

- ☐ 已解除现场警戒
- ☐ 已恢复滑行道使用
- ☐ 已恢复停机位使用
- ☐ 已通知管制/运控运行恢复

## 9. 运行影响评估
| 影响项 | 说明 |
|-------|-----|
| 航班延误情况 | —— |
| 航班调整/取消 | —— |
| 机坪运行影响 | {', '.join(affected_areas) if affected_areas else '——'} |
| 跑道/滑行路线调整 | —— |

## 10. 事件总结与改进建议
**事件经过简述：**
{incident.get('position', '机坪某区域')}发生约{leak_area}的{oil_type}泄漏，{'泄漏持续' if is_continuous == '是' else '泄漏已停止'}，{'发动机处于运转状态，存在火灾风险' if engine_status == '运行中' else '发动机已关闭'}。经风险评估，危险等级为{risk_level}。

**处置效果评估：**
已完成初步风险评估和区域隔离，后续待清污处置完成后再评估。

**后续改进建议：**
1. 加强机坪巡查，及时发现类似情况
2. 定期检查航空器供油系统
3. 完善应急响应预案培训

## 11. 签字与存档
| 角色 | 姓名 | 签字 | 时间 |
|-----|------|-----|------|
| 现场负责人 | | | |
| 机务代表 | | | |
| 清洗/场务代表 | | | |
| 消防代表 | | | |
| 机场运行指挥 | | | |

---
**说明**：本检查单应随事件处置过程同步填写，事件关闭后统一归档，用于运行复盘与安全审计。

报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    return prompt


def _fallback_report(state: AgentState) -> str:
    """回退报告生成（当 LLM 调用失败时）"""
    knowledge = state.get("retrieved_knowledge", {})
    regulations = knowledge.get("regulations", [])

    # 构建处置建议
    recommendations = generate_recommendations(state)
    if regulations:
        for reg in regulations:
            if reg.get("cleanup_method"):
                recommendations.append(f"清理方式: {reg.get('cleanup_method')}")

    return format_report_as_text({
        "title": "机坪特情处置检查单",
        "event_summary": generate_event_summary(state),
        "risk_level": state.get("risk_assessment", {}).get("level", "未评估"),
        "handling_process": generate_handling_process(state),
        "checklist_items": generate_checklist_items(state),
        "coordination_units": generate_coordination_units(state),
        "recommendations": recommendations,
        "regulations": [r.get("title") for r in regulations],
        "generated_at": datetime.now().isoformat(),
    })


def format_report_as_text(report: Dict[str, Any]) -> str:
    """将报告格式化为文本"""
    lines = []

    lines.append(f"# {report['title']}")
    lines.append("")

    lines.append("## 事件摘要")
    lines.append(report["event_summary"])
    lines.append("")

    lines.append(f"## 风险等级: {report['risk_level']}")
    lines.append("")

    # 参考规程
    if report.get("regulations"):
        lines.append("## 参考规程")
        for reg in report["regulations"]:
            lines.append(f"- {reg}")
        lines.append("")

    lines.append("## 处置过程")
    for step in report["handling_process"]:
        lines.append(f"- {step}")
    lines.append("")

    lines.append("## 检查单")
    for category in report["checklist_items"]:
        lines.append(f"### {category['category']}")
        for item in category["items"]:
            lines.append(f"- [{item['status']}] {item['item']}")
    lines.append("")

    lines.append("## 协调单位通知记录")
    lines.append("| 单位 | 是否通知 | 通知时间 | 备注 |")
    lines.append("|-----|---------|---------|------|")
    coordination = report.get("coordination_units", [])
    if coordination and isinstance(coordination, list) and len(coordination) > 0 and isinstance(coordination[0], dict):
        # 新格式：详细字典列表
        for unit in coordination:
            name = unit.get("name", "")
            notified_status = "☐ 是  ☐ 否"
            if unit.get("notified"):
                notified_status = "☑ 是  ☐ 否"
            notify_time = unit.get("notify_time", "——")
            if notify_time and len(notify_time) > 19:
                notify_time = notify_time[11:19]
            lines.append(f"| {name} | {notified_status} | {notify_time} | |")
    else:
        # 旧格式：字符串列表
        for unit in report["coordination_units"]:
            lines.append(f"- {unit}")
    lines.append("")

    lines.append("## 运行影响")
    impact = report.get("operational_impact", {})
    if impact.get("affected_areas"):
        lines.append(f"受影响区域: {', '.join(impact['affected_areas'])}")
    if impact.get("affected_flights"):
        lines.append("受影响航班:")
        for flight in impact["affected_flights"]:
            lines.append(f"  - {flight}")
    lines.append("")
    
    lines.append("## 建议措施")
    for rec in report["recommendations"]:
        lines.append(f"- {rec}")
    lines.append("")
    
    lines.append(f"---")
    lines.append(f"报告生成时间: {report['generated_at']}")
    
    return "\n".join(lines)
