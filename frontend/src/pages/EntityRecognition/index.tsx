import React, { useState } from 'react';
import {
  Card,
  Row,
  Col,
  Input,
  Button,
  Checkbox,
  Space,
  message,
  Typography,
  Divider,
  Tag,
} from 'antd';
import { BulbOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { FileUploader, ResultViewer } from '../../components/common';
import { nerApi } from '../../api';
import { NERResult, Entity } from '../../types';

const { Title, Paragraph } = Typography;
const { TextArea } = Input;

const EntityRecognitionPage: React.FC = () => {
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [entityTypes, setEntityTypes] = useState<string[]>([
    'person',
    'location',
    'event',
    'organization',
    'concept',
  ]);
  const [result, setResult] = useState<NERResult | null>(null);
  const [loading, setLoading] = useState(false);

  const entityTypeOptions = [
    { label: '人名', value: 'person' },
    { label: '地名', value: 'location' },
    { label: '事件', value: 'event' },
    { label: '机构', value: 'organization' },
    { label: '概念', value: 'concept' },
  ];

  const handleUpload = (files: File[]) => {
    setFile(files[0]);
    setText('');
  };

  const handleError = (error: string) => {
    message.error(error);
  };

  const handleExtract = async () => {
    if (!text && !file) {
      message.warning('请输入文本或上传文件');
      return;
    }

    setLoading(true);

    try {
      let nerResult: NERResult;
      if (file) {
        nerResult = await nerApi.extractFromFile(file, entityTypes);
      } else {
        nerResult = await nerApi.extractEntities(text, entityTypes, 'ja');
      }
      setResult(nerResult);
      message.success('实体识别完成');
    } catch (error) {
      message.error('实体识别失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async () => {
    if (!result) return;
    message.success('结果下载中...');
  };

  return (
    <div className="fade-in">
      <Title level={2}>
        <BulbOutlined /> 历史实体识别
      </Title>
      <Paragraph type="secondary">
        自动识别人名、地名、事件、机构等历史专有名词
      </Paragraph>

      <Row gutter={24}>
        <Col span={12}>
          <Card>
            <Title level={4}>输入文本</Title>
            <TextArea
              value={text}
              onChange={(e) => {
                setText(e.target.value);
                setFile(null);
              }}
              placeholder="请输入需要识别的历史文本..."
              rows={8}
              style={{ marginBottom: 16 }}
            />

            <Divider>或上传文件</Divider>

            <FileUploader
              accept={['.txt', '.pdf', '.docx']}
              maxSize={10}
              onUpload={handleUpload}
              onError={handleError}
            />
            {file && (
              <Paragraph style={{ marginTop: 16, color: '#52c41a' }}>
                <CheckCircleOutlined /> 已选择文件: {file.name}
              </Paragraph>
            )}

            <Divider />

            <Title level={4}>实体类型</Title>
            <Checkbox.Group
              options={entityTypeOptions}
              value={entityTypes}
              onChange={(values) => setEntityTypes(values as string[])}
              style={{ marginBottom: 16 }}
            />

            <Button
              type="primary"
              size="large"
              loading={loading}
              onClick={handleExtract}
              block
            >
              开始识别
            </Button>
          </Card>
        </Col>

        <Col span={12}>
          {result ? (
            <Card>
              <Title level={4}>识别结果</Title>
              <ResultViewer
                result={result}
                type="ner"
                onDownload={handleDownload}
              />
            </Card>
          ) : (
            <Card>
              <Paragraph type="secondary" style={{ textAlign: 'center' }}>
                输入文本后，识别结果将在此显示
              </Paragraph>
            </Card>
          )}
        </Col>
      </Row>
    </div>
  );
};

export default EntityRecognitionPage;
