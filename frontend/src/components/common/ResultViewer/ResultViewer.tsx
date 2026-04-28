import { Card, Empty, Space, Tag, Typography } from 'antd';

interface ResultViewerProps {
  title?: string;
  result?: unknown;
  tags?: string[];
}

function ResultViewer({ title = '结果预览', result, tags = [] }: ResultViewerProps) {
  return (
    <Card title={title}>
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        {tags.length > 0 && (
          <Space wrap>
            {tags.map((tag) => (
              <Tag key={tag}>{tag}</Tag>
            ))}
          </Space>
        )}
        {result === undefined ? (
          <Empty description="运行任务后会在这里显示摘要。" />
        ) : (
          <Typography.Paragraph>
            <pre className="task-log">{JSON.stringify(result, null, 2)}</pre>
          </Typography.Paragraph>
        )}
      </Space>
    </Card>
  );
}

export default ResultViewer;
