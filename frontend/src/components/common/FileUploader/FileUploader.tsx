import { InboxOutlined } from '@ant-design/icons';
import { Upload, type UploadProps } from 'antd';

interface FileUploaderProps {
  accept?: string;
  multiple?: boolean;
  onFilesSelected: (files: File[]) => void;
}

function FileUploader({ accept, multiple = false, onFilesSelected }: FileUploaderProps) {
  const props: UploadProps = {
    accept,
    beforeUpload: (file) => {
      onFilesSelected([file]);
      return false;
    },
    multiple,
    onChange: (info) => {
      if (multiple) {
        onFilesSelected(info.fileList.map((item) => item.originFileObj).filter(Boolean) as File[]);
      }
    },
    showUploadList: true,
  };

  return (
    <Upload.Dragger {...props}>
      <p className="ant-upload-drag-icon">
        <InboxOutlined />
      </p>
      <p className="ant-upload-text">拖拽文件到此处，或点击选择</p>
      <p className="ant-upload-hint">支持本地 OCR、远程大模型 OCR、DOCX 解析和批量处理场景。</p>
    </Upload.Dragger>
  );
}

export default FileUploader;
