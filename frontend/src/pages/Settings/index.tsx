import React from 'react';
import { Card, Row, Col, Typography, Divider } from 'antd';
import { SettingOutlined } from '@ant-design/icons';
import { ApiKeyManager } from '../../components/business';
import { useUserStore } from '../../stores';

const { Title, Paragraph } = Typography;

const SettingsPage: React.FC = () => {
  const { preferences } = useUserStore();

  return (
    <div className="fade-in">
      <Title level={2}>
        <SettingOutlined /> 系统设置
      </Title>
      <Paragraph type="secondary">
        配置API密钥、用户偏好和系统参数
      </Paragraph>

      <Row gutter={24}>
        <Col span={16}>
          <ApiKeyManager />
        </Col>

        <Col span={8}>
          <Card title="用户偏好">
            <Paragraph>
              <strong>字体大小：</strong>
              {preferences.fontSize === 'normal'
                ? '标准'
                : preferences.fontSize === 'large'
                ? '大'
                : '超大'}
            </Paragraph>
            <Paragraph>
              <strong>高对比度：</strong>
              {preferences.highContrast ? '已启用' : '未启用'}
            </Paragraph>
            <Paragraph>
              <strong>语言：</strong>
              {preferences.language === 'zh-CN'
                ? '简体中文'
                : preferences.language === 'en-US'
                ? 'English'
                : '日本語'}
            </Paragraph>
          </Card>

          <Divider />

          <Card title="关于">
            <Paragraph>
              <strong>版本：</strong> 1.0.0
            </Paragraph>
            <Paragraph>
              <strong>更新日期：</strong> 2026-04-01
            </Paragraph>
            <Paragraph type="secondary">
              历史研究AI工具 - 专为日本史研究人员打造的AI工具箱
            </Paragraph>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default SettingsPage;
