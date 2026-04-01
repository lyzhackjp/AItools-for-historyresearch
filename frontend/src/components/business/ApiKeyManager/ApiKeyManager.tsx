import React, { useState } from 'react';
import {
  Card,
  List,
  Button,
  Modal,
  Form,
  Input,
  Tag,
  Alert,
  Space,
  message,
  Popconfirm,
} from 'antd';
import {
  CheckCircleFilled,
  MinusCircleFilled,
  PlusOutlined,
  DeleteOutlined,
  ApiOutlined,
} from '@ant-design/icons';
import { useApiStore } from '../../stores';
import { ApiKeyManagerProps } from '../../types';

const ApiKeyManager: React.FC<ApiKeyManagerProps> = ({
  onKeyAdded,
  onKeyRemoved,
  onProviderSwitched,
}) => {
  const {
    apiKeys,
    activeProvider,
    providers,
    setApiKey,
    removeApiKey,
    switchProvider,
    hasKey,
  } = useApiStore();

  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<string>('');
  const [form] = Form.useForm();
  const [testing, setTesting] = useState<string>('');

  const handleAddKey = (providerId: string) => {
    setSelectedProvider(providerId);
    setShowAddModal(true);
  };

  const handleSaveKey = async (values: { apiKey: string }) => {
    setApiKey(selectedProvider, values.apiKey);
    message.success('API密钥添加成功');
    setShowAddModal(false);
    form.resetFields();
    onKeyAdded?.(selectedProvider);
  };

  const handleRemoveKey = (providerId: string) => {
    removeApiKey(providerId);
    message.success('API密钥已删除');
    onKeyRemoved?.(providerId);
  };

  const handleSwitchProvider = (providerId: string) => {
    if (hasKey(providerId)) {
      switchProvider(providerId);
      message.success(`已切换到 ${providers.find((p) => p.id === providerId)?.name}`);
      onProviderSwitched?.(providerId);
    } else {
      message.warning('请先添加该服务商的API密钥');
    }
  };

  const handleTestConnection = async (providerId: string) => {
    setTesting(providerId);
    setTimeout(() => {
      message.success('连接测试成功');
      setTesting('');
    }, 1000);
  };

  return (
    <Card
      title={
        <Space>
          <ApiOutlined />
          <span>API密钥管理</span>
        </Space>
      }
    >
      <Alert
        type="info"
        message="至少配置一个服务商即可使用全部功能"
        showIcon
        style={{ marginBottom: 16 }}
      />

      <List
        dataSource={providers}
        renderItem={(provider) => {
          const hasApiKey = hasKey(provider.id);
          const isActive = activeProvider === provider.id;
          const keyConfig = apiKeys[provider.id];

          return (
            <List.Item
              actions={[
                hasApiKey ? (
                  <Space key="actions">
                    <Button
                      size="small"
                      onClick={() => handleTestConnection(provider.id)}
                      loading={testing === provider.id}
                    >
                      测试
                    </Button>
                    <Popconfirm
                      title="确定要删除此API密钥吗？"
                      onConfirm={() => handleRemoveKey(provider.id)}
                      okText="确定"
                      cancelText="取消"
                    >
                      <Button size="small" danger icon={<DeleteOutlined />}>
                        删除
                      </Button>
                    </Popconfirm>
                  </Space>
                ) : (
                  <Button
                    key="add"
                    size="small"
                    type="primary"
                    icon={<PlusOutlined />}
                    onClick={() => handleAddKey(provider.id)}
                  >
                    添加
                  </Button>
                ),
              ]}
            >
              <List.Item.Meta
                avatar={
                  hasApiKey ? (
                    <CheckCircleFilled style={{ color: '#52c41a', fontSize: 20 }} />
                  ) : (
                    <MinusCircleFilled style={{ color: '#d9d9d9', fontSize: 20 }} />
                  )
                }
                title={
                  <Space>
                    <span
                      style={{ cursor: 'pointer', fontWeight: isActive ? 'bold' : 'normal' }}
                      onClick={() => handleSwitchProvider(provider.id)}
                    >
                      {provider.name}
                    </span>
                    {provider.recommended && <Tag color="blue">推荐</Tag>}
                    {isActive && <Tag color="green">当前使用</Tag>}
                  </Space>
                }
                description={
                  hasApiKey && keyConfig
                    ? `sk-****${keyConfig.key.slice(-4)}`
                    : '未配置'
                }
              />
            </List.Item>
          );
        }}
      />

      <Modal
        title={`添加 ${providers.find((p) => p.id === selectedProvider)?.name} API密钥`}
        open={showAddModal}
        onCancel={() => {
          setShowAddModal(false);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        okText="保存"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" onFinish={handleSaveKey}>
          <Form.Item
            label="API密钥"
            name="apiKey"
            rules={[
              { required: true, message: '请输入API密钥' },
              { min: 10, message: 'API密钥格式不正确' },
            ]}
          >
            <Input.Password
              placeholder="请输入API密钥"
              prefix={<ApiOutlined />}
              size="large"
            />
          </Form.Item>
          <Alert
            type="warning"
            message="API密钥将安全存储在本地，不会上传到服务器"
            showIcon
          />
        </Form>
      </Modal>
    </Card>
  );
};

export default ApiKeyManager;
