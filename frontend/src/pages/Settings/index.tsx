import { Card, Col, Form, Row, Select, Space, Switch, Typography } from 'antd';
import { ApiKeyManager, PromptEditor } from '../../components/business';
import { baseURL } from '../../api';
import { useI18n } from '../../i18n';
import { useUserStore } from '../../stores';
import type { UserPreferences } from '../../types';

function SettingsPage() {
  const { t } = useI18n();
  const preferences = useUserStore((state) => state.preferences);
  const updatePreferences = useUserStore((state) => state.updatePreferences);

  return (
    <div className="page-shell">
      <div className="page-heading">
        <div>
          <div className="page-kicker">{t('settings')}</div>
          <Typography.Title level={2} style={{ margin: 0 }}>
            {t('settingsTitle')}
          </Typography.Title>
          <Typography.Paragraph className="muted" style={{ marginTop: 8 }}>
            {t('settingsIntro')}
          </Typography.Paragraph>
        </div>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={10}>
          <Card title={t('frontendPrefs')}>
            <Form layout="vertical">
              <Form.Item label={t('apiAddress')}>
                <Typography.Text code>{baseURL}</Typography.Text>
              </Form.Item>
              <Form.Item label={t('language')}>
                <Select
                  onChange={(language: UserPreferences['language']) => updatePreferences({ language })}
                  value={preferences.language}
                  options={[
                    { label: '中文', value: 'zh-CN' },
                    { label: 'English', value: 'en-US' },
                    { label: '日本語', value: 'ja-JP' },
                  ]}
                />
              </Form.Item>
              <Form.Item label={t('fontSize')}>
                <Select
                  onChange={(fontSize: UserPreferences['fontSize']) => updatePreferences({ fontSize })}
                  value={preferences.fontSize}
                  options={[
                    { label: preferences.language === 'en-US' ? 'Normal' : preferences.language === 'ja-JP' ? '標準' : '正常', value: 'normal' },
                    { label: preferences.language === 'en-US' ? 'Large' : preferences.language === 'ja-JP' ? '大きめ' : '较大', value: 'large' },
                    { label: preferences.language === 'en-US' ? 'Extra large' : preferences.language === 'ja-JP' ? '特大' : '特大', value: 'extra-large' },
                  ]}
                />
              </Form.Item>
              <Form.Item label={t('compactDensity')}>
                <Switch
                  checked={preferences.compactDensity}
                  onChange={(compactDensity) => updatePreferences({ compactDensity })}
                />
              </Form.Item>
              <Form.Item label={t('highContrast')}>
                <Switch
                  checked={preferences.highContrast}
                  onChange={(highContrast) => updatePreferences({ highContrast })}
                />
              </Form.Item>
            </Form>
          </Card>
        </Col>
        <Col xs={24} lg={14}>
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <ApiKeyManager />
            <PromptEditor />
          </Space>
        </Col>
      </Row>
    </div>
  );
}

export default SettingsPage;
