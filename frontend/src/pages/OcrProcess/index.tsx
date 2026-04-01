import React, { useState } from 'react';
import {
  Card,
  Row,
  Col,
  Radio,
  Space,
  Button,
  message,
  Typography,
  Divider,
  Switch,
} from 'antd';
import { ScanOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { FileUploader, StepIndicator, ResultViewer } from '../../components/common';
import { ocrApi } from '../../api';
import { OCRResult } from '../../types';

const { Title, Paragraph } = Typography;

const OcrProcessPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [engine, setEngine] = useState<string>('ndlocr-lite');
  const [removeWatermark, setRemoveWatermark] = useState(true);
  const [result, setResult] = useState<OCRResult | null>(null);
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

  const handleOCR = async () => {
    if (!file) {
      message.warning('请先上传文件');
      return;
    }

    setLoading(true);
    setCurrentStep(2);

    try {
      const ocrResult = await ocrApi.extractText(file, engine, {
        removeWatermark,
      });
      setResult(ocrResult);
      setCurrentStep(3);
      message.success('OCR识别完成');
    } catch (error) {
      message.error('OCR识别失败，请重试');
      setCurrentStep(1);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async () => {
    if (!result) return;
    message.success('结果下载中...');
  };

  const handleReset = () => {
    setFile(null);
    setResult(null);
    setCurrentStep(0);
  };

  const engineOptions = [
    {
      value: 'ndlocr-lite',
      label: 'NDL OCR-Lite ⭐推荐',
      desc: '近代现代文献',
    },
    {
      value: 'ndlkotenocr-lite',
      label: 'NDL古典籍OCR-Lite',
      desc: '古典籍文献',
    },
    {
      value: 'tesseract',
      label: 'Tesseract OCR',
      desc: '本地运行',
    },
    {
      value: 'qwen-vl-ocr',
      label: '通义千问VL OCR',
      desc: '高精度识别',
    },
  ];

  return (
    <div className="fade-in">
      <Title level={2}>
        <ScanOutlined /> PDF文献OCR识别
      </Title>
      <Paragraph type="secondary">
        将扫描版日文PDF转换为可编辑文本，支持多种OCR引擎
      </Paragraph>

      <StepIndicator
        current={currentStep}
        total={3}
        labels={['上传文件', '选择引擎', '查看结果']}
      />

      <Row gutter={24}>
        <Col span={12}>
          <Card>
            <Title level={4}>1. 上传文件</Title>
            <FileUploader
              accept={['.pdf', '.png', '.jpg', '.jpeg']}
              maxSize={50}
              onUpload={handleUpload}
              onError={handleError}
            />
            {file && (
              <Paragraph style={{ marginTop: 16, color: '#52c41a' }}>
                <CheckCircleOutlined /> 已选择文件: {file.name}
              </Paragraph>
            )}

            <Divider />

            <Title level={4}>2. 选择OCR引擎</Title>
            <Radio.Group
              value={engine}
              onChange={(e) => setEngine(e.target.value)}
              style={{ width: '100%' }}
            >
              <Space direction="vertical" style={{ width: '100%' }}>
                {engineOptions.map((option) => (
                  <Radio key={option.value} value={option.value}>
                    <div>
                      <strong>{option.label}</strong>
                      <br />
                      <span style={{ color: '#999' }}>{option.desc}</span>
                    </div>
                  </Radio>
                ))}
              </Space>
            </Radio.Group>

            <Divider />

            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <span>去除水印：</span>
                <Switch
                  checked={removeWatermark}
                  onChange={setRemoveWatermark}
                />
              </div>

              <Button
                type="primary"
                size="large"
                loading={loading}
                onClick={handleOCR}
                block
              >
                开始识别
              </Button>
            </Space>
          </Card>
        </Col>

        <Col span={12}>
          {result ? (
            <Card>
              <Title level={4}>3. 识别结果</Title>
              <ResultViewer
                result={result}
                type="ocr"
                onDownload={handleDownload}
              />
              <Divider />
              <Button onClick={handleReset}>处理新文件</Button>
            </Card>
          ) : (
            <Card>
              <Paragraph type="secondary" style={{ textAlign: 'center' }}>
                上传文件并选择OCR引擎后，识别结果将在此显示
              </Paragraph>
            </Card>
          )}
        </Col>
      </Row>
    </div>
  );
};

export default OcrProcessPage;
