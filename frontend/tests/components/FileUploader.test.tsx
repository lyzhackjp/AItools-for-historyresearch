import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import FileUploader from '../src/components/common/FileUploader/FileUploader';

describe('FileUploader', () => {
  it('renders upload area', () => {
    const mockOnUpload = vi.fn();
    const mockOnError = vi.fn();

    render(
      <FileUploader
        accept={['.pdf']}
        maxSize={10}
        onUpload={mockOnUpload}
        onError={mockOnError}
      />
    );

    expect(screen.getByText(/拖拽文件到此处/i)).toBeInTheDocument();
  });

  it('accepts valid files', async () => {
    const mockOnUpload = vi.fn();
    const mockOnError = vi.fn();

    render(
      <FileUploader
        accept={['.pdf']}
        maxSize={10}
        onUpload={mockOnUpload}
        onError={mockOnError}
      />
    );

    const file = new File(['content'], 'test.pdf', { type: 'application/pdf' });
    const input = screen.getByRole('button');

    await userEvent.upload(input, file);

    expect(mockOnUpload).toHaveBeenCalledWith([file]);
  });

  it('rejects invalid file types', async () => {
    const mockOnUpload = vi.fn();
    const mockOnError = vi.fn();

    render(
      <FileUploader
        accept={['.pdf']}
        maxSize={10}
        onUpload={mockOnUpload}
        onError={mockOnError}
      />
    );

    const file = new File(['content'], 'test.txt', { type: 'text/plain' });
    const input = screen.getByRole('button');

    await userEvent.upload(input, file);

    expect(mockOnError).toHaveBeenCalled();
    expect(mockOnUpload).not.toHaveBeenCalled();
  });
});
