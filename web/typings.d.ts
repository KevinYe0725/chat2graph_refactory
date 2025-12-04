import '@umijs/max/typings';

export interface IFile {
  name: string;
  file: File;
  file_id: string;
  status: 'success' | 'error' | 'uploading' | 'done';
}
