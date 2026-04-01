import React, { useState } from 'react';
import {
  Card,
  Button,
  Radio,
  Space,
  message,
  Result,
  Typography,
  Divider,
} from 'antd';
import { FileTextOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { FileUploader, StepIndicator, ResultViewer } from '../../components/common';
import { docApi } from '../../api';
import { PolishResult } from '../../types';

const { Title, Paragraph } = Typography;

const PaperPolishPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [strategy, setStrategy] = useState<'quick' | 'deep' | 'custom'>('quick');
  const [language, setLanguage] = useState<'zh' | 'ja' | 'en'>('ja');
  const [result, setResult] = useState<PolishResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);

  const handleUpload = (files: File[]) => {
    setFile(files[0]);
    setCurrentStep(1);
    setResult(null);
  };

  const handleError = (error: string) => {
    message.error(error);
  };

  const handlePolish = async () => {
    if (!file) {
      message.warning('请先上传文档');
      return;
    }

    setLoading(true);
    setCurrentStep(2);

    try {
      const polishResult = await docApi.polishDocument(file, strategy, language);
      setResult(polishResult);
      setCurrentStep(3);
      message.success('润色完成');
    } catch (error) {
      message.error('润色失败，请重试');
      setCurrentStep(1);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async () => {
    if (!result) return;
    message.success('文档下载中...');
  };

  const handleReset = () => {
    setFile(null);
    setResult(null);
    setCurrentStep(0);
  };

  return (
    <div className="fade-in">
      <Title level={2}>
        <FileTextOutlined /> 学术论文润色
      </Title>
      <Paragraph type="secondary">
        智能润色学术论文，提升表达规范性，保留历史专有名词
      </Paragraph>

      <StepIndicator
        current={currentStep}
        total={3}
        labels={['上传文档', '选择策略', '查看结果']}
      />

      <Card style={{ marginBottom: 24 }}>
        <Title level={4}>1. 上传文档</Title>
        <FileUploader
          accept={['.docx']}
          maxSize={10}
          onUpload={handleUpload}
          onError={handleError}
        />
        {file && (
          <Paragraph style={{ marginTop: 16, color: '#52c41a' }}>
            <CheckCircleOutlined /> 已选择文件: {file.name}
          </Paragraph>
        )}
      </Card>

      {file && (
        <Card style={{ marginBottom: 24 }}>
          <Title level={4}>2. 选择润色策略</Title>
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <div>
              <Paragraph strong>润色策略：</Paragraph>
              <Radio.Group
                value={strategy}
                onChange={(e) => setStrategy(e.target.value)}
                buttonStyle="solid"
              >
                <Radio.Button value="quick">快速润色（推荐新手）</Radio.Button>
                <Radio.Button value="deep">深度润色（保留原文风格）</Radio.Button>
                <Radio.Button value="custom">自定义（高级用户）</Radio.Button>
              </Radio.Group>
            </div>

            <div>
              <Paragraph strong>文档语言：</Paragraph>
              <Radio.Group
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                buttonStyle="solid"
              >
                <Radio.Button value="ja">日文</Radio.Button>
                <Radio.Button value="zh">中文</Radio.Button>
                <Radio.Button value="en">英文</Radio.Button>
              </Radio.Group>
            </div>

            <Button
              type="primary"
              size="large"
              loading={loading}
              onClick={handlePolish}
              style={{ marginTop: 16 }}
            >
              开始润色
            </Button>
          </Space>
        </Card>
      )}

      {result && (
        <Card>
          <Title level={4}>3. 润色结果</Title>
          <ResultViewer
            result={result}
            type="polish"
            onDownload={handleDownload}
          />
          <Divider />
          <Button onClick={handleReset}>处理新文档</Button>
        </Card>
      )}
    </div>
  );
};

export default PaperPolishPage;
