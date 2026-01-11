------





# **Bird Strike Risk Classification**







## **鸟击风险区分定义体系（机场特情 Agent）**





------





## **一、设计原则（先定边界）**





1. **风险 ≠ 结论**

   

   - 风险等级用于**触发处置强度**
   - 不等同于“是否适航”

   

2. **风险来源必须可解释**

   

   - 每一条风险判断都有**规则来源**

   

3. **宁保守、不越权**

   

   - 高风险 → 强制人工确认
   - Agent 永不自动放行

   





------





## **二、鸟击风险的五个核心维度（Risk Dimensions）**





你可以把它们作为**规则引擎的五个输入维度**：

| **维度**   | **风险含义**         |
| ---------- | -------------------- |
| ① 飞行阶段 | 阶段越关键，容错越低 |
| ② 撞击部位 | 是否为关键系统       |
| ③ 迹象强度 | 是否有物理/系统证据  |
| ④ 鸟类信息 | 鸟体大小 / 群体      |
| ⑤ 后果外溢 | 是否影响机场运行     |



------





## **三、分维度风险判定规则（核心）**







### **① 飞行阶段风险（Phase Risk）**



| **阶段**           | **风险等级** |
| ------------------ | ------------ |
| 起飞滑跑 / V1 附近 | **高**       |
| 起飞后爬升         | 高           |
| 进近 / 落地        | 高           |
| 滑行               | 中           |
| 停机位             | 低           |

> 规则示例：

> IF phase IN {TAKEOFF, LANDING} THEN risk += HIGH



------





### **② 撞击部位风险（Impact Area Risk）**



| **部位** | **风险**            |
| -------- | ------------------- |
| 发动机   | **高**              |
| 风挡     | 高                  |
| 雷达罩   | 高                  |
| 机翼前缘 | 中                  |
| 机身     | 中                  |
| 未知     | **中 → 高（保守）** |

> **Unknown ≠ Low**（这是审计重点）



------





### **③ 迹象强度（Evidence Strength）**



| **迹象**            | **风险**       |
| ------------------- | -------------- |
| 明确撞击 + 可见残留 | 高             |
| EICAS / ECAM 报警   | 高             |
| 异响 / 震动         | 中             |
| 仅怀疑              | 中             |
| 无任何迹象          | 低（但仍记录） |



------





### **④ 鸟类信息（Bird Characteristics）**



| **情况**   | **风险** |
| ---------- | -------- |
| 大型鸟类   | 高       |
| 鸟群       | 高       |
| 单只中小型 | 中       |
| 不明       | 中       |

> 如果机场鸟防系统可接入，这是**高价值加分项**



------





### **⑤ 后果外溢（Operational Impact）**



| **情况**          | **风险** |
| ----------------- | -------- |
| 需返航 / 中断起飞 | 高       |
| 占用跑道 / 机坪   | 高       |
| 需机务检查        | 中       |
| 不影响运行        | 低       |



------





## **四、综合风险等级定义（最终对外口径）**







### **推荐 4 级风险（够用、好管）**



| **等级**          | **定义**           | **系统含义**        |
| ----------------- | ------------------ | ------------------- |
| **R1 – 低风险**   | 无明显影响         | 记录 + 常规检查     |
| **R2 – 中风险**   | 存在不确定性       | 强制机务检查        |
| **R3 – 高风险**   | 关键系统或关键阶段 | 限制运行 + 多方确认 |
| **R4 – 严重风险** | 明确安全威胁       | 停止运行 + 应急联动 |



------





## **五、示例：Agent 如何算出一个风险等级（可解释）**





**输入：**



- 阶段：起飞后
- 部位：疑似发动机
- 迹象：震动 + 参数波动
- 鸟类：未知
- 后果：返航





**规则命中：**



- 关键阶段 → 高
- 关键部位 → 高
- 系统迹象 → 高
- 运行中断 → 高





**输出：**

```
{
  "risk_level": "R4",
  "confidence": "High",
  "explanation": [
    "Critical flight phase",
    "Engine suspected impact",
    "Abnormal engine indication",
    "Return-to-base required"
  ]
}
```



------





## **六、风险等级 → Orchestration 行为映射（最重要）**



| **风险** | **Agent 能做什么** | **必须人做什么** |
| -------- | ------------------ | ---------------- |
| R1       | 记录 / 提示        | 放行确认         |
| R2       | 编排检查           | 是否继续运行     |
| R3       | 限制动作           | 多方联合决策     |
| R4       | 冻结流程           | 启动应急机制     |

> **R3 / R4 是 Guardrails 的核心价值区**



------





