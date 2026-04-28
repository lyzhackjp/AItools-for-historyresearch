import { useState, type ReactNode } from 'react';
import { Badge, Button, Layout, Menu, Space, theme, Typography } from 'antd';
import {
  ApiOutlined,
  AppstoreOutlined,
  BranchesOutlined,
  DashboardOutlined,
  HomeOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  RobotOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { useLocation, useNavigate } from 'react-router-dom';
import TaskCenterPanel from '../common/TaskCenterPanel';
import { useTaskStore } from '../../stores';
import { useI18n } from '../../i18n';

const { Header, Sider, Content } = Layout;

interface MainLayoutProps {
  children: ReactNode;
}

function MainLayout({ children }: MainLayoutProps) {
  const [collapsed, setCollapsed] = useStateFromStorage('historyresearch-sidebar-collapsed', false);
  const navigate = useNavigate();
  const location = useLocation();
  const { token } = theme.useToken();
  const { t } = useI18n();
  const tasks = useTaskStore((state) => state.tasks);
  const setTaskCenterOpen = useTaskStore((state) => state.setTaskCenterOpen);
  const runningCount = tasks.filter((task) => ['queued', 'running', 'waiting_review'].includes(task.state)).length;
  const menuItems = [
    { key: '/home', icon: <HomeOutlined />, label: t('home') },
    { key: '/manual', icon: <AppstoreOutlined />, label: t('manual') },
    { key: '/agent-solo', icon: <RobotOutlined />, label: t('agentSolo') },
    { key: '/workflow', icon: <BranchesOutlined />, label: t('workflow') },
    { key: '/tasks', icon: <DashboardOutlined />, label: t('taskCenter') },
    { key: '/settings', icon: <SettingOutlined />, label: t('settings') },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        trigger={null}
        width={232}
        style={{
          background: token.colorBgContainer,
          borderRight: `1px solid ${token.colorBorderSecondary}`,
          height: '100vh',
          left: 0,
          position: 'fixed',
          top: 0,
        }}
      >
        <div
          style={{
            alignItems: 'center',
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
            display: 'flex',
            height: 64,
            justifyContent: 'center',
            padding: 12,
          }}
        >
          <Space>
            <ApiOutlined style={{ color: token.colorPrimary, fontSize: 20 }} />
            {!collapsed && <Typography.Text strong>{t('appName')}</Typography.Text>}
          </Space>
        </div>
        <Menu
          items={menuItems}
          mode="inline"
          onClick={({ key }) => navigate(key)}
          selectedKeys={[location.pathname]}
          style={{ borderInlineEnd: 0, paddingTop: 8 }}
        />
      </Sider>
      <Layout style={{ marginLeft: collapsed ? 80 : 232, transition: 'margin-left 0.2s ease' }}>
        <Header
          style={{
            alignItems: 'center',
            background: token.colorBgContainer,
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
            display: 'flex',
            justifyContent: 'space-between',
            padding: '0 20px',
            position: 'sticky',
            top: 0,
            zIndex: 10,
          }}
        >
          <Space>
            <Button
              aria-label="Toggle sidebar"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed(!collapsed)}
              type="text"
            />
            <Typography.Text className="muted">{t('appTagline')}</Typography.Text>
          </Space>
          <Space>
            <Badge count={runningCount} size="small">
              <Button icon={<DashboardOutlined />} onClick={() => setTaskCenterOpen(true)}>
                {t('taskCenter')}
              </Button>
            </Badge>
          </Space>
        </Header>
        <Content style={{ minHeight: 'calc(100vh - 64px)', padding: 20 }}>{children}</Content>
      </Layout>
      <TaskCenterPanel />
    </Layout>
  );
}

function useStateFromStorage(key: string, initialValue: boolean): [boolean, (next: boolean) => void] {
  const stored = localStorage.getItem(key);
  const parsed = stored === null ? initialValue : stored === 'true';
  const [value, setValue] = useState(parsed);

  const updateValue = (next: boolean) => {
    localStorage.setItem(key, String(next));
    setValue(next);
  };

  return [value, updateValue];
}

export default MainLayout;
