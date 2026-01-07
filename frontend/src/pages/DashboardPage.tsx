import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { FileText, Trash2, Eye, Moon, Sun, Database } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { FileUpload } from '@/components/ui/FileUpload';
import { SkeletonCard } from '@/components/ui/LoadingSpinner';
import { DeletingWidget } from '@/components/ui/DeletingWidget';
import { ToastContainer } from '@/components/ui/Toast';
import { useThemeStore } from '@/hooks/useTheme';
import { useToast } from '@/hooks/useToast';
import { documentsAPI, workspaceAPI } from '@/services/api';
import type { Document } from '@/types';

export const DashboardPage = () => {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useThemeStore();
  const { toasts, removeToast, success, error } = useToast();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploadingBase, setIsUploadingBase] = useState(false);
  const [isUploadingEdits, setIsUploadingEdits] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      const docs = await documentsAPI.list();
      setDocuments(docs);
    } catch (error) {
      console.error('Failed to load documents:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleUploadBase = async (file: File) => {
    setIsUploadingBase(true);
    try {
      const newDoc = await documentsAPI.import(file);
      setDocuments(prev => [newDoc, ...prev]);
      success('Документ загружен', `Базовый документ "${file.name}" успешно загружен`);
    } catch (err: any) {
      console.error('Upload failed:', err);
      let errorMessage = 'Не удалось загрузить базовый документ';
      
      if (err?.code === 'ERR_NETWORK' || err?.message === 'Network Error') {
        errorMessage = 'Не удалось подключиться к серверу. Убедитесь, что бэкенд запущен на http://localhost:8000';
      } else if (err?.response?.data?.detail) {
        errorMessage = err.response.data.detail;
      } else if (err?.message) {
        errorMessage = err.message;
      }
      
      error('Ошибка загрузки', errorMessage);
    } finally {
      setIsUploadingBase(false);
    }
  };

  const getLatestBaseDocument = async (): Promise<number | null> => {
    try {
      const latestDoc = await documentsAPI.getLatest();
      return latestDoc.id;
    } catch (err: any) {
      if (err?.response?.status === 404) {
        return null;
      }
      throw err;
    }
  };

  const handleUploadEdits = async (file: File) => {
    setIsUploadingEdits(true);
    try {
      // Автоматически получаем последний загруженный базовый документ
      const latestDocumentId = await getLatestBaseDocument();
      
      if (!latestDocumentId) {
        error('Ошибка', 'Сначала загрузите базовый документ');
        return;
      }

      await workspaceAPI.uploadFile(latestDocumentId, file);
      success('Правки загружены', `Файл "${file.name}" успешно загружен`);
      // Переход на страницу документа для работы с правками
      navigate(`/document/${latestDocumentId}`);
    } catch (err: any) {
      console.error('Edits upload failed:', err);
      let errorMessage = 'Не удалось загрузить файл с правками';
      
      if (err?.code === 'ERR_NETWORK' || err?.message === 'Network Error') {
        errorMessage = 'Не удалось подключиться к серверу. Убедитесь, что бэкенд запущен на http://localhost:8000';
      } else if (err?.response?.data?.detail) {
        errorMessage = err.response.data.detail;
      } else if (err?.message) {
        errorMessage = err.message;
      }
      
      error('Ошибка загрузки', errorMessage);
    } finally {
      setIsUploadingEdits(false);
    }
  };

  const handleDelete = async (id: number) => {
    const document = documents.find(d => d.id === id);
    if (!confirm(`Вы уверены, что хотите удалить документ "${document?.name}"?`)) return;
    
    setDeletingId(id);
    try {
      await documentsAPI.delete(id);
      // Небольшая задержка для завершения анимации прогресса
      await new Promise(resolve => setTimeout(resolve, 300));
      setDocuments(prev => prev.filter(d => d.id !== id));
      success('Документ удален', `"${document?.name}" успешно удален`);
    } catch (err) {
      console.error('Delete failed:', err);
      success('Ошибка удаления', 'Не удалось удалить документ');
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-apple-gray-50 to-white dark:from-apple-gray-900 dark:to-apple-gray-800">
      {/* Header */}
      <header className="bg-white/80 dark:bg-apple-gray-800/80 backdrop-blur-xl border-b border-apple-gray-200 dark:border-apple-gray-700 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-apple-blue rounded-xl">
              <FileText className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-semibold text-apple-gray-900 dark:text-apple-gray-50">Legal Diff</h1>
              <p className="text-sm text-apple-gray-600 dark:text-apple-gray-400">Система обработки документов</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button 
              variant="ghost" 
              onClick={toggleTheme}
              className="p-2"
              title={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
            >
              {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="space-y-12"
        >
          {/* Two Main Sections Side by Side */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-12">
            {/* Section 1: Base Documents (Permanent Storage) */}
            <div>
              {/* Upload New Base Document */}
              <Card className="h-full">
                <CardHeader>
                  <CardTitle>Загрузить базовый документ</CardTitle>
                  <CardDescription>
                    Загрузите базовую версию документа для постоянного хранения
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <FileUpload 
                    onUpload={handleUploadBase} 
                    isLoading={isUploadingBase}
                  />
                </CardContent>
              </Card>
            </div>

            {/* Section 2: Edits (Temporary Upload) */}
            <div>
              {/* Edits File Upload */}
              <Card className="h-full">
                <CardHeader>
                  <CardTitle>Загрузить документ с правками</CardTitle>
                  <CardDescription>
                    Загрузите файл с изменениями для применения к выбранному документу
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <FileUpload 
                    onUpload={handleUploadEdits} 
                    isLoading={isUploadingEdits}
                  />
                </CardContent>
              </Card>
            </div>
          </div>

          {/* Base Documents List */}
          <section>
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                <Database className="w-6 h-6 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-apple-gray-900 dark:text-apple-gray-50">
                  Загруженные документы
                </h2>
                <p className="text-sm text-apple-gray-600 dark:text-apple-gray-400">
                  Список всех загруженных базовых документов
                </p>
              </div>
            </div>

            {isLoading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {[1, 2, 3].map(i => <SkeletonCard key={i} />)}
              </div>
            ) : documents.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {documents.map((doc) => (
                  <motion.div
                    key={doc.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                  >
                    {deletingId === doc.id ? (
                      <DeletingWidget documentName={doc.name} />
                    ) : (
                      <Card hover onClick={() => navigate(`/document/${doc.id}`)}>
                        <div className="flex items-start justify-between mb-3">
                          <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                            <FileText className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                          </div>
                          <div className="flex gap-2">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate(`/document/${doc.id}`);
                              }}
                              className="p-2 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-lg transition-colors"
                              title="Открыть документ"
                            >
                              <Eye className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDelete(doc.id);
                              }}
                              disabled={deletingId !== null}
                              className={`p-2 rounded-lg transition-colors ${
                                deletingId !== null 
                                  ? 'bg-gray-100 cursor-not-allowed' 
                                  : 'hover:bg-red-50 dark:hover:bg-red-900/20'
                              }`}
                              title={deletingId !== null ? "Удаление в процессе..." : "Удалить"}
                            >
                              <Trash2 className="w-4 h-4 text-red-500" />
                            </button>
                          </div>
                        </div>
                        <h3 className="font-semibold text-apple-gray-900 dark:text-apple-gray-50 mb-2 truncate">
                          {doc.name}
                        </h3>
                        <div className="flex items-center gap-2 mb-2">
                          <span className={`px-2 py-0.5 text-xs font-medium rounded ${
                            doc.source_type === 'docx' 
                              ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300' 
                              : 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
                          }`}>
                            {doc.source_type.toUpperCase()}
                          </span>
                          {doc.structure && Object.keys(doc.structure).length > 0 && (
                            <span className="text-xs text-apple-gray-500">
                              {Object.keys(doc.structure).length} {Object.keys(doc.structure).length === 1 ? 'статья' : 'статей'}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-apple-gray-500">
                          Загружен {new Date(doc.imported_at).toLocaleDateString('ru-RU', {
                            day: 'numeric',
                            month: 'short',
                            year: 'numeric',
                          })} в {new Date(doc.imported_at).toLocaleTimeString('ru-RU', {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </p>
                      </Card>
                    )}
                  </motion.div>
                ))}
              </div>
            ) : (
              <Card className="text-center py-12">
                <Database className="w-16 h-16 text-apple-gray-300 dark:text-apple-gray-600 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-apple-gray-900 dark:text-apple-gray-50 mb-2">
                  Нет загруженных документов
                </h3>
                <p className="text-apple-gray-600 dark:text-apple-gray-400">
                  Загрузите первый документ для начала работы
                </p>
              </Card>
            )}
          </section>
        </motion.div>
      </main>

      {/* Toast Notifications */}
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </div>
  );
};
