#!/usr/bin/env node

/**
 * 机坪特情处置检查单生成脚本
 * 用法: node generate_checklist.js --flight=CA1234 --time="2025-01-30 09:15" --location="102停机位" --oil-type="燃油" --area="1-5㎡"
 */

const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, AlignmentType, BorderStyle, WidthType, HeadingLevel } = require("docx");
const fs = require("fs");

// 解析命令行参数
function parseArgs() {
  const args = {};
  process.argv.slice(2).forEach(arg => {
    const [key, value] = arg.replace(/^--/, '').split('=');
    args[key] = value || true;
  });
  return args;
}

// 生成事件编号
function generateEventId() {
  const now = new Date();
  const dateStr = now.toISOString().slice(0, 10).replace(/-/g, '');
  const seq = String(Math.floor(Math.random() * 999) + 1).padStart(3, '0');
  return `TQCZ-${dateStr}-${seq}`;
}

// 创建表格单元格
function createCell(text, options = {}) {
  return new TableCell({
    children: [new Paragraph({
      children: [new TextRun({ text, bold: options.bold || false, size: 24 })],
    })],
    shading: options.shading ? { fill: "E0E0E0" } : undefined,
    width: options.width ? { size: options.width, type: WidthType.PERCENTAGE } : undefined,
  });
}

// 创建两列表格
function createInfoTable(rows) {
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    rows: rows.map(([label, value]) => new TableRow({
      children: [
        createCell(label, { bold: true, shading: true, width: 30 }),
        createCell(value || "——", { width: 70 }),
      ],
    })),
  });
}

// 创建带复选框的项目列表
function createChecklistParagraph(text, checked = false) {
  const checkbox = checked ? "☑" : "☐";
  return new Paragraph({
    children: [new TextRun({ text: `${checkbox} ${text}`, size: 24 })],
    spacing: { after: 100 },
  });
}

// 创建章节标题
function createHeading(text, level = 2) {
  return new Paragraph({
    text,
    heading: level === 1 ? HeadingLevel.HEADING_1 : HeadingLevel.HEADING_2,
    spacing: { before: 300, after: 200 },
  });
}

// 创建分隔线
function createDivider() {
  return new Paragraph({
    children: [new TextRun({ text: "─".repeat(60), color: "999999" })],
    spacing: { before: 200, after: 200 },
  });
}

