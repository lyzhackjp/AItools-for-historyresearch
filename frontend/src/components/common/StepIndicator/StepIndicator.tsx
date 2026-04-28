import { Steps } from 'antd';

interface StepIndicatorProps {
  current: number;
  steps: string[];
}

function StepIndicator({ current, steps }: StepIndicatorProps) {
  return <Steps current={current} items={steps.map((title) => ({ title }))} size="small" />;
}

export default StepIndicator;
