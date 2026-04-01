import React from 'react';
import { Card, Typography, Tag, Button, Space, Divider } from 'antd';
import { DownloadOutlined, EyeOutlined, ReloadOutlined } from '@ant-design/icons';
import { ResultViewerProps } from '../../types';

const { Title, Paragraph, Text } = Typography;

const ResultViewer: React.FC<ResultViewerProps> = ({
  result,
  type,
  onExport,
  onDownload,
}) => {
  const renderPolishResult = () => (
    <div>
      <Title level={5}>润色统计</Title>
      <Space size="large" style={{ marginBottom: 16 }}>
        <Text>总修改数: {result.statistics?.totalChanges || 0}</Text>
        <Text>语法修正: {result.statistics?.grammarFixes || 0}</Text>
        <Text>风格改进: {result.statistics?.styleImprovements || 0}</Text>
        <Text>清晰度提升: {result.statistics?.clarityEnhancements || 0}</Text>
      </Space>

      <Divider />

      <Title level={5}>修改详情</Title>
      {result.changes?.map((change: any, index: number) => (
        <Card key={index} size="small" style={{ marginBottom: 8 }}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <div>
              <Tag color="blue">{change.type}</Tag>
              <Text type="secondary"> {change.explanation}</Text>
            </div>
            <div>
              <Text delete type="danger">
                {change.original}
              </Text>
              <br />
              <Text mark type="success">
                {change.suggested}
              </Text>
            </div>
          </Space>
        </Card>
      ))}
    </div>
  );

  const renderOCRResult = () => (
    <div>
      <Title level={5}>识别统计</Title>
      <Space size="large" style={{ marginBottom: 16 }}>
        <Text>总页数: {result.metadata?.totalPages || 0}</Text>
        <Text>总字符数: {result.metadata?.totalCharacters || 0}</Text>
        <Text>平均置信度: {((result.metadata?.averageConfidence || 0) * 100).toFixed(1)}%</Text>
        <Text>处理时间: {result.metadata?.processingTime || 0}ms</Text>
      </Space>

      <Divider />

      <Title level={5}>识别结果</Title>
      {result.pages?.map((page: any, index: number) => (
        <Card key={index} size="small" style={{ marginBottom: 8 }}>
          <div style={{ marginBottom: 8 }}>
            <Tag>第 {page.pageNumber} 页</Tag>
            <Text type="secondary"> 置信度: {(page.confidence * 100).toFixed(1)}%</Text>
          </div>
          <Paragraph
            ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}
            style={{ marginBottom: 0 }}
          >
            {page.text}
          </Paragraph>
        </Card>
      ))}
    </div>
  );

  const renderNERResult = () => (
    <div>
      <Title level={5}>实体统计</Title>
      <Space size="large" style={{ marginBottom: 16 }}>
        <Text>总实体数: {result.statistics?.totalEntities || 0}</Text>
        <Text>平均置信度: {((result.statistics?.averageConfidence || 0) * 100).toFixed(1)}%</Text>
      </Space>

      <Divider />

      <Title level={5}>识别实体</Title>
      {result.entities?.map((entity: any, index: number) => (
        <Card key={index} size="small" style={{ marginBottom: 8 }}>
          <Space>
            <Tag color="blue">{entity.type}</Tag>
            <Text strong>{entity.text}</Text>
            <Text type="secondary">置信度: {(entity.confidence * 100).toFixed(1)}%</Text>
          </Space>
          <Paragraph
            ellipsis={{ rows: 2 }}
            style={{ marginTop: 8, marginBottom: 0, color: '#666' }}
          >
            上下文: {entity.context}
          </Paragraph>
        </Card>
      ))}
    </div>
  );

  const renderNoteResult = () => (
    <div>
      <Title level={5}>{result.title}</Title>
      <Space style={{ marginBottom: 16 }}>
        {result.tags?.map((tag: string, index: number) => (
          <Tag key={index}>{tag}</Tag>
        ))}
      </Space>
      <Divider />
      <div style={{ whiteSpace: 'pre-wrap' }}>{result.content}</div>
    </div>
  );

  return (
    <Card className="result-card fade-in">
      {type === 'polish' && renderPolishResult()}
      {type === 'ocr' && renderOCRResult()}
      {type === 'ner' && renderNERResult()}
      {type === 'note' && renderNoteResult()}

      <Divider />

      <Space>
        {onDownload && (
          <Button type="primary" icon={<DownloadOutlined />} onClick={onDownload}>
            下载结果
          </Button>
        )}
        {onExport && (
          <Button icon={<EyeOutlined />} onClick={() => onExport('preview')}>
            预览
          </Button>
        )}
        <Button icon={<ReloadOutlined />}>重新处理</Button>
      </Space>
    </Card>
  );
};

export default ResultViewer;
