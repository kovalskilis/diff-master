import React, { useState } from 'react';
import { FileUpload } from '../components/ui/FileUpload';
import { EditsReview } from '../components/ui/EditsReview';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { useToast } from '../hooks/useToast';
import { documentsAPI } from '../services/api';

interface ExtractedEdits {
  filename: string;
  file_type: string;
  articles: Record<string, string>;
  total_articles: number;
  has_unknown: boolean;
}

export const EditsPage: React.FC = () => {
  const [isUploading, setIsUploading] = useState(false);
  const [extractedEdits, setExtractedEdits] = useState<ExtractedEdits | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const { showToast } = useToast();

  const handleFileUpload = async (file: File) => {
    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await documentsAPI.extractEdits(formData);
      setExtractedEdits(response);
      showToast('Правки успешно извлечены', 'success');
    } catch (error) {
      console.error('Error extracting edits:', error);
      showToast('Ошибка при извлечении правок', 'error');
    } finally {
      setIsUploading(false);
    }
  };

  const handleApproveEdits = async (articles: Record<string, string>) => {
    if (!extractedEdits) return;

    setIsProcessing(true);
    try {
      // For now, we'll use a dummy document ID
      // In a real app, you'd select which document to apply edits to
      const documentId = 1; // This should come from document selection

      const response = await documentsAPI.processApprovedEdits({
        articles,
        document_id: documentId
      });

      showToast('Правки отправлены на обработку', 'success');
      setExtractedEdits(null);
    } catch (error) {
      console.error('Error processing approved edits:', error);
      showToast('Ошибка при обработке правок', 'error');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleCancel = () => {
    setExtractedEdits(null);
  };

  if (isProcessing) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <LoadingSpinner size="lg" />
          <p className="mt-4 text-gray-600">Обработка правок...</p>
        </div>
      </div>
    );
  }

  if (extractedEdits) {
    return (
      <EditsReview
        articles={extractedEdits.articles}
        onApprove={handleApproveEdits}
        onCancel={handleCancel}
        filename={extractedEdits.filename || 'Неизвестный файл'}
        totalArticles={extractedEdits.total_articles}
        hasUnknown={extractedEdits.has_unknown}
      />
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold text-gray-800 mb-4">
          Загрузка правок
        </h1>
        <p className="text-gray-600 text-lg">
          Загрузите файл с правками для предварительного просмотра и согласования
        </p>
      </div>

      <div className="bg-white rounded-lg shadow-lg p-8">
        <FileUpload
          onFileSelect={handleFileUpload}
          accept=".docx,.txt"
          disabled={isUploading}
        />
        
        {isUploading && (
          <div className="mt-6 text-center">
            <LoadingSpinner size="md" />
            <p className="mt-2 text-gray-600">Извлечение правок...</p>
          </div>
        )}

        <div className="mt-8 text-sm text-gray-500">
          <h3 className="font-semibold mb-2">Поддерживаемые форматы:</h3>
          <ul className="list-disc list-inside space-y-1">
            <li><strong>.docx</strong> - документы Microsoft Word</li>
            <li><strong>.txt</strong> - текстовые файлы</li>
          </ul>
          
          <h3 className="font-semibold mb-2 mt-4">Ожидаемый формат:</h3>
          <div className="bg-gray-50 p-3 rounded text-xs font-mono">
            <div>Статья 1</div>
            <div className="ml-4">1) В пункте 7 статьи 6.1:</div>
            <div className="ml-8">а) слова "рабочий день" дополнить...</div>
            <div className="ml-4">2) В статье 11:</div>
            <div className="ml-8">а) в пункте 2 изложить...</div>
            <div className="mt-2">Статья 2</div>
            <div className="ml-4">1) Дополнить статью 2 пунктом...</div>
          </div>
        </div>
      </div>
    </div>
  );
};



