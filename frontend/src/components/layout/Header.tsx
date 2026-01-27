import { Switch, Button, Space, Typography, Tag, Dropdown, message } from 'antd';
import type { MenuProps } from 'antd';
import {
  ExpandOutlined,
  CompressOutlined,
  ExportOutlined,
  CloudOutlined,
  DatabaseOutlined,
  FilePdfOutlined,
  FileMarkdownOutlined,
} from '@ant-design/icons';
import { useUIStore } from '../../stores/uiStore';
import { useSessionStore } from '../../stores/sessionStore';
import { useExport } from '../../hooks/useExport';

const { Title, Text } = Typography;

export function Header() {
  const { bigScreenMode, demoMode, toggleBigScreenMode, toggleDemoMode } =
    useUIStore();
  const { fsmState } = useSessionStore();
  const { exportMarkdown, exportPDF } = useExport();

  const handleExport = async (type: 'pdf' | 'markdown') => {
    try {
      if (type === 'pdf') {
        message.loading({ content: '正在生成 PDF...', key: 'export' });
        await exportPDF();
        message.success({ content: 'PDF 导出成功', key: 'export' });
      } else {
        exportMarkdown();
        message.success({ content: 'Markdown 导出成功', key: 'export' });
      }
    } catch {
      message.error({ content: '导出失败，请重试', key: 'export' });
    }
  };

  const exportMenuItems: MenuProps['items'] = [
    {
      key: 'pdf',
      icon: <FilePdfOutlined />,
      label: '导出 PDF',
      onClick: () => handleExport('pdf'),
    },
    {
      key: 'markdown',
      icon: <FileMarkdownOutlined />,
      label: '导出 Markdown',
      onClick: () => handleExport('markdown'),
    },
  ];

  return (
    <header
      style={{
        background: 'var(--bg-card)',
        borderBottom: '1px solid var(--border)',
        padding: bigScreenMode ? '16px 32px' : '12px 24px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}
    >
      {/* 左侧标题 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <Title
          level={bigScreenMode ? 2 : 4}
          style={{ margin: 0, color: 'var(--text-primary)' }}
        >
          AERO Agent
        </Title>
        <Text style={{ color: 'var(--text-secondary)', fontSize: bigScreenMode ? 16 : 14 }}>
          应急响应指挥系统
        </Text>
        {fsmState !== 'INIT' && (
          <Tag color="blue" style={{ marginLeft: 8 }}>
            FSM: {fsmState}
          </Tag>
        )}
      </div>

      {/* 右侧控制区 */}
      <Space size={bigScreenMode ? 24 : 16}>
        {/* 演示/在线模式切换 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <DatabaseOutlined
            style={{
              color: demoMode ? 'var(--accent-green)' : 'var(--text-secondary)',
            }}
          />
          <Switch
            checked={!demoMode}
            onChange={() => toggleDemoMode()}
            size={bigScreenMode ? 'default' : 'small'}
          />
          <CloudOutlined
            style={{
              color: !demoMode ? 'var(--accent-blue)' : 'var(--text-secondary)',
            }}
          />
          <Text
            style={{
              color: 'var(--text-secondary)',
              fontSize: bigScreenMode ? 14 : 12,
              marginLeft: 4,
            }}
          >
            {demoMode ? '演示模式' : '在线模式'}
          </Text>
        </div>

        {/* 大屏模式切换 */}
        <Button
          type={bigScreenMode ? 'primary' : 'default'}
          icon={bigScreenMode ? <CompressOutlined /> : <ExpandOutlined />}
          onClick={toggleBigScreenMode}
          style={{
            background: bigScreenMode ? 'var(--accent-green)' : 'transparent',
            borderColor: 'var(--border)',
            color: bigScreenMode ? '#fff' : 'var(--text-primary)',
          }}
        >
          {bigScreenMode ? '退出大屏' : '大屏模式'}
        </Button>

        {/* 导出报告 */}
        <Dropdown menu={{ items: exportMenuItems }} placement="bottomRight">
          <Button
            icon={<ExportOutlined />}
            style={{
              borderColor: 'var(--border)',
              color: 'var(--text-primary)',
              background: 'transparent',
            }}
          >
            导出报告
          </Button>
        </Dropdown>
      </Space>
    </header>
  );
}
