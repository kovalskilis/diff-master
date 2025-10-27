import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, File } from 'lucide-react';
import { motion } from 'framer-motion';
import { cn } from '@/utils/cn';

interface FileUploadProps {
  onUpload: (file: File) => void;
  accept?: Record<string, string[]>;
  maxSize?: number;
  isLoading?: boolean;
}

export const FileUpload = ({
  onUpload,
  accept = { 
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    'text/plain': ['.txt'] 
  },
  maxSize = 10 * 1024 * 1024, // 10MB
  isLoading = false,
}: FileUploadProps) => {
  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      onUpload(acceptedFiles[0]);
    }
  }, [onUpload]);

  const { getRootProps, getInputProps, isDragActive, acceptedFiles } = useDropzone({
    onDrop,
    accept,
    maxSize,
    multiple: false,
    disabled: isLoading,
  });

  const MotionDiv = motion.div as any;

  return (
    <div>
      <MotionDiv
        {...getRootProps()}
        whileHover={{ scale: isLoading ? 1 : 1.01 }}
        className={cn(
          'border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all duration-200',
          isDragActive
            ? 'border-apple-blue bg-apple-blue/5'
            : 'border-apple-gray-300 hover:border-apple-blue',
          isLoading && 'opacity-50 cursor-not-allowed'
        )}
      >
        <input {...getInputProps()} />
        
        {isLoading ? (
          <div className="flex flex-col items-center gap-4">
            <div className="w-12 h-12 border-3 border-apple-blue border-t-transparent rounded-full animate-spin" />
            <p className="text-apple-gray-600">Загрузка...</p>
          </div>
        ) : acceptedFiles.length > 0 ? (
          <div className="flex flex-col items-center gap-4">
            <File className="w-12 h-12 text-apple-blue" />
            <div>
              <p className="font-medium text-apple-gray-900">{acceptedFiles[0].name}</p>
              <p className="text-sm text-apple-gray-500">
                {(acceptedFiles[0].size / 1024).toFixed(2)} KB
              </p>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-4">
            <Upload className="w-12 h-12 text-apple-gray-400" />
            <div>
              <p className="font-medium text-apple-gray-900">
                {isDragActive ? 'Отпустите файл' : 'Перетащите файл сюда'}
              </p>
              <p className="text-sm text-apple-gray-500 mt-1">
                или нажмите для выбора
              </p>
              <p className="text-xs text-apple-gray-400 mt-2">
                Поддерживаются .docx и .txt файлы (до 10 МБ)
              </p>
            </div>
          </div>
        )}
      </MotionDiv>
    </div>
  );
};

