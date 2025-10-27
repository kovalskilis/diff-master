import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  ArrowLeft, Download, Save, ChevronLeft, 
  ChevronRight, FileText 
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { diffAPI, versionsAPI, exportAPI } from '@/services/api';
import type { DiffItem } from '@/types';
import ReactDiffViewer from 'react-diff-viewer-continued';

export const DiffPage = () => {
  const { workspaceFileId } = useParams<{ workspaceFileId: string }>();
  const navigate = useNavigate();
  const [diffs, setDiffs] = useState<DiffItem[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isCommitting, setIsCommitting] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  useEffect(() => {
    if (workspaceFileId) {
      loadDiffs();
    }
  }, [workspaceFileId]);

  const loadDiffs = async () => {
    try {
      const data = await diffAPI.getByWorkspaceFile(Number(workspaceFileId));
      setDiffs(data);
    } catch (error) {
      console.error('Failed to load diffs:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCommit = async () => {
    const comment = prompt('Комментарий к версии (необязательно):');
    if (comment === null) return; // User cancelled

    setIsCommitting(true);
    try {
      await versionsAPI.commit(Number(workspaceFileId), comment);
      alert('Изменения сохранены!');
      navigate(-1);
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

  return (
    <div className="min-h-screen bg-gradient-to-br from-apple-gray-50 to-white flex flex-col">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-xl border-b border-apple-gray-200 z-30">
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
                <h1 className="text-xl font-semibold text-apple-gray-900">
                  Просмотр изменений
                </h1>
                <p className="text-sm text-apple-gray-600">
                  {diffs.length} изменений
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
        <div className="bg-white border-b border-apple-gray-200">
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
            <span className="text-sm text-apple-gray-600">
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
        {!currentDiff ? (
          <div className="h-full flex items-center justify-center">
            <Card className="text-center p-12">
              <FileText className="w-16 h-16 text-apple-gray-300 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-apple-gray-900 mb-2">
                Нет изменений
              </h3>
              <p className="text-apple-gray-600">
                Правки еще не применены
              </p>
            </Card>
          </div>
        ) : (
          <div className="h-full flex flex-col">
            {/* Breadcrumbs */}
            <div className="bg-white border-b border-apple-gray-200 px-6 py-3">
              <p className="text-sm text-apple-blue">
                {currentDiff.breadcrumbs_path}
              </p>
              {currentDiff.title && (
                <h2 className="font-semibold text-apple-gray-900 mt-1">
                  {currentDiff.title}
                </h2>
              )}
            </div>

            {/* Diff Viewer */}
            <div className="flex-1 overflow-hidden bg-white">
              <ReactDiffViewer
                oldValue={currentDiff.before_text}
                newValue={currentDiff.after_text}
                splitView={true}
                leftTitle="Было"
                rightTitle="Стало"
                hideLineNumbers={false}
                showDiffOnly={false}
                useDarkTheme={false}
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

