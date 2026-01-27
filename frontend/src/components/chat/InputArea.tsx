import { useState } from 'react';
import { Input, Button, Select, Space } from 'antd';
import { SendOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { useUIStore } from '../../stores/uiStore';
import { useSession } from '../../hooks/useSession';
import { presetScenarios } from '../../services/mockData';

const { TextArea } = Input;

export function InputArea() {
  const { bigScreenMode, demoMode } = useUIStore();
  const { isLoading, sendMessage, loadPresetScenario, startSession } = useSession();
  const [input, setInput] = useState('');
  const [selectedScenario, setSelectedScenario] = useState<string | undefined>(undefined);

  // 发送消息
  const handleSend = () => {
    if (!input.trim() || isLoading) return;
    sendMessage(input);
    setInput('');
  };

  // 加载预设场景
  const handleLoadScenario = () => {
    if (!selectedScenario) return;
    loadPresetScenario(selectedScenario);
    setSelectedScenario(undefined);
  };

  // 快速开始
  const handleQuickStart = async () => {
    await startSession();
    if (demoMode) {
      // 演示模式自动发送默认场景
      const defaultScenario = presetScenarios[0];
      if (defaultScenario) {
        setTimeout(() => {
          sendMessage(defaultScenario.initial_message);
        }, 500);
      }
    }
  };

  return (
    <div
      style={{
        borderTop: '1px solid var(--border)',
        padding: bigScreenMode ? '16px' : '12px',
      }}
    >
      {/* 预设场景选择 */}
      <div style={{ marginBottom: bigScreenMode ? 12 : 8 }}>
        <Space.Compact style={{ width: '100%' }}>
          <Select
            placeholder="选择预设场景"
            value={selectedScenario}
            onChange={setSelectedScenario}
            style={{ flex: 1 }}
            options={presetScenarios.map((s) => ({
              value: s.id,
              label: (
                <div>
                  <div style={{ fontWeight: 500 }}>{s.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                    {s.description}
                  </div>
                </div>
              ),
            }))}
            optionLabelProp="label"
            size={bigScreenMode ? 'large' : 'middle'}
          />
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            onClick={selectedScenario ? handleLoadScenario : handleQuickStart}
            disabled={isLoading}
            size={bigScreenMode ? 'large' : 'middle'}
          >
            {selectedScenario ? '加载' : '快速开始'}
          </Button>
        </Space.Compact>
      </div>

      {/* 文本输入 */}
      <div style={{ display: 'flex', gap: 8 }}>
        <TextArea
          placeholder="输入事件描述，如：CES2876在501机位漏油了"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onPressEnter={(e) => {
            if (!e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          autoSize={{ minRows: 1, maxRows: 3 }}
          disabled={isLoading}
          style={{
            flex: 1,
            background: 'var(--bg-primary)',
            borderColor: 'var(--border)',
            color: 'var(--text-primary)',
            fontSize: bigScreenMode ? 14 : 13,
          }}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSend}
          loading={isLoading}
          disabled={!input.trim()}
          size={bigScreenMode ? 'large' : 'middle'}
          style={{ alignSelf: 'flex-end' }}
        >
          发送
        </Button>
      </div>

      {/* 提示 */}
      <div
        style={{
          marginTop: 8,
          fontSize: bigScreenMode ? 12 : 10,
          color: 'var(--text-secondary)',
        }}
      >
        提示：Enter 发送，Shift + Enter 换行
      </div>
    </div>
  );
}
