import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useThemeStore } from '@/hooks/useTheme';
import { 
  ArrowLeft, Download, Save, ChevronLeft, 
  ChevronRight, FileText, Loader2 
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { diffAPI, versionsAPI, exportAPI, editsAPI } from '@/services/api';
import type { DiffItem } from '@/types';
import ReactDiffViewer from 'react-diff-viewer-continued';

export const DiffPage = () => {
  const { workspaceFileId } = useParams<{ workspaceFileId: string }>();
  const navigate = useNavigate();
  const { theme } = useThemeStore();
  const [diffs, setDiffs] = useState<DiffItem[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isCommitting, setIsCommitting] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [totalTargets, setTotalTargets] = useState<number | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const initialLoadRef = useRef(true);

  useEffect(() => {
    if (workspaceFileId) {
      initializePage();
    }
    
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, [workspaceFileId]);

  const initializePage = async () => {
    try {
      // Get total number of targets to track progress
      const targets = await editsAPI.getTargets(Number(workspaceFileId));
      setTotalTargets(targets.length);
      
      // Load initial diffs
      await loadDiffs();
      
      // If we have targets but no diffs yet, start polling
      if (targets.length > 0 && initialLoadRef.current) {
        initialLoadRef.current = false;
        startPolling();
      }
    } catch (error) {
      console.error('Failed to initialize page:', error);
    }
  };

  const loadDiffs = async (showLoading = true) => {
    try {
      if (showLoading) {
        setIsLoading(true);
      }
      
      const data = await diffAPI.getByWorkspaceFile(Number(workspaceFileId));
      console.log('Loaded diffs:', data);
      
      setDiffs(prevDiffs => {
        const prevCount = prevDiffs.length;
        
        // Stop polling when all diffs are loaded
        if (data.length > prevCount && totalTargets && data.length >= totalTargets) {
          stopPolling();
        }
        
        return data;
      });
    } catch (error) {
      console.error('Failed to load diffs:', error);
    } finally {
      if (showLoading) {
        setIsLoading(false);
      }
    }
  };

  const startPolling = () => {
    if (pollingIntervalRef.current) return;
    
    setIsPolling(true);
    console.log('Starting polling for diffs...');
    
    pollingIntervalRef.current = setInterval(async () => {
      try {
        await loadDiffs(false); // Don't show loading spinner during polling
      } catch (error) {
        console.error('Polling failed:', error);
      }
    }, 2500); // Poll every 2.5 seconds
  };

  const stopPolling = () => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
      setIsPolling(false);
      console.log('Stopped polling for diffs');
    }
  };

  const handleCommit = async () => {
    const comment = prompt('Комментарий к версии (необязательно):');
    if (comment === null) return; // User cancelled

    setIsCommitting(true);
    try {
      await versionsAPI.commit(Number(workspaceFileId), comment);
      alert('Изменения сохранены!');
      // Don't navigate away - let user export the document
    } catch (error) {
      console.error('Failed to commit:', error);
      alert('Ошибка сохранения');
    } finally {
      setIsCommitting(false);
    }
  };

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const blob = await exportAPI.exportExcel(undefined, Number(workspaceFileId));
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `changes_report_${workspaceFileId}.xlsx`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Export failed:', error);
      alert('Ошибка экспорта');
    } finally {
      setIsExporting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  const currentDiff = diffs[currentIndex];
  const isDarkTheme = theme === 'dark';
  
  console.log('Diffs:', diffs, 'currentIndex:', currentIndex, 'currentDiff:', currentDiff);
  
  return (
    <div className="min-h-screen bg-gradient-to-br from-apple-gray-50 to-white dark:from-apple-gray-900 dark:to-apple-gray-800 flex flex-col">
      {/* Header */}
      <header className="bg-white/80 dark:bg-apple-gray-800/80 backdrop-blur-xl border-b border-apple-gray-200 dark:border-apple-gray-700 z-30">
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
                  Просмотр изменений
                </h1>
                <p className="text-sm text-apple-gray-600 dark:text-apple-gray-400 flex items-center gap-2">
                  {diffs.length || 0} из {totalTargets ?? '?'} изменений
                  {isPolling && (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  )}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Button
                variant="secondary"
                icon={<Download />}
                onClick={handleExport}
                isLoading={isExporting}
              >
                Экспорт в Excel
              </Button>
              <Button
                variant="primary"
                icon={<Save />}
                onClick={handleCommit}
                isLoading={isCommitting}
              >
                Зафиксировать версию
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Diff Navigation */}
      {diffs.length > 1 && (
        <div className="bg-white dark:bg-apple-gray-800 border-b border-apple-gray-200 dark:border-apple-gray-700">
          <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
            <Button
              variant="ghost"
              size="sm"
              icon={<ChevronLeft />}
              onClick={() => setCurrentIndex(Math.max(0, currentIndex - 1))}
              disabled={currentIndex === 0}
            >
              Предыдущее
            </Button>
            <span className="text-sm text-apple-gray-600 dark:text-apple-gray-400">
              {currentIndex + 1} из {diffs.length}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setCurrentIndex(Math.min(diffs.length - 1, currentIndex + 1))}
              disabled={currentIndex === diffs.length - 1}
            >
              Следующее
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="flex-1 overflow-hidden">
        {!currentDiff || diffs.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <Card className="text-center p-12">
              <FileText className="w-16 h-16 text-apple-gray-300 dark:text-apple-gray-600 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-apple-gray-900 dark:text-apple-gray-50 mb-2">
                Нет изменений
              </h3>
              <p className="text-apple-gray-600 dark:text-apple-gray-400">
                Правки еще не применены
              </p>
            </Card>
          </div>
        ) : (
          <div className="h-full flex flex-col">
            {/* Breadcrumbs */}
            <div className="bg-white dark:bg-apple-gray-800 border-b border-apple-gray-200 dark:border-apple-gray-700 px-6 py-3">
              <p className="text-sm text-apple-blue">
                {currentDiff.breadcrumbs_path}
              </p>
              {currentDiff.title && (
                <h2 className="font-semibold text-apple-gray-900 dark:text-apple-gray-50 mt-1">
                  {currentDiff.title}
                </h2>
              )}
            </div>

            {/* Diff Viewer */}
            <div className="flex-1 overflow-hidden bg-white dark:bg-apple-gray-900">
              <ReactDiffViewer
                oldValue={currentDiff.before_text}
                newValue={currentDiff.after_text}
                splitView={true}
                leftTitle="Было"
                rightTitle="Стало"
                hideLineNumbers={false}
                showDiffOnly={false}
                useDarkTheme={isDarkTheme}
                styles={{
                  variables: {
                    light: {
                      codeFoldGutterBackground: '#f6f8fa',
                      codeFoldBackground: '#ffffff',
                      addedBackground: '#e6ffed',
                      addedColor: '#24292e',
                      removedBackground: '#ffeef0',
                      removedColor: '#24292e',
                      wordAddedBackground: '#acf2bd',
                      wordRemovedBackground: '#fdb8c0',
                      addedGutterBackground: '#cdffd8',
                      removedGutterBackground: '#fecdd3',
                      gutterBackground: '#fafbfc',
                      gutterBackgroundDark: '#f1f8ff',
                      highlightBackground: '#fffbdd',
                      highlightGutterBackground: '#fff5b1',
                    },
                    dark: {
                      codeFoldGutterBackground: '#1c1c1f',
                      codeFoldBackground: '#2c2c2e',
                      addedBackground: '#1a472a',
                      addedColor: '#d4edda',
                      removedBackground: '#5c1e1e',
                      removedColor: '#f8d7da',
                      wordAddedBackground: '#28a745',
                      wordRemovedBackground: '#dc3545',
                      addedGutterBackground: '#28a745',
                      removedGutterBackground: '#dc3545',
                      gutterBackground: '#1c1c1f',
                      gutterBackgroundDark: '#2c2c2e',
                      highlightBackground: '#5c4f21',
                      highlightGutterBackground: '#6c5a31',
                    }
                  },
                  contentText: {
                    fontSize: '0.875rem',
                    lineHeight: '1.5',
                  },
                  line: {
                    fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                  }
                }}
              />
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

