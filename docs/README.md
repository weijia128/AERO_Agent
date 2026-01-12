# 文档目录

本文档目录已按主题分类，便于快速查找。

## 目录结构

```
docs/
├── core/                  # 核心架构文档
│   ├── ARCHITECTURE_DECISIONS.md   # 架构决策记录 (ADR)
│   └── PRODUCTION_READINESS.md     # 生产就绪评估
│
├── guides/                # 开发指南
│   ├── TOOL_DEVELOPMENT_GUIDE.md   # 工具开发指南
│   ├── refactoring_plan.md         # 项目重构计划
│   └── report_refactoring_plan.md  # 报告重构计划
│
├── deployment/            # 部署运维
│   ├── DEPLOYMENT_GUIDE.md         # 部署指南
│   └── API_DOCUMENTATION.md        # API 文档
│
├── scenarios/             # 业务场景文档
│   ├── 机坪漏油检查单_dsl_与_ui_表单设计.md  # 漏油检查单设计
│   ├── 报告数据来源分析.md                  # 报告数据来源分析
│   └── DIALOGUE_ROLE_CHANGE.md             # 对话角色变更记录
│
├── integration/           # 集成文档
│   ├── TOPOLOGY_INTEGRATION_SUMMARY.md     # 拓扑集成总结
│   ├── TOPOLOGY_CORRECTION_SUMMARY.md      # 拓扑修正总结
│   └── FLIGHT_IMPACT_INTEGRATION.md        # 飞行影响集成
│
├── bugfix/                # Bug 修复记录
│   ├── bugfix_summary.md              # Bug 修复总结
│   ├── bugfix_position_checklist.md   # 位置检查单 bug
│   └── bugfix_recursion_limit.md      # 递归限制 bug
│
└── resources/             # 资源文件
    └── 空中交通无线电通话用语.pdf
```

## 快速导航

| 主题 | 文档 |
|------|------|
| 了解系统架构 | [core/ARCHITECTURE_DECISIONS.md](core/ARCHITECTURE_DECISIONS.md) |
| 开发新工具 | [guides/TOOL_DEVELOPMENT_GUIDE.md](guides/TOOL_DEVELOPMENT_GUIDE.md) |
| 部署到生产 | [deployment/DEPLOYMENT_GUIDE.md](deployment/DEPLOYMENT_GUIDE.md) |
| API 参考 | [deployment/API_DOCUMENTATION.md](deployment/API_DOCUMENTATION.md) |
| 检查单设计 | [scenarios/机坪漏油检查单_dsl_与_ui_表单设计.md](scenarios/机坪漏油检查单_dsl_与_ui_表单设计.md) |
| 问题排查 | [bugfix/](bugfix/) |
