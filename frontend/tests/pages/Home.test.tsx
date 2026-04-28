import { describe, expect, it } from 'vitest';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import HomePage from '../../src/pages/Home';

function renderHome() {
  return render(
    <BrowserRouter>
      <ConfigProvider locale={zhCN}>
        <HomePage />
      </ConfigProvider>
    </BrowserRouter>,
  );
}

describe('HomePage', () => {
  it('renders both work modes', () => {
    renderHome();

    expect(screen.getByText('全手动经典模式')).toBeInTheDocument();
    expect(screen.getByText('AI agent solo 模式')).toBeInTheDocument();
  });

  it('renders task center entry', () => {
    renderHome();

    expect(screen.getByText('任务中心')).toBeInTheDocument();
  });
});
