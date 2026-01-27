import { Button, ConfigProvider, theme, Typography } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { Header, SummaryCard, Footer } from './components/layout';
import { ChatTimeline, ReasoningTrace, InputArea } from './components/chat';
import { TopologyMap, FlightGantt, FSMFlow, WeatherCard } from './components/visualization';
import { RiskPanel, CrossValidation, ImpactStats } from './components/assessment';
import { ActionChecklist } from './components/action';
import { useSession } from './hooks/useSession';
import { useUIStore } from './stores/uiStore';
import { useSessionStore } from './stores/sessionStore';
import './index.css';

const { Title } = Typography;

// 左侧面板（对话交互区）
function LeftPanel() {
  const { bigScreenMode } = useUIStore();
  const { resetSession, isLoading, isThinking } = useSessionStore();
  const { cancelRequest } = useSession();

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: bigScreenMode ? 12 : 8,
        height: '100%',
        minHeight: 0,
      }}
    >
      {/* 对话区域 */}
      <div
        className="card"
        style={{
          flex: 2,
          display: 'flex',
          flexDirection: 'column',
          padding: 0,
          overflow: 'hidden',
          minHeight: 0,
        }}
      >
        <div
          style={{
            padding: bigScreenMode ? '12px 16px' : '10px 12px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
          }}
        >
          <Title
            level={5}
            style={{ margin: 0, color: 'var(--text-primary)', fontSize: bigScreenMode ? 16 : 14 }}
          >
            对话交互区
          </Title>
          <div style={{ display: 'flex', gap: 6 }}>
            <Button
              size="small"
              disabled={isLoading || isThinking}
              onClick={resetSession}
            >
              清除对话
            </Button>
            <Button
              size="small"
              danger
              onClick={() => {
                cancelRequest();
                resetSession();
              }}
            >
              强制清理+取消
            </Button>
          </div>
        </div>
        <ChatTimeline />
        <ReasoningTrace />
        <InputArea />
      </div>

      {/* 天气信息 */}
      <div className="card" style={{ flex: 1, minHeight: 100, overflow: 'hidden' }}>
        <Title
          level={5}
          style={{
            margin: 0,
            marginBottom: bigScreenMode ? 8 : 6,
            color: 'var(--text-primary)',
            fontSize: bigScreenMode ? 16 : 14,
          }}
        >
          天气信息
        </Title>
        <div style={{ height: 'calc(100% - 28px)', overflow: 'auto' }}>
          <WeatherCard />
        </div>
      </div>
    </div>
  );
}

// 中部面板（可视化区域）
function CenterPanel() {
  const { bigScreenMode } = useUIStore();

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: bigScreenMode ? 12 : 8,
        height: '100%',
        minHeight: 0,
      }}
    >
      {/* 拓扑图 */}
      <div className="card" style={{ flex: 3, minHeight: 0 }}>
        <Title
          level={5}
          style={{
            margin: 0,
            marginBottom: bigScreenMode ? 12 : 8,
            color: 'var(--text-primary)',
            fontSize: bigScreenMode ? 16 : 14,
          }}
        >
          机场拓扑图
        </Title>
        <div style={{ height: 'calc(100% - 32px)' }}>
          <TopologyMap />
        </div>
      </div>

      {/* 航班甘特图 */}
      <div className="card" style={{ flex: 1, minHeight: 150, overflow: 'hidden' }}>
        <Title
          level={5}
          style={{
            margin: 0,
            marginBottom: bigScreenMode ? 12 : 8,
            color: 'var(--text-primary)',
            fontSize: bigScreenMode ? 16 : 14,
          }}
        >
          航班影响分析
        </Title>
        <div style={{ height: 'calc(100% - 32px)', overflow: 'auto' }}>
          <FlightGantt />
        </div>
      </div>
    </div>
  );
}

