import React from 'react';
import { Card, Row, Col, Statistic, Typography, Space, Button } from 'antd';
import {
  FileTextOutlined,
  ScanOutlined,
  BulbOutlined,
  FormOutlined,
  MessageOutlined,
  RocketOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

const { Title, Paragraph } = Typography;

const HomePage: React.FC = () => {
  const navigate = useNavigate();

  const features = [
    {
      key: 'paper-polish',
      title: '论文润色',
      icon: <FileTextOutlined style={{ fontSize: 32, color: '#1890ff' }} />,
      description: '智能润色学术论文，提升表达规范性',
      path: '/paper-polish',
    },
    {
      key: 'ocr-process',
      title: 'OCR识别',
      icon: <ScanOutlined style={{ fontSize: 32, color: '#52c41a' }} />,
      description: '支持多种OCR引擎，识别日文史料',
      path: '/ocr-process',
    },
    {
      key: 'entity-recognition',
      title: '实体识别',
      icon: <BulbOutlined style={{ fontSize: 32, color: '#faad14' }} />,
      description: '自动识别人名、地名、事件等历史实体',
      path: '/entity-recognition',
    },
    {
      key: 'note-generator',
      title: '笔记生成',
      icon: <FormOutlined style={{ fontSize: 32, color: '#722ed1' }} />,
      description: '生成Obsidian格式的学术笔记',
      path: '/note-generator',
    },
    {
      key: 'research-assistant',
      title: '研究助手',
      icon: <MessageOutlined style={{ fontSize: 32, color: '#eb2f96' }} />,
      description: 'AI辅助研究，智能问答与文献分析',
      path: '/research-assistant',
    },
  ];

  return (
    <div className="fade-in">
      <Card style={{ marginBottom: 24 }}>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <div>
            <Title level={2}>
              <RocketOutlined /> 欢迎使用历史研究AI工具
            </Title>
            <Paragraph style={{ fontSize: 16, color: '#666' }}>
              专为日本史研究人员打造的AI工具箱，帮助您处理日文史料、润色学术论文、管理研究文献。
            </Paragraph>
          </div>

          <Row gutter={16}>
            <Col span={6}>
              <Statistic title="支持功能" value={11} suffix="个" />
            </Col>
            <Col span={6}>
              <Statistic title="OCR引擎" value={4} suffix="种" />
            </Col>
            <Col span={6}>
              <Statistic title="LLM服务商" value={5} suffix="个" />
            </Col>
            <Col span={6}>
              <Statistic title="导出格式" value={6} suffix="种" />
            </Col>
          </Row>
        </Space>
      </Card>

      <Title level={3}>核心功能</Title>
      <Row gutter={[16, 16]}>
        {features.map((feature) => (
          <Col span={8} key={feature.key}>
            <Card
              hoverable
              className="result-card"
              onClick={() => navigate(feature.path)}
            >
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                {feature.icon}
                <Title level={4} style={{ margin: 0 }}>
                  {feature.title}
                </Title>
                <Paragraph style={{ margin: 0, color: '#666' }}>
                  {feature.description}
                </Paragraph>
                <Button type="link" style={{ padding: 0 }}>
                  立即使用 →
                </Button>
              </Space>
            </Card>
          </Col>
        ))}
      </Row>

      <Card style={{ marginTop: 24 }}>
        <Title level={4}>快速开始</Title>
        <Paragraph>
          1. 前往「系统设置」配置API密钥（至少配置一个服务商）
        </Paragraph>
        <Paragraph>
          2. 选择需要使用的功能模块
        </Paragraph>
        <Paragraph>
          3. 上传文件或输入文本，开始处理
        </Paragraph>
        <Button type="primary" size="large" onClick={() => navigate('/settings')}>
          开始配置
        </Button>
      </Card>
    </div>
  );
};

export default HomePage;
