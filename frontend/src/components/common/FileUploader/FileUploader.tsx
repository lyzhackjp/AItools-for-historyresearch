import React, { useCallback, useState } from 'react';
import { Upload, message } from 'antd';
import { InboxOutlined } from '@ant-design/icons';
import type { UploadProps } from 'antd';
import classNames from 'classnames';
import { FileUploaderProps } from '../../types';

const { Dragger } = Upload;

const FileUploader: React.FC<FileUploaderProps> = ({
  accept,
  maxSize,
  multiple = false,
  onUpload,
  onError,
  disabled = false,
  className,
}) => {
  const [isDragging, setIsDragging] = useState(false);

  const validateFiles = useCallback(
    (files: File[]): File[] => {
      const validFiles: File[] = [];
      const maxSizeBytes = maxSize * 1024 * 1024;

      for (const file of files) {
        const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();
        const isValidType = accept.some((type) =>
          type.toLowerCase() === fileExtension
        );

        if (!isValidType) {
          onError(`不支持的文件格式: ${file.name}`);
          continue;
        }

        if (file.size > maxSizeBytes) {
          onError(`文件大小超过限制: ${file.name} (最大 ${maxSize}MB)`);
          continue;
        }

        validFiles.push(file);
      }

      return validFiles;
    },
    [accept, maxSize, onError]
  );

  const uploadProps: UploadProps = {
    name: 'file',
    multiple,
    disabled,
    accept: accept.join(','),
    beforeUpload: (file) => {
      const validFiles = validateFiles([file]);
      if (validFiles.length > 0) {
        onUpload(validFiles);
      }
      return false;
    },
    onDrop: (e) => {
      setIsDragging(false);
      const files = Array.from(e.dataTransfer.files);
      const validFiles = validateFiles(files);
      if (validFiles.length > 0) {
        onUpload(validFiles);
      }
    },
    onDragEnter: () => setIsDragging(true),
    onDragLeave: () => setIsDragging(false),
    showUploadList: false,
  };

  return (
    <div className={classNames('upload-dragger', className, { dragging: isDragging })}>
      <Dragger {...uploadProps}>
        <p className="ant-upload-drag-icon">
          <InboxOutlined style={{ fontSize: 48, color: '#1890ff' }} />
        </p>
        <p className="ant-upload-text" style={{ fontSize: 16, margin: '16px 0' }}>
          拖拽文件到此处，或<span style={{ color: '#1890ff' }}>点击选择</span>
        </p>
        <p className="ant-upload-hint" style={{ color: '#999' }}>
          支持 {accept.join(', ')} 格式，最大 {maxSize}MB
        </p>
      </Dragger>
    </div>
  );
};

export default FileUploader;
