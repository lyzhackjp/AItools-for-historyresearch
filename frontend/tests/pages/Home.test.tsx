import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import HomePage from '../src/pages/Home';

const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <ConfigProvider locale={zhCN}>{children}</ConfigProvider>
  </BrowserRouter>
);

describe('HomePage', () => {
  it('renders welcome message', () => {
    render(
      <Wrapper>
        <HomePage />
      </Wrapper>
    );

    expect(screen.getByText(/欢迎使用历史研究AI工具/i)).toBeInTheDocument();
  });

  it('renders feature cards', () => {
    render(
      <Wrapper>
        <HomePage />
      </Wrapper>
    );

    expect(screen.getByText('论文润色')).toBeInTheDocument();
    expect(screen.getByText('OCR识别')).toBeInTheDocument();
    expect(screen.getByText('实体识别')).toBeInTheDocument();
  });
});
