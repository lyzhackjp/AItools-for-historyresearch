import { Button, Card, Form, Input, List, Space, Tag, Typography } from 'antd';
import { useI18n } from '../../../i18n';
import { useApiStore } from '../../../stores';

function ApiKeyManager() {
  const { language, t } = useI18n();
  const providers = useApiStore((state) => state.providers);
  const markConfigured = useApiStore((state) => state.markConfigured);
  const [form] = Form.useForm<{ provider: string; displayName: string }>();

  return (
    <Card title={t('providerStatus')}>
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <Typography.Paragraph className="muted">
          {t('providerStatusHelp')}
        </Typography.Paragraph>
        <List
          dataSource={providers}
          renderItem={(item) => (
            <List.Item>
              <Space style={{ justifyContent: 'space-between', width: '100%' }}>
                <Typography.Text>{item.displayName}</Typography.Text>
                <Tag color={item.configured ? 'success' : 'default'}>
                  {item.configured ? t('configured') : t('notConfigured')}
                </Tag>
              </Space>
            </List.Item>
          )}
        />
        <Form
          form={form}
          layout="inline"
          onFinish={(values) => {
            markConfigured(values.provider, values.displayName);
            form.resetFields();
          }}
        >
          <Form.Item
            name="provider"
            rules={[
              {
                required: true,
                message: language === 'en-US' ? 'Enter provider id' : language === 'ja-JP' ? 'provider idを入力してください' : '请输入 provider id',
              },
            ]}
          >
            <Input placeholder="provider id" />
          </Form.Item>
          <Form.Item
            name="displayName"
            rules={[
              {
                required: true,
                message: language === 'en-US' ? 'Enter display name' : language === 'ja-JP' ? '表示名を入力してください' : '请输入显示名称',
              },
            ]}
          >
            <Input placeholder={language === 'en-US' ? 'Display name' : language === 'ja-JP' ? '表示名' : '显示名称'} />
          </Form.Item>
          <Button htmlType="submit" type="primary">
            {language === 'en-US' ? 'Mark configured' : language === 'ja-JP' ? '設定済みにする' : '标记为已配置'}
          </Button>
        </Form>
      </Space>
    </Card>
  );
}

export default ApiKeyManager;
