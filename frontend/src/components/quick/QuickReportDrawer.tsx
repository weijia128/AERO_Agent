import { useMemo, useRef, useState } from 'react';
import { Drawer, Form, Input, Select, Switch, Button, Space, Divider, Typography, message } from 'antd';
import { api, type StreamEvent } from '../../services/api';
import ReactMarkdown from 'react-markdown';

const { Text } = Typography;
const { TextArea } = Input;

type ScenarioType = 'oil_spill' | 'bird_strike' | 'fod';

interface QuickReportDrawerProps {
  open: boolean;
  onClose: () => void;
}

const scenarioOptions = [
  { value: 'oil_spill', label: '漏油' },
  { value: 'bird_strike', label: '鸟击' },
  { value: 'fod', label: 'FOD 外来物' },
];

const oilFluidOptions = [
  { value: 'FUEL', label: '燃油' },
  { value: 'HYDRAULIC', label: '液压油' },
  { value: 'OIL', label: '发动机滑油' },
  { value: 'UNKNOWN', label: '不明' },
];

const engineOptions = [
  { value: 'RUNNING', label: '发动机运转中' },
  { value: 'STOPPED', label: '发动机已关闭' },
  { value: 'APU', label: '仅 APU 运行' },
];

const leakSizeOptions = [
  { value: 'SMALL', label: '小面积 (<1m²)' },
  { value: 'MEDIUM', label: '中面积 (1-5m²)' },
  { value: 'LARGE', label: '大面积 (>5m²)' },
];

const birdEventOptions = [
  { value: '确认鸟击', label: '确认鸟击' },
  { value: '疑似鸟击', label: '疑似鸟击' },
];

const birdPhaseOptions = [
  { value: 'PUSHBACK', label: '推出' },
  { value: 'TAXI', label: '滑行' },
  { value: 'TAKEOFF_ROLL', label: '起飞滑跑' },
  { value: 'INITIAL_CLIMB', label: '起飞后爬升' },
  { value: 'CRUISE', label: '巡航' },
  { value: 'DESCENT', label: '下降' },
  { value: 'APPROACH', label: '进近' },
  { value: 'LANDING_ROLL', label: '落地滑跑' },
  { value: 'ON_STAND', label: '停机位' },
  { value: 'UNKNOWN', label: '不明' },
];

const birdEvidenceOptions = [
  { value: 'CONFIRMED_STRIKE_WITH_REMAINS', label: '确认撞击有残留' },
  { value: 'SYSTEM_WARNING', label: '系统告警' },
  { value: 'ABNORMAL_NOISE_VIBRATION', label: '异响/振动' },
  { value: 'SUSPECTED_ONLY', label: '仅怀疑' },
  { value: 'NO_ABNORMALITY', label: '无异常' },
];

const birdInfoOptions = [
  { value: 'LARGE_BIRD', label: '大型鸟类' },
  { value: 'FLOCK', label: '鸟群' },
  { value: 'MEDIUM_SMALL_SINGLE', label: '中小型单只' },
  { value: 'UNKNOWN', label: '不明' },
];

const birdOpsOptions = [
  { value: 'RTO_OR_RTB', label: '中断起飞/返航' },
  { value: 'BLOCKING_RUNWAY_OR_TAXIWAY', label: '占用跑道/滑行道' },
  { value: 'REQUEST_MAINT_CHECK', label: '请求机务检查' },
  { value: 'NO_OPS_IMPACT', label: '不影响运行' },
  { value: 'UNKNOWN', label: '不明' },
];

const fodAreaOptions = [
  { value: 'RUNWAY', label: '跑道' },
  { value: 'TAXIWAY', label: '滑行道' },
  { value: 'APRON', label: '机坪' },
  { value: 'UNKNOWN', label: '不明' },
];

const fodTypeOptions = [
  { value: 'METAL', label: '金属类' },
  { value: 'PLASTIC_RUBBER', label: '塑料/橡胶' },
  { value: 'STONE_GRAVEL', label: '石块/砂石' },
  { value: 'LIQUID', label: '油液/液体异物' },
  { value: 'UNKNOWN', label: '不明' },
];

const fodPresenceOptions = [
  { value: 'ON_SURFACE', label: '仍在道面' },
  { value: 'REMOVED', label: '已移除' },
  { value: 'MOVING_BLOWING', label: '被风吹动/移动' },
  { value: 'UNKNOWN', label: '不明' },
];