// 右侧面板
function RightPanel() {
  const { bigScreenMode } = useUIStore();

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: bigScreenMode ? 12 : 8,
        height: '100%',
        minHeight: 0,
      }}
    >
      {/* FSM 状态 */}
      <div className="card" style={{ minHeight: bigScreenMode ? 100 : 80, overflow: 'hidden' }}>
        <Title
          level={5}
          style={{
            margin: 0,
            marginBottom: bigScreenMode ? 8 : 6,
            color: 'var(--text-primary)',
            fontSize: bigScreenMode ? 16 : 14,
          }}
        >
          FSM 状态
        </Title>
        <div style={{ height: 'calc(100% - 28px)', overflow: 'auto' }}>
          <FSMFlow />
        </div>
      </div>

      {/* 处置清单 */}
      <div className="card" style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
        <Title
          level={5}
          style={{
            margin: 0,
            marginBottom: bigScreenMode ? 12 : 8,
            color: 'var(--text-primary)',
            fontSize: bigScreenMode ? 16 : 14,
          }}
        >
          处置清单
        </Title>
        <div style={{ height: 'calc(100% - 32px)', overflow: 'auto' }}>
          <ActionChecklist />
        </div>
      </div>

      {/* 风险评估 + 双引擎对比 */}
      <div className="card" style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
        <Title
          level={5}
          style={{
            margin: 0,
            marginBottom: bigScreenMode ? 12 : 8,
            color: 'var(--text-primary)',
            fontSize: bigScreenMode ? 16 : 14,
          }}
        >
          风险评估
        </Title>
        <div style={{ height: 'calc(100% - 32px)', overflow: 'auto' }}>
          <RiskPanel />
        </div>
      </div>

      {/* 交叉验证 */}
      <div className="card" style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
        <Title
          level={5}
          style={{
            margin: 0,
            marginBottom: bigScreenMode ? 12 : 8,
            color: 'var(--text-primary)',
            fontSize: bigScreenMode ? 16 : 14,
          }}
        >
          双引擎验证
        </Title>
        <div style={{ height: 'calc(100% - 32px)', overflow: 'auto' }}>
          <CrossValidation />
        </div>
      </div>

      {/* 影响统计 */}
      <div className="card" style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
        <Title
          level={5}
          style={{
            margin: 0,
            marginBottom: bigScreenMode ? 12 : 8,
            color: 'var(--text-primary)',
            fontSize: bigScreenMode ? 16 : 14,
          }}
        >
          影响统计
        </Title>
        <div style={{ height: 'calc(100% - 32px)', overflow: 'auto' }}>
          <ImpactStats />
        </div>
      </div>
    </div>
  );
}

function App() {
  const { bigScreenMode } = useUIStore();

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: '#238636',
          colorBgContainer: '#161b22',
          colorBgElevated: '#161b22',
          colorBorder: '#30363d',
          colorText: '#e6edf3',
          colorTextSecondary: '#8b949e',
          borderRadius: 6,
          fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
        },
      }}
    >
      <div
        className={bigScreenMode ? 'big-screen' : ''}
        style={{
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          background: 'var(--bg-primary)',
        }}
      >
        {/* 顶部 */}
        <Header />

        {/* 主内容区 */}
        <main
          style={{
            flex: 1,
            padding: bigScreenMode ? '24px 32px' : '16px 24px',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            minHeight: 0,
          }}
        >
          {/* 事件摘要 */}
          <SummaryCard />

          {/* 三栏布局 */}
          <div
            style={{
              flex: 1,
              display: 'flex',
              gap: bigScreenMode ? 24 : 16,
              minHeight: 0,
              overflow: 'hidden',
            }}
          >
            {/* 左侧 25% */}
            <div style={{ width: '25%', minWidth: 300, minHeight: 0, overflow: 'hidden' }}>
              <LeftPanel />
            </div>

            {/* 中部 50% */}
            <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
              <CenterPanel />
            </div>

            {/* 右侧 25% */}
            <div style={{ width: '25%', minWidth: 280, minHeight: 0, overflow: 'hidden' }}>
              <RightPanel />
            </div>
          </div>
        </main>

        {/* 底部 */}
        <Footer />
      </div>
    </ConfigProvider>
  );
}

export default App;