## **七、鸟击规则引擎json**



{
  "rule_set_id": "airport-irregularity-birdstrike-risk",
  "version": "1.0.0",
  "effective_date": "2026-01-11",
  "owner": "AOC/Apron-Orchestration",
  "input_schema": {
    "required": ["phase", "impact_area", "evidence"],
    "properties": {
      "phase": {
        "type": "string",
        "enum": ["PUSHBACK", "TAXI", "TAKEOFF_ROLL", "INITIAL_CLIMB", "CRUISE", "DESCENT", "APPROACH", "LANDING_ROLL", "ON_STAND", "UNKNOWN"]
      },
      "impact_area": {
        "type": "string",
        "enum": ["ENGINE", "WINDSHIELD", "RADOME", "WING_LEADING_EDGE", "FUSELAGE", "LANDING_GEAR", "UNKNOWN"]
      },
      "evidence": {
        "type": "string",
        "enum": ["CONFIRMED_STRIKE_WITH_REMAINS", "SYSTEM_WARNING", "ABNORMAL_NOISE_VIBRATION", "SUSPECTED_ONLY", "NO_ABNORMALITY"]
      },
      "bird_info": {
        "type": "string",
        "enum": ["LARGE_BIRD", "FLOCK", "MEDIUM_SMALL_SINGLE", "UNKNOWN"],
        "default": "UNKNOWN"
      },
      "ops_impact": {
        "type": "string",
        "enum": ["RTO_OR_RTB", "BLOCKING_RUNWAY_OR_TAXIWAY", "REQUEST_MAINT_CHECK", "NO_OPS_IMPACT", "UNKNOWN"],
        "default": "UNKNOWN"
      }
    }
  },

  "scoring_model": {
    "method": "weighted_sum",
    "max_score": 100,
    "dimensions": [
      { "name": "phase", "weight": 1.0 },
      { "name": "impact_area", "weight": 1.0 },
      { "name": "evidence", "weight": 1.0 },
      { "name": "bird_info", "weight": 0.7 },
      { "name": "ops_impact", "weight": 0.8 }
    ]
  },

  "lookup_tables": {
    "phase_points": {
      "TAKEOFF_ROLL": 30,
      "INITIAL_CLIMB": 25,
      "APPROACH": 25,
      "LANDING_ROLL": 30,
      "DESCENT": 15,
      "CRUISE": 10,
      "TAXI": 15,
      "PUSHBACK": 10,
      "ON_STAND": 5,
      "UNKNOWN": 20
    },
    "impact_area_points": {
      "ENGINE": 30,
      "WINDSHIELD": 25,
      "RADOME": 25,
      "WING_LEADING_EDGE": 15,
      "FUSELAGE": 12,
      "LANDING_GEAR": 12,
      "UNKNOWN": 20
    },
    "evidence_points": {
      "CONFIRMED_STRIKE_WITH_REMAINS": 30,
      "SYSTEM_WARNING": 30,
      "ABNORMAL_NOISE_VIBRATION": 20,
      "SUSPECTED_ONLY": 15,
      "NO_ABNORMALITY": 5
    },
    "bird_info_points": {
      "LARGE_BIRD": 20,
      "FLOCK": 25,
      "MEDIUM_SMALL_SINGLE": 10,
      "UNKNOWN": 12
    },
    "ops_impact_points": {
      "RTO_OR_RTB": 25,
      "BLOCKING_RUNWAY_OR_TAXIWAY": 20,
      "REQUEST_MAINT_CHECK": 10,
      "NO_OPS_IMPACT": 0,
      "UNKNOWN": 8
    }
  },

  "rules": [
    {
      "id": "BS-K1-ENGINE-CRITICAL",
      "priority": 10,
      "when": {
        "all": [
          { "in": ["phase", ["TAKEOFF_ROLL", "INITIAL_CLIMB", "APPROACH", "LANDING_ROLL"]] },
          { "eq": ["impact_area", "ENGINE"] },
          { "in": ["evidence", ["CONFIRMED_STRIKE_WITH_REMAINS", "SYSTEM_WARNING", "ABNORMAL_NOISE_VIBRATION", "SUSPECTED_ONLY"]] }
        ]
      },
      "then": {
        "risk_floor": "R3",
        "explain": "Critical phase + engine involved => at least High risk (R3)."
      }
    },
    {
      "id": "BS-K2-WINDSHIELD-RADOME-CRITICAL",
      "priority": 20,
      "when": {
        "all": [
          { "in": ["phase", ["TAKEOFF_ROLL", "INITIAL_CLIMB", "APPROACH", "LANDING_ROLL"]] },
          { "in": ["impact_area", ["WINDSHIELD", "RADOME"]] },
          { "in": ["evidence", ["CONFIRMED_STRIKE_WITH_REMAINS", "SYSTEM_WARNING", "ABNORMAL_NOISE_VIBRATION", "SUSPECTED_ONLY"]] }
        ]
      },
      "then": {
        "risk_floor": "R3",
        "explain": "Critical phase + windshield/radome suspected => at least High risk (R3)."
      }
    },
    {
      "id": "BS-K3-RTO-RTB-SEVERE",
      "priority": 30,
      "when": { "any": [{ "eq": ["ops_impact", "RTO_OR_RTB"] }] },
      "then": {
        "risk_floor": "R4",
        "explain": "RTO/RTB triggered => Severe risk (R4) floor."
      }
    },
    {
      "id": "BS-K4-FLOCK-LARGE-BIRD-UPGRADE",
      "priority": 40,
      "when": {
        "any": [
          { "eq": ["bird_info", "FLOCK"] },
          { "eq": ["bird_info", "LARGE_BIRD"] }
        ]
      },
      "then": {
        "risk_boost": 8,
        "explain": "Flock/large bird increases probability of damage => score +8."
      }
    },
    {
      "id": "BS-K5-UNKNOWN-AREA-CONSERVATIVE",
      "priority": 50,
      "when": {
        "all": [
          { "eq": ["impact_area", "UNKNOWN"] },
          { "in": ["evidence", ["CONFIRMED_STRIKE_WITH_REMAINS", "SYSTEM_WARNING", "ABNORMAL_NOISE_VIBRATION", "SUSPECTED_ONLY"]] }
        ]
      },
      "then": {
        "risk_boost": 6,
        "explain": "Unknown impact area but non-trivial evidence => conservative score +6."
      }
    }
  ],

  "risk_mapping": {
    "by_score": [
      { "min": 0, "max": 29, "risk_level": "R1" },
      { "min": 30, "max": 54, "risk_level": "R2" },
      { "min": 55, "max": 74, "risk_level": "R3" },
      { "min": 75, "max": 100, "risk_level": "R4" }
    ],
    "apply_floor_override": true
  },

  "guardrails": {
    "by_risk_level": {
      "R1": {
        "requires_human_approval": true,
        "allowed_actions": ["LOG_EVENT", "REQUEST_VISUAL_CHECK", "NOTIFY_MAINT_OPTIONAL"],
        "forbidden_actions": ["AUTO_RELEASE_TO_DEPARTURE"]
      },
      "R2": {
        "requires_human_approval": true,
        "allowed_actions": ["LOG_EVENT", "REQUEST_MAINT_CHECK", "HOLD_POSITION_OR_RETURN_STAND_RECOMMEND", "NOTIFY_BIRD_CONTROL"],
        "forbidden_actions": ["AUTO_RELEASE_TO_DEPARTURE", "AUTO_CONTINUE_TAXI_IF_SUSPECTED"]
      },
      "R3": {
        "requires_human_approval": true,
        "allowed_actions": ["LOG_EVENT", "REQUEST_MAINT_CHECK_URGENT", "COORDINATE_GATE_REALLOC", "NOTIFY_BIRD_CONTROL", "RECOMMEND_STOP_TAXI"],
        "forbidden_actions": ["AUTO_RELEASE_TO_DEPARTURE", "AUTO_PUSHBACK", "AUTO_TOW"]
      },
      "R4": {
        "requires_human_approval": true,
        "allowed_actions": ["LOG_EVENT", "TRIGGER_EMERGENCY_COORDINATION", "REQUEST_MAINT_CHECK_IMMEDIATE", "COORDINATE_RUNWAY_SWEEP", "COORDINATE_GATE_REALLOC"],
        "forbidden_actions": ["AUTO_RELEASE_TO_DEPARTURE", "AUTO_PUSHBACK", "AUTO_TOW", "AUTO_CLEAR_BLOCKED_AREA"]
      }
    }
  },

  "output_schema": {
    "properties": {
      "risk_level": { "type": "string", "enum": ["R1", "R2", "R3", "R4"] },
      "score": { "type": "number" },
      "risk_floor_applied": { "type": "string", "enum": ["NONE", "R2", "R3", "R4"] },
      "explanations": { "type": "array", "items": { "type": "string" } },
      "guardrails": {
        "type": "object",
        "properties": {
          "requires_human_approval": { "type": "boolean" },
          "allowed_actions": { "type": "array", "items": { "type": "string" } },
          "forbidden_actions": { "type": "array", "items": { "type": "string" } }
        }
      }
    }
  }
}