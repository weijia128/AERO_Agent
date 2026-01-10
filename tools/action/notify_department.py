"""
部门通知工具
"""
from typing import Dict, Any
from datetime import datetime
from tools.base import BaseTool


# 部门联系方式
DEPARTMENTS = {
    "消防": {
        "name": "消防部门",
        "contact": "119/内线8119",
        "response_time": "3分钟",
    },
    "塔台": {
        "name": "塔台管制",
        "contact": "内线8001",
        "response_time": "即时",
    },
    "机务": {
        "name": "机务维修",
        "contact": "内线8200",
        "response_time": "5分钟",
    },
    "运控": {
        "name": "运行指挥中心",
        "contact": "内线8000",
        "response_time": "即时",
    },
    "地服": {
        "name": "地面保障",
        "contact": "内线8300",
        "response_time": "5分钟",
    },
    "清洗": {
        "name": "清洗部门",
        "contact": "内线8400",
        "response_time": "10分钟",
    },
}


class NotifyDepartmentTool(BaseTool):
    """通知相关部门"""
    
    name = "notify_department"
    description = """通知相关部门。
    
输入参数:
- department: 部门名称（消防/塔台/机务/运控/地服）
- priority: 优先级（immediate/high/normal）
- message: 通知内容（可选，自动生成）

返回信息:
- 通知状态
- 预计响应时间"""
    
    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        department = inputs.get("department", "")
        priority = inputs.get("priority", "normal")
        message = inputs.get("message", "")
        
        if not department:
            return {"observation": "缺少部门参数"}
        
        dept_info = DEPARTMENTS.get(department)
        if not dept_info:
            return {"observation": f"未知部门: {department}"}
        
        # 生成通知内容
        if not message:
            incident = state.get("incident", {})
            position = incident.get("position", "未知位置")
            fluid_type = incident.get("fluid_type", "")
            fluid_map = {"FUEL": "燃油", "HYDRAULIC": "液压油", "OIL": "滑油"}
            fluid_name = fluid_map.get(fluid_type, "油液")
            
            risk = state.get("risk_assessment", {})
            risk_level = risk.get("level", "")
            
            message = f"{position}发生{fluid_name}泄漏"
            if risk_level:
                message += f"，风险等级: {risk_level}"
        
        # 模拟通知
        timestamp = datetime.now().isoformat()
        
        # 更新强制动作状态
        mandatory_updates = {}
        if department == "消防":
            mandatory_updates["fire_dept_notified"] = True
        elif department == "塔台":
            mandatory_updates["atc_notified"] = True
        elif department == "机务":
            mandatory_updates["maintenance_notified"] = True
        elif department == "运控":
            mandatory_updates["operations_notified"] = True
        elif department == "清洗":
            mandatory_updates["cleaning_notified"] = True
        
        # 记录通知
        notification = {
            "department": department,
            "priority": priority,
            "message": message,
            "timestamp": timestamp,
            "status": "SENT",
        }
        
        observation = (
            f"已通知{dept_info['name']}: {message}. "
            f"联系方式: {dept_info['contact']}, "
            f"预计响应时间: {dept_info['response_time']}"
        )
        
        return {
            "observation": observation,
            "mandatory_actions_done": mandatory_updates,
            "notifications_sent": [notification],
        }
