"""
规程检索工具 (RAG)
"""
from typing import Dict, Any, List
from tools.base import BaseTool


# 模拟知识库
MOCK_REGULATIONS = {
    "fuel_spill": {
        "title": "航空燃油(Jet Fuel)泄漏应急处置规程",
        "risk_level": "高风险",
        "risk_features": "易燃易爆",
        "content": """
1. 立即通知消防部门并请求支援
2. 要求机组立即关闭发动机
3. 疏散周边100米范围内人员
4. 设置警戒区域，禁止无关车辆和人员进入
5. 使用泡沫覆盖泄漏区域进行覆盖抑制
6. 禁止任何火花、热源、移动设备靠近
7. 使用专业吸油材料控制扩散
8. 使用防爆泵抽吸回收燃油
9. 完成清污后进行可燃气体检测确认
10. 记录泄漏量和处置过程
""",
        "cleanup_method": "专业吸油材料+防爆泵抽吸",
        "source": "CCAR-139-R2 机场安全管理手册",
    },
    "engine_oil_spill": {
        "title": "发动机滑油泄漏应急处置规程",
        "risk_level": "中风险",
        "risk_features": "可燃，烟雾有毒",
        "content": """
1. 通知机务部门到场处置
2. 评估泄漏量和影响范围
3. 使用吸附材料(吸油棉/毡)控制扩散
4. 对污染区域进行防滑处理，防止人员滑倒
5. 保持通风良好，减少有毒烟雾积聚
6. 使用工业清洁剂清除残余油污
7. 高压冲洗污染区域(注意废水收集)
8. 清理后确认无残留油污
9. 记录泄漏原因和处置过程
""",
        "cleanup_method": "吸附材料+工业清洁剂+高压冲洗",
        "source": "航空器地面勤务规程",
    },
    "hydraulic_spill": {
        "title": "液压油泄漏应急处置规程",
        "risk_level": "中高风险",
        "risk_features": "易燃，高压喷射危险",
        "content": """
1. 通知机务部门和消防部门
2. 首先要求机组执行液压系统泄压程序
3. 等待压力完全释放后再接近
4. 使用吸附材料控制泄漏扩散
5. 设置防滑警示标识
6. 使用专业回收容器收集泄漏液压油
7. 避免高压喷射造成的二次伤害
8. 清理后检查系统完整性
9. 记录并分析泄漏原因
""",
        "cleanup_method": "先泄压+吸附+专业回收容器",
        "source": "航空器维修手册-液压系统",
    },
    "hydraulic_spill_simple": {
        "title": "液压油泄漏应急处置规程",
        "content": """
1. 通知机务部门
2. 评估泄漏量和范围
3. 使用吸油材料控制扩散
4. 注意防滑措施
5. 完成清污后进行检测
""",
        "source": "机场手册-地面安全",
    },
    "engine_running_spill": {
        "title": "发动机运转中泄漏处置要点",
        "content": """
1. 立即要求机组关闭发动机
2. 通知消防部门待命
3. 评估火灾风险
4. 准备应急疏散
5. 持续监控直至发动机完全停止
""",
        "source": "应急预案-2024",
    },
}

MOCK_CASES = [
    {
        "id": "CASE-2024-001",
        "title": "A320航空燃油泄漏事件",
        "summary": "501机位A320飞机航空燃油泄漏约5平方米，发动机已停止",
        "risk_type": "燃油",
        "handling": "通知消防、机务，使用泡沫覆盖，30分钟内完成清污和防爆泵回收",
        "lessons": "加强起飞前燃油系统检查，发现渗漏及时处置",
    },
    {
        "id": "CASE-2024-002",
        "title": "B737发动机滑油泄漏事件",
        "summary": "滑行道发动机滑油持续泄漏，面积约3平方米，发动机运转中",
        "risk_type": "滑油",
        "handling": "要求机组关闭发动机，使用吸油材料控制，防滑处理后清理",
        "lessons": "发动机运转中泄漏风险高，需优先要求关车",
    },
    {
        "id": "CASE-2023-045",
        "title": "B737液压油泄漏事件",
        "summary": "机位液压油泄漏，面积较小，系统压力已释放",
        "risk_type": "液压油",
        "handling": "机务处理，泄压后使用吸油材料清理，未影响运行",
        "lessons": "日常巡检注意液压管路状态，大面积泄漏需专业回收",
    },
]


class SearchRegulationsTool(BaseTool):
    """检索应急处置规程"""
    
    name = "search_regulations"
    description = """检索相关的应急处置规程和历史案例。
    
输入参数:
- query: 检索关键词
- fluid_type: 油液类型
- include_cases: 是否包含历史案例

返回信息:
- 相关规程内容
- 历史相似案例"""
    
    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        query = inputs.get("query", "")
        fluid_type = inputs.get("fluid_type", "")
        include_cases = inputs.get("include_cases", True)

        # 从状态获取油液类型
        if not fluid_type:
            incident = state.get("incident", {})
            fluid_type = incident.get("fluid_type", "FUEL")

        # 检索规程
        regulations = []

        if fluid_type == "FUEL" or "燃油" in query:
            regulations.append(MOCK_REGULATIONS["fuel_spill"])
        elif fluid_type == "HYDRAULIC" or "液压" in query:
            regulations.append(MOCK_REGULATIONS["hydraulic_spill"])
        elif fluid_type == "OIL" or "滑油" in query:
            regulations.append(MOCK_REGULATIONS["engine_oil_spill"])

        # 发动机运转相关
        incident = state.get("incident", {})
        if incident.get("engine_status") == "RUNNING":
            regulations.append(MOCK_REGULATIONS["engine_running_spill"])

        # 检索案例
        cases = []
        if include_cases:
            # 根据油液类型筛选案例
            for case in MOCK_CASES:
                if fluid_type == "FUEL" and case.get("risk_type") == "燃油":
                    cases.append(case)
                elif fluid_type == "HYDRAULIC" and case.get("risk_type") == "液压油":
                    cases.append(case)
                elif fluid_type == "OIL" and case.get("risk_type") == "滑油":
                    cases.append(case)

        # 构建结果
        reg_summary = "; ".join([r["title"] for r in regulations])
        case_summary = "; ".join([c["title"] for c in cases])

        observation = f"检索到{len(regulations)}条规程: {reg_summary}"
        if cases:
            observation += f"; 相关案例{len(cases)}条: {case_summary}"

        return {
            "observation": observation,
            "retrieved_knowledge": {
                "regulations": regulations,
                "cases": cases,
            },
        }
