import React, { useState } from 'react';
import { Card, Select, Typography, Divider, message } from 'antd';
import { CodeOutlined } from '@ant-design/icons';
import { PromptEditor } from '../../components/business';

const { Title, Paragraph } = Typography;
const { Option } = Select;

const PromptEditorPage: React.FC = () => {
  const [selectedModule, setSelectedModule] = useState('academic_note_generator');
  const [selectedPrompt, setSelectedPrompt] = useState('AN_G001');

  const modules = [
    { id: 'academic_note_generator', name: '学术笔记生成' },
    { id: 'academic_summarizer', name: '学术摘要生成' },
    { id: 'paper_polisher', name: '论文润色' },
    { id: 'ner_processor', name: '实体识别' },
    { id: 'style_transfer', name: '文风迁移' },
  ];

  const prompts = [
    { id: 'AN_G001', name: '基础笔记生成' },
    { id: 'AN_G002', name: '详细笔记生成' },
    { id: 'AN_G003', name: '简要笔记生成' },
  ];

  const handleSave = (content: string) => {
    message.success('提示词已保存');
  };

  return (
    <div className="fade-in">
      <Title level={2}>
        <CodeOutlined /> 提示词编辑器
      </Title>
      <Paragraph type="secondary">
        可视化编辑和管理AI提示词模板
      </Paragraph>

      <Card style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          <div>
            <span style={{ marginRight: 8 }}>选择模块：</span>
            <Select
              value={selectedModule}
              onChange={setSelectedModule}
              style={{ width: 200 }}
            >
              {modules.map((module) => (
                <Option key={module.id} value={module.id}>
                  {module.name}
                </Option>
              ))}
            </Select>
          </div>

          <div>
            <span style={{ marginRight: 8 }}>选择提示词：</span>
            <Select
              value={selectedPrompt}
              onChange={setSelectedPrompt}
              style={{ width: 200 }}
            >
              {prompts.map((prompt) => (
                <Option key={prompt.id} value={prompt.id}>
                  {prompt.name}
                </Option>
              ))}
            </Select>
          </div>
        </div>
      </Card>

      <PromptEditor
        moduleId={selectedModule}
        promptId={selectedPrompt}
        onSave={handleSave}
      />
    </div>
  );
};

export default PromptEditorPage;
