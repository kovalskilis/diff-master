import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  ArrowLeft, Check, Edit, Search, AlertCircle, 
  Play, Trash2, Plus
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Modal } from '@/components/ui/Modal';
import { Input } from '@/components/ui/Input';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { editsAPI, searchAPI } from '@/services/api';
import type { EditTarget, SearchResult } from '@/types';

export const ReviewPage = () => {
  const { workspaceFileId } = useParams<{ workspaceFileId: string }>();
  const navigate = useNavigate();
  const [targets, setTargets] = useState<EditTarget[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [taskStatus, setTaskStatus] = useState<string>('');
  
  // Edit modal state
  const [editingTarget, setEditingTarget] = useState<EditTarget | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  
  // Add new target modal state
  const [isAddingTarget, setIsAddingTarget] = useState(false);
  const [newInstructionText, setNewInstructionText] = useState('');
  const [newArticleId, setNewArticleId] = useState<number | null>(null);

  useEffect(() => {
    if (workspaceFileId) {
      checkAndStartPhase1();
    }
  }, [workspaceFileId]);

  const checkAndStartPhase1 = async () => {
    try {
      // First check if targets already exist
      const existingTargets = await editsAPI.getTargets(Number(workspaceFileId));
      
      if (existingTargets && existingTargets.length > 0) {
        // Targets already exist, just load them
        setTargets(existingTargets);
        setIsLoading(false);
      } else {
        // No targets exist, start Phase 1
        startPhase1();
      }
    } catch (error) {
      console.error('Failed to check targets:', error);
      // If error getting targets, try starting Phase1 anyway
      startPhase1();
    }
  };

  const startPhase1 = async () => {
    try {
      const response = await editsAPI.startPhase1(Number(workspaceFileId));
      pollTaskStatus(response.task_id);
    } catch (error) {
      console.error('Failed to start phase 1:', error);
      setIsLoading(false);
    }
  };

  const pollTaskStatus = async (taskId: string) => {
    const interval = setInterval(async () => {
      try {
        const status = await editsAPI.getTaskStatus(taskId);
        setTaskStatus(status.status);
        
        if (status.status === 'SUCCESS') {
          clearInterval(interval);
          loadTargets();
        } else if (status.status === 'FAILURE') {
          clearInterval(interval);
          alert('Ошибка обработки: ' + (status.error || 'Неизвестная ошибка'));
          setIsLoading(false);
        }
      } catch (error) {
        clearInterval(interval);
        console.error('Failed to check task status:', error);
        setIsLoading(false);
      }
    }, 2000);
  };

  const loadTargets = async () => {
    try {
      const data = await editsAPI.getTargets(Number(workspaceFileId));
      setTargets(data);
    } catch (error) {
      console.error('Failed to load targets:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleEditTarget = (target: EditTarget) => {
    setEditingTarget(target);
    setSearchQuery('');
    setSearchResults([]);
  };

  const handleSearch = async () => {
    if (!searchQuery.trim() || !editingTarget) return;
    
    // Get document ID from current editing target or first target's base_document_id
    const documentId = editingTarget.base_document_id || targets[0]?.base_document_id;
    
    if (!documentId) {
      alert('Не удалось определить ID документа. Пожалуйста, перезагрузите страницу.');
      return;
    }
    
    setIsSearching(true);
    try {
      console.log('Searching with document ID:', documentId, 'query:', searchQuery);
      const results = await searchAPI.searchTaxUnits(searchQuery, documentId);
      setSearchResults(results);
      console.log('Search results:', results);
      
      if (results.length === 0) {
        alert('Ничего не найдено. Попробуйте другой запрос.');
      }
    } catch (error) {
      console.error('Search failed:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      alert('Ошибка поиска: ' + errorMessage);
    } finally {
      setIsSearching(false);
    }
  };

  const handleSelectTaxUnit = async (taxUnitId: number) => {
    if (!editingTarget) return;
    
    try {
      const updated = await editsAPI.updateTarget(editingTarget.id, taxUnitId);
      setTargets(targets.map(t => t.id === updated.id ? updated : t));
      setEditingTarget(null);
    } catch (error) {
      console.error('Failed to update target:', error);
      alert('Ошибка обновления цели');
    }
  };

  const handleStartPhase2 = async () => {
    try {
      await editsAPI.startPhase2(Number(workspaceFileId));
      navigate(`/diff/${workspaceFileId}`);
    } catch (error) {
      console.error('Failed to start phase 2:', error);
      alert('Ошибка применения правок');
    }
  };

  const handleDeleteTarget = async (targetId: number) => {
    if (!confirm('Вы уверены, что хотите удалить эту правку?')) {
      return;
    }
    
    try {
      await editsAPI.deleteTarget(targetId);
      setTargets(targets.filter(t => t.id !== targetId));
    } catch (error) {
      console.error('Failed to delete target:', error);
      alert('Ошибка удаления правки');
    }
  };

  const handleAddTarget = async () => {
    if (!newInstructionText.trim()) {
      alert('Введите текст правки');
      return;
    }
    
    if (!newArticleId) {
      alert('Выберите статью');
      return;
    }
    
    try {
      const newTarget = await editsAPI.createTarget(Number(workspaceFileId), newInstructionText, newArticleId);
      setTargets([...targets, newTarget]);
      setIsAddingTarget(false);
      setNewInstructionText('');
      setNewArticleId(null);
    } catch (error) {
      console.error('Failed to create target:', error);
      alert('Ошибка создания правки');
    }
  };
  
  if (isLoading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-apple-gray-50 to-white dark:from-apple-gray-900 dark:to-apple-gray-800">
        <LoadingSpinner size="lg" />
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="mt-6 text-apple-gray-700 dark:text-apple-gray-300 font-medium"
        >
          {taskStatus === 'PENDING' && 'Инициализация...'}
          {taskStatus === 'STARTED' && 'Анализируем правки с помощью LLM...'}
          {taskStatus === 'PROCESSING' && 'Ищем соответствия в документе...'}
          {!taskStatus && 'Загрузка...'}
        </motion.p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-apple-gray-50 to-white dark:from-apple-gray-900 dark:to-apple-gray-800">
      {/* Header */}
      <header className="bg-white/80 dark:bg-apple-gray-800/80 backdrop-blur-xl border-b border-apple-gray-200 dark:border-apple-gray-700 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                icon={<ArrowLeft />}
                onClick={() => navigate(-1)}
              >
                Назад
              </Button>
              <div>
                <h1 className="text-xl font-semibold text-apple-gray-900 dark:text-apple-gray-50">
                  Проверка целей правок
                </h1>
                <p className="text-sm text-apple-gray-600 dark:text-apple-gray-400">
                  Найдено {targets.length} правок
                </p>
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                icon={<Plus />}
                onClick={() => setIsAddingTarget(true)}
              >
                Добавить правку
              </Button>
              <Button
                variant="primary"
                icon={<Play />}
                onClick={handleStartPhase2}
                disabled={targets.some(t => !t.article_id)}
              >
                Применить правки
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-12">
        <AnimatePresence>
          {targets.length === 0 ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <Card className="text-center py-12">
                <AlertCircle className="w-16 h-16 text-apple-gray-300 dark:text-apple-gray-600 mx-auto mb-4" />
                <h3 className="text-xl font-semibold text-apple-gray-900 dark:text-apple-gray-50 mb-2">
                  Правки не найдены
                </h3>
                <p className="text-apple-gray-600 dark:text-apple-gray-400">
                  LLM не смог извлечь правки из файла
                </p>
              </Card>
            </motion.div>
          ) : (
            <div className="space-y-4">
              {targets.map((target, idx) => (
                <motion.div
                  key={target.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.05 }}
                >
                  <Card className="hover:shadow-apple-lg transition-shadow">
                    <div className="flex items-start gap-6">
                      {/* Number */}
                      <div className="flex-shrink-0">
                        <div className="w-10 h-10 rounded-full bg-apple-blue/10 dark:bg-apple-blue/20 flex items-center justify-center">
                          <span className="text-apple-blue font-semibold">
                            {idx + 1}
                          </span>
                        </div>
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <h4 className="font-semibold text-apple-gray-900 dark:text-apple-gray-50 mb-2">
                          Инструкция правки:
                        </h4>
                        <p className="text-apple-gray-700 dark:text-apple-gray-300 mb-4 bg-apple-gray-50 dark:bg-apple-gray-900 p-4 rounded-xl">
                          {target.instruction_text}
                        </p>

                        <div className="flex items-center gap-3 text-sm">
                          <span className="font-medium text-apple-gray-600 dark:text-apple-gray-400">
                            Цель:
                          </span>
                          {target.confirmed_tax_unit_breadcrumbs ? (
                            <span className="text-apple-blue bg-apple-blue/10 px-3 py-1 rounded-lg">
                              {target.confirmed_tax_unit_breadcrumbs}
                            </span>
                          ) : target.article_number ? (
                            <span className="text-orange-600 dark:text-orange-400 bg-orange-50 dark:bg-orange-900/30 px-3 py-1 rounded-lg">
                              Статья {target.article_number}
                            </span>
                          ) : (
                            <span className="text-apple-gray-400 dark:text-apple-gray-500">
                              Не определено
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex-shrink-0 flex gap-2">
                        <Button
                          variant="secondary"
                          size="sm"
                          icon={<Edit />}
                          onClick={() => handleEditTarget(target)}
                        >
                          Изменить
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          icon={<Trash2 />}
                          onClick={() => handleDeleteTarget(target.id)}
                          className="text-red-600 hover:text-red-700 hover:bg-red-50"
                        >
                          Удалить
                        </Button>
                      </div>
                    </div>
                  </Card>
                </motion.div>
              ))}
            </div>
          )}
        </AnimatePresence>
      </main>

      {/* Edit Target Modal */}
      <Modal
        isOpen={!!editingTarget}
        onClose={() => setEditingTarget(null)}
        title="Выбрать цель правки"
        description="Найдите правильный раздел, статью или пункт в документе"
        size="lg"
      >
        <div className="space-y-6">
          {/* Current instruction */}
          <div>
            <h4 className="font-semibold text-apple-gray-900 dark:text-apple-gray-50 mb-2">
              Инструкция правки:
            </h4>
            <p className="text-apple-gray-700 dark:text-apple-gray-300 bg-apple-gray-50 dark:bg-apple-gray-900 p-4 rounded-xl">
              {editingTarget?.instruction_text}
            </p>
          </div>

          {/* Search */}
          <div>
            <div className="flex gap-2">
              <Input
                placeholder="Поиск по статьям, пунктам..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              />
              <Button
                variant="primary"
                icon={<Search />}
                onClick={handleSearch}
                isLoading={isSearching}
              >
                Найти
              </Button>
            </div>
          </div>

          {/* Search Results */}
          {searchResults.length > 0 && (
            <div className="space-y-2 max-h-96 overflow-y-auto scrollbar-apple">
              {searchResults.map((result) => (
                <motion.button
                  key={result.tax_unit_id}
                  whileHover={{ x: 4 }}
                  onClick={() => handleSelectTaxUnit(result.tax_unit_id)}
                  className="w-full text-left p-4 bg-white border border-apple-gray-200 rounded-xl hover:border-apple-blue hover:bg-apple-blue/5 transition-all"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <p className="font-medium text-apple-gray-900">
                        {result.breadcrumbs_path}
                      </p>
                      <p className="text-sm text-apple-gray-600 mt-1">
                        {result.title}
                      </p>
                    </div>
                    <Check className="w-5 h-5 text-apple-blue opacity-0 group-hover:opacity-100" />
                  </div>
                </motion.button>
              ))}
            </div>
          )}
        </div>
      </Modal>

      {/* Add New Target Modal */}
      <Modal
        isOpen={isAddingTarget}
        onClose={() => {
          setIsAddingTarget(false);
          setNewInstructionText('');
          setNewArticleId(null);
        }}
        title="Добавить новую правку"
        description="Введите текст правки и выберите статью"
        size="lg"
      >
        <div className="space-y-6">
          {/* Instruction text */}
          <div>
            <h4 className="font-semibold text-apple-gray-900 mb-2">
              Текст правки:
            </h4>
            <textarea
              className="w-full p-3 border border-apple-gray-300 rounded-lg focus:border-apple-blue focus:ring-2 focus:ring-apple-blue/20 outline-none resize-none"
              rows={5}
              placeholder="Введите текст правки..."
              value={newInstructionText}
              onChange={(e) => setNewInstructionText(e.target.value)}
            />
          </div>

          {/* Search */}
          <div>
            <div className="flex gap-2">
              <Input
                placeholder="Поиск статьи..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              />
              <Button
                variant="primary"
                icon={<Search />}
                onClick={handleSearch}
                isLoading={isSearching}
              >
                Найти
              </Button>
            </div>
          </div>

          {/* Search Results */}
          {searchResults.length > 0 && (
            <div className="space-y-2 max-h-96 overflow-y-auto scrollbar-apple">
              {searchResults.map((result) => (
                <motion.button
                  key={result.tax_unit_id}
                  whileHover={{ x: 4 }}
                  onClick={() => setNewArticleId(result.tax_unit_id)}
                  className={`w-full text-left p-4 bg-white border rounded-xl transition-all ${
                    newArticleId === result.tax_unit_id
                      ? 'border-apple-blue bg-apple-blue/10'
                      : 'border-apple-gray-200 hover:border-apple-blue hover:bg-apple-blue/5'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <p className="font-medium text-apple-gray-900">
                        {result.breadcrumbs_path}
                      </p>
                      <p className="text-sm text-apple-gray-600 mt-1">
                        {result.title}
                      </p>
                    </div>
                    {newArticleId === result.tax_unit_id && (
                      <Check className="w-5 h-5 text-apple-blue" />
                    )}
                  </div>
                </motion.button>
              ))}
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-2 pt-4">
            <Button
              variant="secondary"
              onClick={() => {
                setIsAddingTarget(false);
                setNewInstructionText('');
                setNewArticleId(null);
              }}
            >
              Отмена
            </Button>
            <Button
              variant="primary"
              onClick={handleAddTarget}
              disabled={!newInstructionText.trim() || !newArticleId}
            >
              Добавить
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};

