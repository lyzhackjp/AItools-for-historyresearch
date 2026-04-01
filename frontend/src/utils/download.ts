import { downloadFile } from './format';

export const downloadJSON = (data: any, filename: string) => {
  const content = JSON.stringify(data, null, 2);
  downloadFile(content, filename, 'application/json');
};

export const downloadCSV = (data: any[], filename: string) => {
  if (data.length === 0) return;

  const headers = Object.keys(data[0]);
  const csvContent = [
    headers.join(','),
    ...data.map((row) =>
      headers.map((header) => `"${row[header] || ''}"`).join(',')
    ),
  ].join('\n');

  downloadFile(csvContent, filename, 'text/csv');
};

export const downloadText = (content: string, filename: string) => {
  downloadFile(content, filename, 'text/plain');
};

export const downloadMarkdown = (content: string, filename: string) => {
  downloadFile(content, filename, 'text/markdown');
};