async function generateChecklist(data) {
  const eventId = data.eventId || generateEventId();
  
  const doc = new Document({
    sections: [{
      properties: {},
      children: [
        // 标题
        new Paragraph({
          children: [new TextRun({ text: "机坪特情处置检查单", bold: true, size: 40 })],
          alignment: AlignmentType.CENTER,
          spacing: { after: 400 },
        }),
        
        // 适用范围说明
        new Paragraph({
          children: [new TextRun({ 
            text: "适用范围：机坪航空器漏油、油污、渗漏等特情事件的识别、处置与闭环记录",
            italics: true, size: 20, color: "666666"
          })],
          spacing: { after: 300 },
        }),
        
        createDivider(),
        
        // 1. 事件基本信息
        createHeading("1. 事件基本信息"),
        createInfoTable([
          ["事件编号", eventId],
          ["航班号/航空器注册号", data.flight || ""],
          ["事件触发时间", data.time || ""],
          ["上报方式", data.reportMethod || "巡查"],
          ["报告人", data.reporter || ""],
          ["发现位置", data.location || ""],
        ]),
        
        createDivider(),
        
        // 2. 特情初始确认
        createHeading("2. 特情初始确认"),
        new Paragraph({
          children: [new TextRun({ text: "2.1 漏油基本情况", bold: true, size: 26 })],
          spacing: { before: 200, after: 150 },
        }),
        createInfoTable([
          ["油液类型", data.oilType || "不明"],
          ["是否持续滴漏", data.isContinuous || "否"],
          ["发动机/APU状态", data.engineStatus || "关闭"],
          ["泄漏面积评估", data.leakArea || "待评估"],
          ["漏油形态", data.leakPattern || "滴漏"],
          ["现场气象条件", data.weather || "晴"],
        ]),
        
        createDivider(),
        
        // 3. 初期风险控制措施
        createHeading("3. 初期风险控制措施"),
        createChecklistParagraph("已要求机组关车或保持关车", data.measures?.shutdownEngine),
        createChecklistParagraph("已禁止航空器滑行", data.measures?.noTaxi),
        createChecklistParagraph("已设置安全警戒区域", data.measures?.safetyZone),
        createChecklistParagraph("已排除现场点火源", data.measures?.noIgnition),
        createChecklistParagraph("已向周边航空器发布注意通告", data.measures?.notifyNearby),
        
        createDivider(),
        
        // 4. 协同单位通知记录
        createHeading("4. 协同单位通知记录"),
        new Table({
          width: { size: 100, type: WidthType.PERCENTAGE },
          rows: [
            new TableRow({
              children: [
                createCell("单位", { bold: true, shading: true }),
                createCell("是否通知", { bold: true, shading: true }),
                createCell("通知时间", { bold: true, shading: true }),
                createCell("备注", { bold: true, shading: true }),
              ],
            }),
            ...["机务", "清污/场务", "消防", "机场运行指挥", "安全监察"].map(unit => 
              new TableRow({
                children: [
                  createCell(unit),
                  createCell("☐ 是  ☐ 否"),
                  createCell(""),
                  createCell(""),
                ],
              })
            ),
          ],
        }),
        
        createDivider(),
        
        // 5. 区域隔离与现场检查
        createHeading("5. 区域隔离与现场检查"),
        new Paragraph({
          children: [new TextRun({ text: "5.1 隔离与运行限制", bold: true, size: 26 })],
          spacing: { before: 200, after: 150 },
        }),
        new Table({
          width: { size: 100, type: WidthType.PERCENTAGE },
          rows: [
            new TableRow({
              children: [
                createCell("项目", { bold: true, shading: true }),
                createCell("是/否", { bold: true, shading: true }),
                createCell("备注", { bold: true, shading: true }),
              ],
            }),
            ...["隔离区域已明确划定", "滑行道关闭执行", "停机位暂停使用", "跑道运行受影响"].map(item =>
              new TableRow({
                children: [
                  createCell(item),
                  createCell("☐ 是  ☐ 否"),
                  createCell(""),
                ],
              })
            ),
          ],
        }),
        new Paragraph({
          children: [new TextRun({ text: "5.2 现场检查要点", bold: true, size: 26 })],
          spacing: { before: 200, after: 150 },
        }),
        createChecklistParagraph("地面油污范围已确认"),
        createChecklistParagraph("周边设施未受污染"),
        createChecklistParagraph("无二次泄漏风险"),
        createChecklistParagraph("无新增安全隐患"),
        
        createDivider(),
        
        // 6. 清污处置执行情况
        createHeading("6. 清污处置执行情况"),
        createInfoTable([
          ["清污车辆到场时间", ""],
          ["作业开始时间", ""],
          ["作业结束时间", ""],
          ["清理方式", "吸附 / 化学清洗 / 吸取 / 其他"],
          ["是否符合环保要求", "是 / 否"],
        ]),
        
        createDivider(),
        
        // 7. 处置结果确认
        createHeading("7. 处置结果确认"),
        new Table({
          width: { size: 100, type: WidthType.PERCENTAGE },
          rows: [
            new TableRow({
              children: [
                createCell("检查项", { bold: true, shading: true }),
                createCell("结果", { bold: true, shading: true }),
                createCell("备注", { bold: true, shading: true }),
              ],
            }),
            ...["泄漏已停止", "地面无残留油污", "表面摩擦系数符合要求", "现场检查合格"].map(item =>
              new TableRow({
                children: [
                  createCell(item),
                  createCell("☐ 是  ☐ 否"),
                  createCell(""),
                ],
              })
            ),
          ],
        }),
        
        createDivider(),
        
        // 8. 区域恢复与运行返还
        createHeading("8. 区域恢复与运行返还"),
        createChecklistParagraph("已解除现场警戒"),
        createChecklistParagraph("已恢复滑行道使用"),
        createChecklistParagraph("已恢复停机位使用"),
        createChecklistParagraph("已通知管制/运控运行恢复"),
        
        createDivider(),
        
        // 9. 运行影响评估
        createHeading("9. 运行影响评估"),
        createInfoTable([
          ["航班延误情况", ""],
          ["航班调整/取消", ""],
          ["机坪运行影响", ""],
          ["跑道/滑行路线调整", ""],
        ]),
        
        createDivider(),
        
        // 10. 事件总结与改进建议
        createHeading("10. 事件总结与改进建议"),
        new Paragraph({
          children: [new TextRun({ text: "事件经过简述：", bold: true, size: 24 })],
          spacing: { after: 100 },
        }),
        new Paragraph({
          children: [new TextRun({ text: data.summary || "（待填写）", size: 24 })],
          spacing: { after: 200 },
        }),
        new Paragraph({
          children: [new TextRun({ text: "处置效果评估：", bold: true, size: 24 })],
          spacing: { after: 100 },
        }),
        new Paragraph({
          children: [new TextRun({ text: "（待填写）", size: 24 })],
          spacing: { after: 200 },
        }),
        new Paragraph({
          children: [new TextRun({ text: "后续改进建议：", bold: true, size: 24 })],
          spacing: { after: 100 },
        }),
        new Paragraph({
          children: [new TextRun({ text: "（待填写）", size: 24 })],
          spacing: { after: 200 },
        }),
        
        createDivider(),
        
        // 11. 签字与存档
        createHeading("11. 签字与存档"),
        new Table({
          width: { size: 100, type: WidthType.PERCENTAGE },
          rows: [
            new TableRow({
              children: [
                createCell("角色", { bold: true, shading: true }),
                createCell("姓名", { bold: true, shading: true }),
                createCell("签字", { bold: true, shading: true }),
                createCell("时间", { bold: true, shading: true }),
              ],
            }),
            ...["现场负责人", "机务代表", "清污/场务代表", "消防代表", "机场运行指挥"].map(role =>
              new TableRow({
                children: [
                  createCell(role),
                  createCell(""),
                  createCell(""),
                  createCell(""),
                ],
              })
            ),
          ],
        }),
        
        createDivider(),
        
        // 说明
        new Paragraph({
          children: [new TextRun({ 
            text: "说明：本检查单应随事件处置过程同步填写，事件关闭后统一归档，用于运行复盘与安全审计。",
            italics: true, size: 20, color: "666666"
          })],
          spacing: { before: 200 },
        }),
      ],
    }],
  });
  
  return doc;
}

// 主函数
async function main() {
  const args = parseArgs();
  
  const data = {
    flight: args.flight,
    time: args.time,
    location: args.location,
    oilType: args['oil-type'],
    leakArea: args.area,
    reportMethod: args['report-method'],
    reporter: args.reporter,
    isContinuous: args.continuous,
    engineStatus: args['engine-status'],
    leakPattern: args.pattern,
    weather: args.weather,
    summary: args.summary,
  };
  
  const outputFile = args.output || `checklist_${data.flight || 'incident'}_${Date.now()}.docx`;
  
  const doc = await generateChecklist(data);
  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(outputFile, buffer);
  
  console.log(`检查单已生成: ${outputFile}`);
}

main().catch(console.error);