const fodOpsOptions = [
  { value: 'RUNWAY_CLOSED', label: '跑道关闭' },
  { value: 'TAXIWAY_BLOCKED', label: '滑行道封闭' },
  { value: 'APRON_RESTRICTED', label: '机坪限制' },
  { value: 'MINOR_IMPACT', label: '轻微影响' },
  { value: 'NO_IMPACT', label: '不影响运行' },
  { value: 'UNKNOWN', label: '不明' },
];

const fodRelatedOptions = [
  { value: 'YES', label: '是' },
  { value: 'NO', label: '否' },
  { value: 'UNKNOWN', label: '不明' },
];

export function QuickReportDrawer({ open, onClose }: QuickReportDrawerProps) {
  const [form] = Form.useForm();
  const [scenarioType, setScenarioType] = useState<ScenarioType>('oil_spill');
  const [fullText, setFullText] = useState('');
  const [parseNote, setParseNote] = useState('');
  const [parsing, setParsing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [reportContent, setReportContent] = useState('');
  const [showFullReport, setShowFullReport] = useState(false);
  const autoConfirmRef = useRef(false);
  const sessionIdRef = useRef('');

  const triggerAutoConfirm = (sessionId: string) => {
    if (!sessionId || autoConfirmRef.current) {
      return;
    }
    autoConfirmRef.current = true;
    api.chatStream(
      {
        session_id: sessionId,
        message: '完毕',
      },
      {
        onNodeUpdate: (followEvent: StreamEvent) => {
          if (followEvent.final_answer) {
            setReportContent(followEvent.final_answer);
          }
          if (followEvent.session_id) {
            sessionIdRef.current = followEvent.session_id;
          }
        },
        onComplete: (followEvent: StreamEvent) => {
          if (followEvent.final_answer) {
            setReportContent(followEvent.final_answer);
          }
          setSubmitting(false);
        },
        onError: () => {
          autoConfirmRef.current = false;
          setSubmitting(false);
        },
      }
    );
  };

  const resetAll = () => {
    form.resetFields();
    setScenarioType('oil_spill');
    setFullText('');
    setParseNote('');
    setParsing(false);
    setSubmitting(false);
    setReportContent('');
    setShowFullReport(false);
    autoConfirmRef.current = false;
  };

  const handleClose = () => {
    resetAll();
    onClose();
  };

  const requiredFields = useMemo(() => {
    if (scenarioType === 'oil_spill') {
      return ['flight_no', 'position', 'fluid_type', 'continuous', 'engine_status'];
    }
    if (scenarioType === 'bird_strike') {
      return ['flight_no', 'position', 'event_type', 'affected_part', 'current_status', 'crew_request'];
    }
    return ['location_area', 'position', 'fod_type', 'presence', 'report_time', 'fod_size'];
  }, [scenarioType]);

  const handleScenarioChange = (value: ScenarioType) => {
    setScenarioType(value);
    form.resetFields();
    setParseNote('');
    setReportContent('');
    setShowFullReport(false);
  };

  const handleParse = async () => {
    if (!fullText.trim()) {
      message.warning('请先输入完整描述');
      return;
    }
    setParsing(true);
    try {
      const result = await api.parseEvent({ message: fullText, scenario_type: scenarioType });
      if (result.scenario_type) {
        setScenarioType(result.scenario_type as ScenarioType);
      }
      if (result.incident) {
        form.setFieldsValue(result.incident);
      }
      setParseNote(result.enrichment_observation || '');
      message.success('已自动提取字段');
    } catch (err) {
      message.error(err instanceof Error ? err.message : '解析失败');
    } finally {
      setParsing(false);
    }
  };

  const buildMessage = (values: Record<string, unknown>) => {
    if (fullText.trim()) {
      return fullText.trim();
    }
    if (scenarioType === 'oil_spill') {
      const fluid = oilFluidOptions.find((o) => o.value === values.fluid_type)?.label || '油液';
      const engine = engineOptions.find((o) => o.value === values.engine_status)?.label || '状态未知';
      const continuous = values.continuous ? '持续泄漏' : '非持续泄漏';
      const leakSize = leakSizeOptions.find((o) => o.value === values.leak_size)?.label || '面积未知';
      return `${values.flight_no || ''}在${values.position || ''}发生${fluid}泄漏，${continuous}，${engine}，泄漏面积${leakSize}`;
    }
    if (scenarioType === 'bird_strike') {
      return `${values.flight_no || ''}在${values.position || ''}${values.event_type || ''}，影响部位${values.affected_part || ''}，当前状态${values.current_status || ''}，机组请求${values.crew_request || ''}`;
    }
    return `FOD发现于${values.position || ''}（${values.location_area || ''}），类型${values.fod_type || ''}，状态${values.presence || ''}，尺寸${values.fod_size || ''}，汇报时间${values.report_time || ''}`;
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      setReportContent('');
      setShowFullReport(false);
      autoConfirmRef.current = false;
      sessionIdRef.current = '';
      const messageText = buildMessage(values);
      api.startSessionStream(
        {
          message: messageText,
          scenario_type: scenarioType,
        },
        {
          onNodeUpdate: (event: StreamEvent) => {
            if (event.session_id) {
              sessionIdRef.current = event.session_id;
            }
            if (event.final_answer) {
              setReportContent(event.final_answer);
            }
            if (event.next_question) {
              triggerAutoConfirm(event.session_id || sessionIdRef.current);
            }
          },
          onComplete: (event: StreamEvent) => {
            if (event.session_id) {
              sessionIdRef.current = event.session_id;
            }
            if (event.final_answer) {
              setReportContent(event.final_answer);
            }
            if (event.next_question) {
              triggerAutoConfirm(event.session_id || sessionIdRef.current);
              return;
            }
            setSubmitting(false);
          },
          onError: (error) => {
            message.error(error instanceof Error ? error.message : '生成失败');
            setSubmitting(false);
          },
        }
      );
    } catch {
      // validation errors handled by form
      setSubmitting(false);
    } finally {
      // handled by stream callbacks
    }
  };

  return (
    <Drawer
      title="快速生成工单"
      placement="right"
      width={720}
      onClose={handleClose}
      open={open}
      destroyOnClose
      bodyStyle={{ paddingBottom: 80 }}
    >
      <Form form={form} layout="vertical" requiredMark="optional">
        <Form.Item label="特情场景">
          <Select
            options={scenarioOptions}
            value={scenarioType}
            onChange={handleScenarioChange}
          />
        </Form.Item>

        <Form.Item label="完整特情描述">
          <Space direction="vertical" style={{ width: '100%' }}>
            <TextArea
              value={fullText}
              onChange={(e) => setFullText(e.target.value)}
              rows={4}
              placeholder="粘贴或输入完整特情描述，点击自动提取字段"
            />
            <Button onClick={handleParse} loading={parsing}>
              自动提取字段
            </Button>
            {parseNote && (
              <div
                style={{
                  padding: '8px 10px',
                  background: 'var(--bg-primary)',
                  borderRadius: 6,
                  border: '1px solid var(--border)',
                  color: 'var(--text-secondary)',
                  fontSize: 12,
                  whiteSpace: 'pre-wrap',
                }}
              >
                提取说明: {parseNote}
              </div>
            )}
          </Space>
        </Form.Item>

        <Divider orientation="left">必填信息</Divider>

        {scenarioType === 'oil_spill' && (
          <>
            <Form.Item name="flight_no" label="航班号" rules={[{ required: true, message: '请输入航班号' }]}>
              <Input placeholder="如: MU5728" />
            </Form.Item>
            <Form.Item name="position" label="航空器位置" rules={[{ required: true, message: '请输入位置' }]}>
              <Input placeholder="如: 217 / 滑行道A3" />
            </Form.Item>
            <Form.Item name="fluid_type" label="油液类型" rules={[{ required: true, message: '请选择油液类型' }]}>
              <Select options={oilFluidOptions} />
            </Form.Item>
            <Form.Item name="continuous" label="是否持续滴漏" valuePropName="checked" rules={[{ required: true, message: '请选择' }]}>
              <Switch checkedChildren="是" unCheckedChildren="否" />
            </Form.Item>
            <Form.Item name="engine_status" label="发动机/APU状态" rules={[{ required: true, message: '请选择发动机状态' }]}>
              <Select options={engineOptions} />
            </Form.Item>
            <Form.Item name="leak_size" label="泄漏面积">
              <Select options={leakSizeOptions} allowClear />
            </Form.Item>
          </>
        )}

        {scenarioType === 'bird_strike' && (
          <>
            <Form.Item name="flight_no" label="航班号" rules={[{ required: true, message: '请输入航班号' }]}>
              <Input placeholder="如: CA1234" />
            </Form.Item>
            <Form.Item name="position" label="发生位置" rules={[{ required: true, message: '请输入位置' }]}>
              <Input placeholder="如: 跑道05R" />
            </Form.Item>
            <Form.Item name="event_type" label="事件类型" rules={[{ required: true, message: '请选择事件类型' }]}>
              <Select options={birdEventOptions} />
            </Form.Item>
            <Form.Item name="affected_part" label="影响部位" rules={[{ required: true, message: '请输入影响部位' }]}>
              <Input placeholder="如: 发动机/风挡" />
            </Form.Item>
            <Form.Item name="current_status" label="当前状态" rules={[{ required: true, message: '请输入当前状态' }]}>
              <Input placeholder="如: 正常/待检查" />
            </Form.Item>
            <Form.Item name="crew_request" label="机组请求" rules={[{ required: true, message: '请输入机组请求' }]}>
              <Input placeholder="如: 返航/检查/支援" />
            </Form.Item>
            <Form.Item name="tail_no" label="机号">
              <Input placeholder="如: B-1234" />
            </Form.Item>
            <Form.Item name="phase" label="飞行阶段">
              <Select options={birdPhaseOptions} allowClear />
            </Form.Item>
            <Form.Item name="evidence" label="迹象强度">
              <Select options={birdEvidenceOptions} allowClear />
            </Form.Item>
            <Form.Item name="bird_info" label="鸟类信息">
              <Select options={birdInfoOptions} allowClear />
            </Form.Item>
            <Form.Item name="ops_impact" label="运行影响">
              <Select options={birdOpsOptions} allowClear />
            </Form.Item>
            <Form.Item name="suspend_resources" label="是否暂停机坪资源" valuePropName="checked">
              <Switch checkedChildren="是" unCheckedChildren="否" />
            </Form.Item>
            <Form.Item name="followup_required" label="是否触发后续检查/通报" valuePropName="checked">
              <Switch checkedChildren="是" unCheckedChildren="否" />
            </Form.Item>
          </>
        )}

        {scenarioType === 'fod' && (
          <>
            <Form.Item name="location_area" label="位置类别" rules={[{ required: true, message: '请选择位置类别' }]}>
              <Select options={fodAreaOptions} />
            </Form.Item>
            <Form.Item name="position" label="具体位置" rules={[{ required: true, message: '请输入具体位置' }]}>
              <Input placeholder="如: 跑道02L/滑行道A3" />
            </Form.Item>
            <Form.Item name="fod_type" label="FOD 种类" rules={[{ required: true, message: '请选择种类' }]}>
              <Select options={fodTypeOptions} />
            </Form.Item>
            <Form.Item name="presence" label="是否仍在道面" rules={[{ required: true, message: '请选择状态' }]}>
              <Select options={fodPresenceOptions} />
            </Form.Item>
            <Form.Item name="report_time" label="汇报时间" rules={[{ required: true, message: '请输入汇报时间' }]}>
              <Input placeholder="如: 14:32" />
            </Form.Item>
            <Form.Item name="fod_size" label="FOD 尺寸" rules={[{ required: true, message: '请输入尺寸' }]}>
              <Input placeholder="如: SMALL / 螺母" />
            </Form.Item>
            <Form.Item name="ops_impact" label="运行即时影响">
              <Select options={fodOpsOptions} allowClear />
            </Form.Item>
            <Form.Item name="related_event" label="是否与前序事件有关">
              <Select options={fodRelatedOptions} allowClear />
            </Form.Item>
          </>
        )}

        <Divider />

        <Space style={{ justifyContent: 'flex-end', width: '100%' }}>
          <Text type="secondary">
            必填项：{requiredFields.length} 项
          </Text>
          <Button onClick={handleClose}>取消</Button>
          <Button type="primary" onClick={handleSubmit} loading={submitting}>
            生成工单
          </Button>
        </Space>

        {reportContent && (
          <>
            <Divider orientation="left">工单概览</Divider>
            {!showFullReport && (
              <>
                <div
                  style={{
                    padding: '10px 12px',
                    background: 'var(--bg-primary)',
                    borderRadius: 6,
                    border: '1px solid var(--border)',
                    fontSize: 12,
                    color: 'var(--text-secondary)',
                    whiteSpace: 'pre-wrap',
                    maxHeight: 160,
                    overflow: 'hidden',
                  }}
                >
                  {reportContent.split('\n').slice(0, 8).join('\n')}
                </div>
                <Button type="link" onClick={() => setShowFullReport(true)}>
                  查看完整工单 →
                </Button>
              </>
            )}
            {showFullReport && (
              <>
                <div
                  style={{
                    maxHeight: 360,
                    overflowY: 'auto',
                    padding: '10px',
                    background: 'var(--bg-primary)',
                    borderRadius: 6,
                    border: '1px solid var(--border)',
                  }}
                  className="markdown-content"
                >
                  <ReactMarkdown>{reportContent}</ReactMarkdown>
                </div>
                <Button type="link" onClick={() => setShowFullReport(false)}>
                  收起工单 ↑
                </Button>
              </>
            )}
          </>
        )}
      </Form>
    </Drawer>
  );
}
