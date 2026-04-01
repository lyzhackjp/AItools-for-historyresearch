import React, { useState } from 'react';
import {
  Card,
  Row,
  Col,
  Input,
  Button,
  Select,
  Space,
  message,
  Typography,
  Divider,
} from 'antd';
import { FormOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { FileUploader, ResultViewer } from '../../components/common';
import { researchApi } from '../../api';
import { Note } from '../../types';

const { Title, Paragraph } = Typography;
const { TextArea } = Input;
const { Option } = Select;

const NoteGeneratorPage: React.FC = () => {
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [template, setTemplate] = useState('academic');
  const [format, setFormat] = useState<'markdown' | 'obsidian'>('obsidian');
  const [result, setResult] = useState<Note | null>(null);
  const [loading, setLoading] = useState(false);

  const handleUpload = (files: File[]) => {
    setFile(files[0]);
    setText('');
  };

  const handleError = (error: string) => {
    message.error(error);
  };

  const handleGenerate = async () => {
    if (!text && !file) {
      message.warning('请输入文本或上传文件');
      return;
    }

    setLoading(true);

    try {
      const note = await researchApi.generateNote(text, {
        template,
        format,
        extractEntities: true,
      });
      setResult(note);
      message.success('笔记生成完成');
    } catch (error) {
      message.error('笔记生成失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async () => {
    if (!result) return;
    message.success('笔记下载中...');
  };

  return (
    <div className="fade-in">
      <Title level={2}>
        <FormOutlined /> 学术笔记生成
      </Title>
      <Paragraph type="secondary">
        生成符合Obsidian格式的阅读笔记，自动构建知识图谱
      </Paragraph>

      <Row gutter={24}>
        <Col span={12}>
          <Card>
            <Title level={4}>输入文献内容</Title>
            <TextArea
              value={text}
              onChange={(e) => {
                setText(e.target.value);
                setFile(null);
              }}
              placeholder="请输入文献内容..."
              rows={8}
              style={{ marginBottom: 16 }}
            />

            <Divider>或上传文件</Divider>

            <FileUploader
              accept={['.txt', '.pdf']}
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

            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <div>
                <Paragraph strong>笔记模板：</Paragraph>
                <Select
                  value={template}
                  onChange={setTemplate}
                  style={{ width: '100%' }}
                >
                  <Option value="academic">学术笔记模板</Option>
                  <Option value="summary">文献摘要模板</Option>
                  <Option value="reading">阅读笔记模板</Option>
                </Select>
              </div>

              <div>
                <Paragraph strong>输出格式：</Paragraph>
                <Select
                  value={format}
                  onChange={setFormat}
                  style={{ width: '100%' }}
                >
                  <Option value="obsidian">Obsidian格式</Option>
                  <Option value="markdown">Markdown格式</Option>
                </Select>
              </div>

              <Button
                type="primary"
                size="large"
                loading={loading}
                onClick={handleGenerate}
                block
              >
                生成笔记
              </Button>
            </Space>
          </Card>
        </Col>

        <Col span={12}>
          {result ? (
            <Card>
              <Title level={4}>生成结果</Title>
              <ResultViewer
                result={result}
                type="note"
                onDownload={handleDownload}
              />
            </Card>
          ) : (
            <Card>
              <Paragraph type="secondary" style={{ textAlign: 'center' }}>
                输入文献内容后，生成的笔记将在此显示
              </Paragraph>
            </Card>
          )}
        </Col>
      </Row>
    </div>
  );
};

export default NoteGeneratorPage;
