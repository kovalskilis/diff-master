import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { FileText, Upload, Plus, Trash2, LogOut, Eye, Moon, Sun } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardTitle, CardDescription } from '@/components/ui/Card';
import { Modal } from '@/components/ui/Modal';
import { FileUpload } from '@/components/ui/FileUpload';
import { SkeletonCard } from '@/components/ui/LoadingSpinner';
import { DocumentStructure } from '@/components/ui/DocumentStructure';
import { DeletingWidget } from '@/components/ui/DeletingWidget';
import { ToastContainer } from '@/components/ui/Toast';
import { useAuthStore } from '@/hooks/useAuthStore';
import { useThemeStore } from '@/hooks/useTheme';
import { useToast } from '@/hooks/useToast';
import { documentsAPI } from '@/services/api';
import type { Document } from '@/types';

export const DashboardPage = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const { theme, toggleTheme } = useThemeStore();
  const { toasts, removeToast, success } = useToast();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
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

  const handleUpload = async (file: File) => {
    setIsUploading(true);
    try {
      const newDoc = await documentsAPI.import(file);
      setDocuments(prev => [newDoc, ...prev]);
      setSelectedDocument(newDoc); // Show structure of newly uploaded document
      setIsUploadModalOpen(false);
      success('Документ загружен', `Файл "${file.name}" успешно загружен`);
    } catch (err) {
      console.error('Upload failed:', err);
      success('Ошибка загрузки', 'Не удалось загрузить документ');
    } finally {
      setIsUploading(false);
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

  const handleLogout = async () => {
    await logout();
    navigate('/login');
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
              <p className="text-sm text-apple-gray-600 dark:text-apple-gray-400">{user?.email}</p>
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
            <Button variant="ghost" onClick={handleLogout} icon={<LogOut />}>
              Выйти
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
        >
          <div className="flex items-center justify-between mb-8">
            <div>
              <h2 className="text-3xl font-bold text-apple-gray-900 dark:text-apple-gray-50 mb-2">
                Мои документы
              </h2>
              <p className="text-apple-gray-600 dark:text-apple-gray-400">
                Загрузите базовый документ для начала работы
              </p>
            </div>
            <div className="flex gap-3">
              <Button
                variant="primary"
                icon={<Plus />}
                onClick={() => setIsUploadModalOpen(true)}
              >
                Новый документ
              </Button>
            </div>
          </div>

          {/* Documents Grid */}
          {isLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[1, 2, 3].map(i => <SkeletonCard key={i} />)}
            </div>
          ) : documents.length === 0 ? (
            <Card className="text-center py-12">
              <Upload className="w-16 h-16 text-apple-gray-300 mx-auto mb-4" />
              <CardTitle className="mb-2">Нет документов</CardTitle>
              <CardDescription className="mb-6">
                Загрузите первый документ для начала работы
              </CardDescription>
              <Button
                variant="primary"
                icon={<Plus />}
                onClick={() => setIsUploadModalOpen(true)}
              >
                Загрузить документ
              </Button>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {documents.map((doc, idx) => (
                <motion.div
                  key={doc.id}
                  layout
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  transition={{ delay: idx * 0.1 }}
                >
                  {deletingId === doc.id ? (
                    <DeletingWidget documentName={doc.name} />
                  ) : (
                    <Card hover onClick={() => navigate(`/document/${doc.id}`)}>
                      <div className="flex items-start justify-between mb-4">
                        <div className="p-3 bg-apple-blue/10 rounded-xl">
                          <FileText className="w-6 h-6 text-apple-blue" />
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={async (e) => {
                              e.stopPropagation();
                              // Always load fresh document with structure
                              try {
                                const fullDoc = await documentsAPI.get(doc.id);
                                setSelectedDocument(fullDoc);
                              } catch (error) {
                                console.error('Failed to load document structure:', error);
                                // Fallback to cached document
                                setSelectedDocument(doc);
                              }
                            }}
                            className="p-2 hover:bg-blue-50 rounded-lg transition-colors"
                            title="Показать структуру"
                          >
                            <Eye className="w-4 h-4 text-apple-blue" />
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
                                : 'hover:bg-red-50'
                            }`}
                            title={deletingId !== null ? "Удаление в процессе..." : "Удалить"}
                          >
                            <Trash2 className="w-4 h-4 text-red-500" />
                          </button>
                        </div>
                      </div>
                      <h3 className="font-semibold text-apple-gray-900 mb-2 truncate">
                        {doc.name}
                      </h3>
                      <p className="text-sm text-apple-gray-500">
                        {new Date(doc.imported_at).toLocaleDateString('ru-RU', {
                          day: 'numeric',
                          month: 'long',
                          year: 'numeric',
                        })}
                      </p>
                    </Card>
                  )}
                </motion.div>
              ))}
            </div>
          )}
        </motion.div>
      </main>

      {/* Upload Modal */}
      <Modal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        title="Загрузить базовый документ"
        description="Выберите файл .docx или .txt с базовой версией документа"
        size="md"
      >
        <FileUpload onUpload={handleUpload} isLoading={isUploading} />
      </Modal>

      {/* Document Structure Modal */}
      <Modal
        isOpen={!!selectedDocument}
        onClose={() => setSelectedDocument(null)}
        title={selectedDocument ? `Структура: ${selectedDocument.name}` : ''}
        description="Просмотр структуры документа по статьям"
        size="xl"
      >
        {selectedDocument && selectedDocument.structure && Object.keys(selectedDocument.structure).length > 0 && (
          <DocumentStructure structure={selectedDocument.structure} />
        )}
        {selectedDocument && selectedDocument.structure && Object.keys(selectedDocument.structure).length === 0 && (
          <div className="text-center py-8 text-apple-gray-500">
            <p>Структура пуста (0 статей)</p>
          </div>
        )}
        {selectedDocument && !selectedDocument.structure && (
          <div className="text-center py-8 text-apple-gray-500">
            <p>Структура документа не найдена</p>
          </div>
        )}
      </Modal>

      {/* Toast Notifications */}
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </div>
  );
};

