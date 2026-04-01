import React, { useState, useRef, useEffect } from 'react';
import {
  Card,
  Input,
  Button,
  Space,
  Typography,
  Avatar,
  message,
  Spin,
} from 'antd';
import { MessageOutlined, UserOutlined, SendOutlined } from '@ant-design/icons';
import { researchApi } from '../../api';
import { ResearchMessage } from '../../types';

const { Title, Paragraph } = Typography;
const { TextArea } = Input;

const ResearchAssistantPage: React.FC = () => {
  const [messages, setMessages] = useState<ResearchMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) {
      message.warning('请输入内容');
      return;
    }

    const userMessage: ResearchMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: input,
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const assistantMessage = await researchApi.sendMessage(input);
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      message.error('发送失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="fade-in">
      <Title level={2}>
        <MessageOutlined /> 智能研究助手
      </Title>
      <Paragraph type="secondary">
        AI辅助研究，智能问答与文献分析
      </Paragraph>

      <Card style={{ height: 'calc(100vh - 250px)', display: 'flex', flexDirection: 'column' }}>
        <div style={{ flex: 1, overflow: 'auto', marginBottom: 16 }}>
          {messages.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 0' }}>
              <MessageOutlined style={{ fontSize: 48, color: '#d9d9d9' }} />
              <Paragraph type="secondary" style={{ marginTop: 16 }}>
                开始与AI助手对话吧！
              </Paragraph>
            </div>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                style={{
                  display: 'flex',
                  justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  marginBottom: 16,
                }}
              >
                <Space align="start">
                  {msg.role === 'assistant' && (
                    <Avatar icon={<MessageOutlined />} style={{ backgroundColor: '#1890ff' }} />
                  )}
                  <Card
                    size="small"
                    style={{
                      maxWidth: '70%',
                      backgroundColor: msg.role === 'user' ? '#e6f7ff' : '#f5f5f5',
                    }}
                  >
                    <Paragraph style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                      {msg.content}
                    </Paragraph>
                  </Card>
                  {msg.role === 'user' && (
                    <Avatar icon={<UserOutlined />} style={{ backgroundColor: '#52c41a' }} />
                  )}
                </Space>
              </div>
            ))
          )}
          {loading && (
            <div style={{ textAlign: 'center', padding: '20px 0' }}>
              <Spin tip="AI助手正在思考..." />
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div style={{ borderTop: '1px solid #f0f0f0', paddingTop: 16 }}>
          <Space.Compact style={{ width: '100%' }}>
            <TextArea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="输入您的问题..."
              autoSize={{ minRows: 1, maxRows: 4 }}
              style={{ flex: 1 }}
            />
            <Button
              type="primary"
              icon={<SendOutlined />}
              loading={loading}
              onClick={handleSend}
            >
              发送
            </Button>
          </Space.Compact>
        </div>
      </Card>
    </div>
  );
};

export default ResearchAssistantPage;
