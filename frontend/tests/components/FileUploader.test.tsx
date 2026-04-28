import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import FileUploader from '../../src/components/common/FileUploader/FileUploader';

describe('FileUploader', () => {
  it('renders the upload affordance', () => {
    render(<FileUploader accept=".pdf" onFilesSelected={vi.fn()} />);

    expect(screen.getByText('拖拽文件到此处，或点击选择')).toBeInTheDocument();
    expect(screen.getByText(/本地 OCR/)).toBeInTheDocument();
  });
});
