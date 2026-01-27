import { useCallback } from 'react';
import { useSessionStore } from '../stores/sessionStore';

// 生成 Markdown 报告内容
function generateMarkdownReport(state: ReturnType<typeof useSessionStore.getState>): string {
  const { incident, riskAssessment, spatialAnalysis, flightImpact, checklist, actions, messages } = state;

  const lines: string[] = [];

  // 标题
  lines.push('# 机场特情处置报告');
  lines.push('');
  lines.push(`**生成时间**: ${new Date().toLocaleString('zh-CN')}`);
  lines.push(`**会话ID**: ${state.sessionId || 'N/A'}`);
  lines.push('');

  // 事件摘要
  lines.push('## 一、事件摘要');
  lines.push('');
  if (incident) {
    lines.push(`- **航班号**: ${incident.flight_no || 'N/A'}`);
    lines.push(`- **位置**: ${incident.position || 'N/A'}`);
    lines.push(`- **事件类型**: ${incident.scenario_type === 'oil_spill' ? '油液泄漏' : incident.scenario_type || 'N/A'}`);
    if (incident.fluid_type) {
      const fluidTypeMap: Record<string, string> = {
        'FUEL': '燃油',
        'HYDRAULIC': '液压油',
        'OIL': '润滑油',
      };
      lines.push(`- **油液类型**: ${fluidTypeMap[incident.fluid_type] || incident.fluid_type}`);
    }
    if (incident.engine_status) {
      lines.push(`- **发动机状态**: ${incident.engine_status === 'RUNNING' ? '运转中' : '已停止'}`);
    }
    if (incident.continuous !== undefined) {
      lines.push(`- **泄漏状态**: ${incident.continuous ? '持续泄漏' : '已停止'}`);
    }
    lines.push(`- **事件时间**: ${incident.incident_time || 'N/A'}`);
  } else {
    lines.push('*暂无事件信息*');
  }
  lines.push('');

  // 风险评估
  lines.push('## 二、风险评估');
  lines.push('');
  if (riskAssessment) {
    lines.push(`### 2.1 评估结果`);
    lines.push('');
    lines.push(`- **风险等级**: ${riskAssessment.level}`);
    lines.push(`- **风险评分**: ${riskAssessment.score}/100`);
    lines.push('');

    if (riskAssessment.rules_triggered && riskAssessment.rules_triggered.length > 0) {
      lines.push(`### 2.2 触发规则`);
      lines.push('');
      riskAssessment.rules_triggered.forEach((rule, idx) => {
        lines.push(`${idx + 1}. ${rule}`);
      });
      lines.push('');
    }

    if (riskAssessment.cross_validation) {
      lines.push(`### 2.3 双引擎验证`);
      lines.push('');
      lines.push(`| 引擎 | 结果 | 置信度 |`);
      lines.push(`|------|------|--------|`);
      lines.push(`| 规则引擎 | ${riskAssessment.cross_validation.rule_result} | ${riskAssessment.cross_validation.rule_score}分 |`);
      lines.push(`| LLM验证 | ${riskAssessment.cross_validation.llm_result} | ${Math.round(riskAssessment.cross_validation.llm_confidence * 100)}% |`);
      lines.push('');
      lines.push(`**验证结果**: ${riskAssessment.cross_validation.consistent ? '✓ 一致' : '⚠ 不一致'}`);
      lines.push('');
    }
  } else {
    lines.push('*暂无风险评估数据*');
  }
  lines.push('');

  // 影响分析
  lines.push('## 三、影响分析');
  lines.push('');

  if (spatialAnalysis) {
    lines.push(`### 3.1 空间影响`);
    lines.push('');
    lines.push(`- **受影响机位**: ${spatialAnalysis.affected_stands.join(', ') || '无'}`);
    lines.push(`- **受影响滑行道**: ${spatialAnalysis.affected_taxiways.join(', ') || '无'}`);
    lines.push(`- **受影响跑道**: ${spatialAnalysis.affected_runways.join(', ') || '无'}`);
    lines.push(`- **影响半径**: ${spatialAnalysis.impact_radius} 级`);
    lines.push('');
  }

  if (flightImpact) {
    lines.push(`### 3.2 航班影响`);
    lines.push('');
    lines.push(`- **受影响航班数**: ${flightImpact.affected_count} 架次`);
    lines.push(`- **累计延误时间**: ${flightImpact.total_delay_minutes} 分钟`);
    lines.push(`- **平均延误**: ${flightImpact.average_delay} 分钟/架次`);
    lines.push('');

    if (flightImpact.delay_distribution) {
      lines.push(`#### 延误分布`);
      lines.push('');
      lines.push(`- 严重延误 (≥60分钟): ${flightImpact.delay_distribution.severe} 架次`);
      lines.push(`- 中等延误 (20-59分钟): ${flightImpact.delay_distribution.moderate} 架次`);
      lines.push(`- 轻微延误 (<20分钟): ${flightImpact.delay_distribution.minor} 架次`);
      lines.push('');
    }

    if (flightImpact.flights && flightImpact.flights.length > 0) {
      lines.push(`#### 受影响航班明细`);
      lines.push('');
      lines.push(`| 航班号 | 机型 | 机位 | 计划时间 | 延误(分钟) | 严重程度 |`);
      lines.push(`|--------|------|------|----------|------------|----------|`);
      flightImpact.flights.forEach((flight) => {
        const severityMap: Record<string, string> = {
          severe: '严重',
          moderate: '中等',
          minor: '轻微',
        };
        lines.push(`| ${flight.callsign} | ${flight.aircraft_type} | ${flight.stand} | ${flight.scheduled_time?.split(' ')[1] || 'N/A'} | ${flight.delay} | ${severityMap[flight.severity] || flight.severity} |`);
      });
      lines.push('');
    }
  }

  if (!spatialAnalysis && !flightImpact) {
    lines.push('*暂无影响分析数据*');
    lines.push('');
  }

  // 处置清单
  lines.push('## 四、处置清单');
  lines.push('');

  if (checklist && checklist.length > 0) {
    const grouped = checklist.reduce((acc, item) => {
      if (!acc[item.phase]) acc[item.phase] = [];
      acc[item.phase].push(item);
      return acc;
    }, {} as Record<string, typeof checklist>);

    const phaseNames: Record<string, string> = {
      P1: '信息收集',
      P2: '即时响应',
      P3: '后续处理',
    };

    Object.entries(grouped).forEach(([phase, items]) => {
      const completed = items.filter((i) => i.completed).length;
      lines.push(`### ${phase} - ${phaseNames[phase] || phase} (${completed}/${items.length})`);
      lines.push('');
      items.forEach((item) => {
        const status = item.completed ? '✓' : '☐';
        const dept = item.department ? ` [${item.department}]` : '';
        lines.push(`- [${status}] ${item.item}${dept}`);
      });
      lines.push('');
    });
  } else {
    lines.push('*暂无处置清单*');
    lines.push('');
  }

  // 执行动作
  lines.push('## 五、执行记录');
  lines.push('');

  if (actions && actions.length > 0) {
    lines.push(`| 时间 | 动作 | 状态 | 部门 |`);
    lines.push(`|------|------|------|------|`);
    actions.forEach((action) => {
      const statusMap: Record<string, string> = {
        completed: '✓ 完成',
        pending: '⏳ 待处理',
        failed: '✗ 失败',
      };
      lines.push(`| ${action.time || 'N/A'} | ${action.action} | ${statusMap[action.status] || action.status} | ${action.department || '-'} |`);
    });
    lines.push('');
  } else {
    lines.push('*暂无执行记录*');
    lines.push('');
  }

  // 对话记录
  lines.push('## 六、对话记录');
  lines.push('');

  if (messages && messages.length > 0) {
    messages.forEach((msg) => {
      const role = msg.role === 'user' ? '👤 用户' : '🤖 Agent';
      const time = msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString('zh-CN') : '';
      lines.push(`### ${role} ${time ? `(${time})` : ''}`);
      lines.push('');
      lines.push(msg.content);
      lines.push('');
    });
  } else {
    lines.push('*暂无对话记录*');
    lines.push('');
  }

  // 页脚
  lines.push('---');
  lines.push('');
  lines.push('*此报告由 AERO Agent 智能应急响应系统自动生成*');

  return lines.join('\n');
}

