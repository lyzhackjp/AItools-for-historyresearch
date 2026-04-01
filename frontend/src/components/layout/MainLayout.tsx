import React from 'react';
import { Layout, Menu, theme, Button, Dropdown, Avatar, Space } from 'antd';
import {
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  HomeOutlined,
  FileTextOutlined,
  ScanOutlined,
  BulbOutlined,
  FormOutlined,
  MessageOutlined,
  SettingOutlined,
  CodeOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { useUserStore } from '../../stores';

const { Header, Sider, Content } = Layout;

interface MainLayoutProps {
  children: React.ReactNode;
}

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const [collapsed, setCollapsed] = React.useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { preferences } = useUserStore();
  const { token } = theme.useToken();

  const menuItems = [
    {
      key: '/home',
      icon: <HomeOutlined />,
      label: '工作台',
    },
    {
      key: '/paper-polish',
      icon: <FileTextOutlined />,
      label: '论文润色',
    },
    {
      key: '/ocr-process',
      icon: <ScanOutlined />,
      label: 'OCR识别',
    },
    {
      key: '/entity-recognition',
      icon: <BulbOutlined />,
      label: '实体识别',
    },
    {
      key: '/note-generator',
      icon: <FormOutlined />,
      label: '笔记生成',
    },
    {
      key: '/research-assistant',
      icon: <MessageOutlined />,
      label: '研究助手',
    },
    {
      key: '/prompt-editor',
      icon: <CodeOutlined />,
      label: '提示词编辑',
    },
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: '系统设置',
    },
  ];

  const userMenuItems = [
    {
      key: 'settings',
      label: '系统设置',
      icon: <SettingOutlined />,
    },
    {
      key: 'help',
      label: '帮助文档',
    },
    {
      type: 'divider' as const,
    },
    {
      key: 'about',
      label: '关于',
    },
  ];

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key);
  };

  const handleUserMenuClick = ({ key }: { key: string }) => {
    if (key === 'settings') {
      navigate('/settings');
    }
  };

  const fontSizeClass =
    preferences.fontSize === 'large'
      ? 'text-lg'
      : preferences.fontSize === 'extra-large'
      ? 'text-xl'
      : '';

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        style={{
          overflow: 'auto',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          background: token.colorBgContainer,
        }}
      >
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderBottom: `1px solid ${token.colorBorder}`,
          }}
        >
          <h1
            style={{
              margin: 0,
              fontSize: collapsed ? 16 : 18,
              fontWeight: 'bold',
              color: token.colorPrimary,
            }}
          >
            {collapsed ? 'AI' : '历史研究AI工具'}
          </h1>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={handleMenuClick}
          style={{ borderRight: 0 }}
        />
      </Sider>
      <Layout style={{ marginLeft: collapsed ? 80 : 200, transition: 'all 0.2s' }}>
        <Header
          style={{
            padding: '0 24px',
            background: token.colorBgContainer,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: `1px solid ${token.colorBorder}`,
            position: 'sticky',
            top: 0,
            zIndex: 1,
          }}
        >
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
            style={{
              fontSize: 16,
              width: 64,
              height: 64,
            }}
          />
          <Dropdown
            menu={{ items: userMenuItems, onClick: handleUserMenuClick }}
            placement="bottomRight"
          >
            <Space style={{ cursor: 'pointer' }}>
              <Avatar icon={<UserOutlined />} />
              <span>用户</span>
            </Space>
          </Dropdown>
        </Header>
        <Content
          className={fontSizeClass}
          style={{
            background: token.colorBgLayout,
            minHeight: 'calc(100vh - 64px)',
          }}
        >
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;
