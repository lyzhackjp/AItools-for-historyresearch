import React from 'react';
import { Steps } from 'antd';
import { CheckCircleFilled } from '@ant-design/icons';
import { StepIndicatorProps } from '../../types';

const StepIndicator: React.FC<StepIndicatorProps> = ({ current, total, labels }) => {
  const items = Array.from({ length: total }, (_, index) => ({
    title: labels?.[index] || `步骤 ${index + 1}`,
    status: index < current ? 'finish' : index === current ? 'process' : 'wait',
    icon: index < current ? <CheckCircleFilled style={{ color: '#52c41a' }} /> : undefined,
  }));

  return (
    <div style={{ marginBottom: 24 }}>
      <Steps current={current} items={items} />
    </div>
  );
};

export default StepIndicator;
