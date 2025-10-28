import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { 
  ArrowLeft, Upload, Search, FileText, 
  Play, History 
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Modal } from '@/components/ui/Modal';
import { FileUpload } from '@/components/ui/FileUpload';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { documentsAPI, workspaceAPI, editsAPI } from '@/services/api';
import type { Document, WorkspaceFile } from '@/types';

export const DocumentPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [document, setDocument] = useState<Document | null>(null);
  const [workspaceFiles, setWorkspaceFiles] = useState<WorkspaceFile[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  useEffect(() => {
    if (id) {
      loadDocument();
      loadWorkspaceFiles();
    }
  }, [id]);

  const loadDocument = async () => {
    try {
      const doc = await documentsAPI.get(Number(id));
      setDocument(doc);
    } catch (error) {
      console.error('Failed to load document:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const loadWorkspaceFiles = async () => {
    try {
      const files = await workspaceAPI.list(Number(id));
      setWorkspaceFiles(files);
    } catch (error) {
      console.error('Failed to load workspace files:', error);
    }
  };

  const handleUploadEdits = async (file: File) => {
    setIsUploading(true);
    try {
      const newFile = await workspaceAPI.uploadFile(Number(id), file);
      setWorkspaceFiles([newFile, ...workspaceFiles]);
      setIsUploadModalOpen(false);
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Ошибка загрузки файла правок');
    } finally {
      setIsUploading(false);
    }
  };

  const handleStartPhase1 = async (workspaceFileId: number) => {
    try {
      // Сначала проверяем, есть ли уже созданные цели
      const existingTargets = await editsAPI.getTargets(workspaceFileId);
      
      if (existingTargets && existingTargets.length > 0) {
        // Цели уже существуют, просто переходим на страницу Review
        console.log('Targets already exist, loading existing results');
        navigate(`/review/${workspaceFileId}`);
      } else {
        // Целей нет, запускаем Phase1 и передаём task_id, чтобы ReviewPage не стартовал повторно
        console.log('No targets found, starting Phase 1');
        const res = await editsAPI.startPhase1(workspaceFileId);
        navigate(`/review/${workspaceFileId}?task=${encodeURIComponent(res.task_id)}`);
      }
    } catch (error) {
      console.error('Failed to start Phase 1:', error);
      alert('Ошибка запуска поиска целей');
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (!document) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Card>
          <CardContent>
            <p>Документ не найден</p>
            <Button onClick={() => navigate('/dashboard')} className="mt-4">
              Вернуться
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }
  
  return (
    <div className="min-h-screen bg-gradient-to-br from-apple-gray-50 to-white dark:from-apple-gray-900 dark:to-apple-gray-800">
      {/* Header */}
      <header className="bg-white/80 dark:bg-apple-gray-800/80 backdrop-blur-xl border-b border-apple-gray-200 dark:border-apple-gray-700 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              icon={<ArrowLeft />}
              onClick={() => navigate('/dashboard')}
            >
              Назад
            </Button>
            <div className="flex-1">
              <h1 className="text-xl font-semibold text-apple-gray-900 dark:text-apple-gray-50">
                {document.name}
              </h1>
              <p className="text-sm text-apple-gray-600 dark:text-apple-gray-400">
                Базовый документ
              </p>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-12">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column - Actions */}
          <div className="lg:col-span-2 space-y-6">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <Card>
                <CardHeader>
                  <CardTitle>Загрузить файл правок</CardTitle>
                  <CardDescription>
                    Загрузите файл с правками для их применения к базовому документу
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Button
                    variant="primary"
                    icon={<Upload />}
                    onClick={() => setIsUploadModalOpen(true)}
                    className="w-full"
                  >
                    Загрузить правки
                  </Button>
                </CardContent>
              </Card>
            </motion.div>

            {/* Workspace Files */}
            {workspaceFiles.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
              >
                <h3 className="text-lg font-semibold text-apple-gray-900 mb-4">
                  Файлы правок
                </h3>
                <div className="space-y-4">
                  {workspaceFiles.map((file) => (
                    <Card key={file.id}>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                          <div className="p-3 bg-apple-blue/10 rounded-xl">
                            <FileText className="w-6 h-6 text-apple-blue" />
                          </div>
                          <div>
                            <h4 className="font-semibold text-apple-gray-900">
                              {file.filename}
                            </h4>
                            <p className="text-sm text-apple-gray-500">
                              {new Date(file.created_at).toLocaleDateString('ru-RU')}
                            </p>
                          </div>
                        </div>
                        <Button
                          variant="primary"
                          icon={<Play />}
                          onClick={() => handleStartPhase1(file.id)}
                        >
                          Найти цели
                        </Button>
                      </div>
                    </Card>
                  ))}
                </div>
              </motion.div>
            )}
          </div>

          {/* Right Column - Quick Actions */}
          <div className="space-y-4">
            <Card hover onClick={() => navigate(`/search/${id}`)}>
              <div className="flex items-center gap-4">
                <div className="p-3 bg-purple-100 rounded-xl">
                  <Search className="w-6 h-6 text-purple-600" />
                </div>
                <div>
                  <h4 className="font-semibold text-apple-gray-900">Поиск</h4>
                  <p className="text-sm text-apple-gray-600">
                    Найти в документе
                  </p>
                </div>
              </div>
            </Card>

            <Card hover onClick={() => navigate(`/versions/${id}`)}>
              <div className="flex items-center gap-4">
                <div className="p-3 bg-green-100 rounded-xl">
                  <History className="w-6 h-6 text-green-600" />
                </div>
                <div>
                  <h4 className="font-semibold text-apple-gray-900">Версии</h4>
                  <p className="text-sm text-apple-gray-600">
                    История изменений
                  </p>
                </div>
              </div>
            </Card>
          </div>
        </div>
      </main>

      {/* Upload Modal */}
      <Modal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        title="Загрузить файл правок"
        description="Выберите файл .docx или .txt с правками"
        size="md"
      >
        <FileUpload onUpload={handleUploadEdits} isLoading={isUploading} />
      </Modal>
    </div>
  );
};

