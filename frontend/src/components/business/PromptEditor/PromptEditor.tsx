import React, { useState, useEffect } from 'react';
import {
  Card,
  Row,
  Col,
  Button,
  Tag,
  Space,
  Select,
  message,
  Spin,
  Alert,
} from 'antd';
import { SaveOutlined, ReloadOutlined, EyeOutlined } from '@ant-design/icons';
import { PromptEditorProps, PromptTemplate } from '../../types';
import { promptApi } from '../../api';

const { Option } = Select;

const PromptEditor: React.FC<PromptEditorProps> = ({
  moduleId,
  promptId,
  onSave,
  readOnly = false,
}) => {
  const [content, setContent] = useState('');
  const [variables, setVariables] = useState<string[]>([]);
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadPrompt();
    loadTemplates();
  }, [moduleId, promptId]);

  const loadPrompt = async () => {
    setLoading(true);
    try {
      const prompt = await promptApi.getPrompt(moduleId, promptId);
      setContent(prompt.content);
      extractVariables(prompt.content);
    } catch (error) {
      message.error('加载提示词失败');
    } finally {
      setLoading(false);
    }
  };

  const loadTemplates = async () => {
    try {
      const templateList = await promptApi.getTemplates();
      setTemplates(templateList);
    } catch (error) {
      console.error('Failed to load templates:', error);
    }
  };

  const extractVariables = (text: string) => {
    const regex = /\{\{(\w+)\}\}/g;
    const matches: string[] = [];
    let match;
    while ((match = regex.exec(text)) !== null) {
      if (!matches.includes(match[1])) {
        matches.push(match[1]);
      }
    }
    setVariables(matches);
  };

  const handleContentChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newContent = e.target.value;
    setContent(newContent);
    extractVariables(newContent);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await promptApi.updatePrompt(moduleId, promptId, content);
      message.success('提示词保存成功');
      onSave?.(content);
    } catch (error) {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    loadPrompt();
  };

  const handleLoadTemplate = (templateId: string) => {
    const template = templates.find((t) => t.id === templateId);
    if (template) {
      setContent(template.content);
      extractVariables(template.content);
      message.success('模板加载成功');
    }
  };

  if (loading) {
    return (
      <Card>
        <Spin tip="加载中..." />
      </Card>
    );
  }

  return (
    <Card title="提示词编辑器">
      <Row gutter={16}>
        <Col span={18}>
          <div style={{ marginBottom: 16 }}>
            <Space>
              <span>模板选择：</span>
              <Select
                style={{ width: 200 }}
                placeholder="选择预设模板"
                onChange={handleLoadTemplate}
                disabled={readOnly}
              >
                {templates.map((template) => (
                  <Option key={template.id} value={template.id}>
                    {template.name}
                  </Option>
                ))}
              </Select>
            </Space>
          </div>

          <textarea
            value={content}
            onChange={handleContentChange}
            readOnly={readOnly}
            style={{
              width: '100%',
              minHeight: 400,
              padding: 12,
              border: '1px solid #d9d9d9',
              borderRadius: 4,
              fontSize: 14,
              fontFamily: 'Consolas, Monaco, monospace',
              resize: 'vertical',
            }}
            placeholder="在此输入提示词..."
          />
        </Col>

        <Col span={6}>
          <Card size="small" title="变量说明" style={{ marginBottom: 16 }}>
            {variables.length > 0 ? (
              variables.map((v) => (
                <Tag key={v} color="blue" style={{ margin: '4px' }}>
                  {`{{${v}}}`}
                </Tag>
              ))
            ) : (
              <Alert type="info" message="暂无变量" />
            )}
          </Card>

          <Card size="small" title="模板库">
            <Space direction="vertical" style={{ width: '100%' }}>
              <Button block onClick={() => handleLoadTemplate('academic')}>
                学术笔记模板
              </Button>
              <Button block onClick={() => handleLoadTemplate('summary')}>
                文献摘要模板
              </Button>
              <Button block onClick={() => handleLoadTemplate('polish')}>
                论文润色模板
              </Button>
            </Space>
          </Card>
        </Col>
      </Row>

      {!readOnly && (
        <div style={{ marginTop: 16, textAlign: 'right' }}>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={handleReset}>
              重置
            </Button>
            <Button icon={<EyeOutlined />}>预览效果</Button>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              loading={saving}
              onClick={handleSave}
            >
              保存模板
            </Button>
          </Space>
        </div>
      )}
    </Card>
  );
};

export default PromptEditor;
