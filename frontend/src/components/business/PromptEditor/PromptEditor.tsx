import { Card, Input, Space, Typography } from 'antd';
import { useI18n } from '../../../i18n';

interface PromptEditorProps {
  value?: string;
  onChange?: (next: string) => void;
}

function PromptEditor({ value, onChange }: PromptEditorProps) {
  const { language, t } = useI18n();

  return (
    <Card title={t('promptDraft')}>
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <Typography.Text className="muted">
          {t('promptDraftHelp')}
        </Typography.Text>
        <Input.TextArea
          autoSize={{ minRows: 8, maxRows: 18 }}
          onChange={(event) => onChange?.(event.target.value)}
          placeholder={
            language === 'en-US'
              ? 'Edit prompt templates here...'
              : language === 'ja-JP'
                ? 'ここでpromptテンプレートを編集...'
                : '在这里编辑 prompt 模板...'
          }
          value={value}
        />
      </Space>
    </Card>
  );
}

export default PromptEditor;