// 生成 HTML 报告内容（用于 PDF 导出）
function generateHTMLReport(state: ReturnType<typeof useSessionStore.getState>): string {
  const markdown = generateMarkdownReport(state);

  // 简单的 Markdown 到 HTML 转换
  let html = markdown
    .replace(/^# (.*$)/gm, '<h1 style="color: #e6edf3; border-bottom: 1px solid #30363d; padding-bottom: 8px;">$1</h1>')
    .replace(/^## (.*$)/gm, '<h2 style="color: #e6edf3; margin-top: 24px;">$1</h2>')
    .replace(/^### (.*$)/gm, '<h3 style="color: #e6edf3; margin-top: 16px;">$1</h3>')
    .replace(/^#### (.*$)/gm, '<h4 style="color: #8b949e;">$1</h4>')
    .replace(/\*\*(.*?)\*\*/g, '<strong style="color: #e6edf3;">$1</strong>')
    .replace(/\*(.*?)\*/g, '<em style="color: #8b949e;">$1</em>')
    .replace(/^- (.*$)/gm, '<li style="color: #e6edf3; margin: 4px 0;">$1</li>')
    .replace(/(<li.*<\/li>\n)+/g, '<ul style="list-style: disc; padding-left: 20px; margin: 8px 0;">$&</ul>')
    .replace(/^---$/gm, '<hr style="border: none; border-top: 1px solid #30363d; margin: 24px 0;">')
    .replace(/\n\n/g, '</p><p style="color: #e6edf3; margin: 8px 0;">')
    .replace(/✓/g, '<span style="color: #238636;">✓</span>')
    .replace(/☐/g, '<span style="color: #8b949e;">☐</span>')
    .replace(/✗/g, '<span style="color: #f85149;">✗</span>')
    .replace(/⚠/g, '<span style="color: #d29922;">⚠</span>');

  // 处理表格
  const tableRegex = /\|(.+)\|\n\|[-\s|]+\|\n((?:\|.+\|\n?)+)/g;
  html = html.replace(tableRegex, (_match, header, body) => {
    const headerCells = header.split('|').filter((c: string) => c.trim()).map((c: string) =>
      `<th style="background: #21262d; color: #e6edf3; padding: 8px; border: 1px solid #30363d;">${c.trim()}</th>`
    ).join('');

    const bodyRows = body.trim().split('\n').map((row: string) => {
      const cells = row.split('|').filter((c: string) => c.trim()).map((c: string) =>
        `<td style="padding: 8px; border: 1px solid #30363d; color: #e6edf3;">${c.trim()}</td>`
      ).join('');
      return `<tr>${cells}</tr>`;
    }).join('');

    return `<table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
      <thead><tr>${headerCells}</tr></thead>
      <tbody>${bodyRows}</tbody>
    </table>`;
  });

  return `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <style>
        body {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          background: #0d1117;
          color: #e6edf3;
          padding: 40px;
          line-height: 1.6;
        }
        h1, h2, h3, h4 { margin: 0; }
        p { margin: 8px 0; }
        ul { margin: 8px 0; }
      </style>
    </head>
    <body>
      ${html}
    </body>
    </html>
  `;
}

export function useExport() {
  const state = useSessionStore.getState();

  // 导出 Markdown
  const exportMarkdown = useCallback(() => {
    const markdown = generateMarkdownReport(state);
    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `AERO_Report_${new Date().toISOString().split('T')[0]}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, [state]);

  // 导出 PDF
  const exportPDF = useCallback(async () => {
    try {
      // 动态导入 html2pdf.js
      const html2pdf = (await import('html2pdf.js')).default;

      const html = generateHTMLReport(state);
      const container = document.createElement('div');
      container.innerHTML = html;
      container.style.position = 'absolute';
      container.style.left = '-9999px';
      document.body.appendChild(container);

      const opt = {
        margin: 10,
        filename: `AERO_Report_${new Date().toISOString().split('T')[0]}.pdf`,
        image: { type: 'jpeg' as const, quality: 0.98 },
        html2canvas: {
          scale: 2,
          backgroundColor: '#0d1117',
        },
        jsPDF: {
          unit: 'mm' as const,
          format: 'a4' as const,
          orientation: 'portrait' as const,
        },
      };

      await html2pdf().set(opt).from(container).save();
      document.body.removeChild(container);
    } catch (error) {
      console.error('PDF export failed:', error);
      throw error;
    }
  }, [state]);

  return {
    exportMarkdown,
    exportPDF,
  };
}
