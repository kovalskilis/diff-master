import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, ChevronRight, FileText, BookOpen } from 'lucide-react';
import { cn } from '@/utils/cn';

interface Article {
  title: string;
  content: string;
}

interface DocumentStructureProps {
  structure: Record<string, Article>;
  className?: string;
}

export const DocumentStructure = ({ structure, className }: DocumentStructureProps) => {
  const [expandedArticles, setExpandedArticles] = useState<Set<string>>(new Set());
  const [selectedArticle, setSelectedArticle] = useState<string | null>(null);

  const articles = Object.entries(structure).sort(([a], [b]) => {
    // Sort articles numerically (1, 2, 10 instead of 1, 10, 2)
    const aNum = parseFloat(a);
    const bNum = parseFloat(b);
    return aNum - bNum;
  });

  const toggleArticle = (articleNumber: string) => {
    setExpandedArticles(prev => {
      const newSet = new Set(prev);
      if (newSet.has(articleNumber)) {
        newSet.delete(articleNumber);
      } else {
        newSet.add(articleNumber);
      }
      return newSet;
    });
  };

  const selectArticle = (articleNumber: string) => {
    setSelectedArticle(articleNumber);
  };

  if (!articles.length) {
    return (
      <div className={cn("text-center py-8 text-apple-gray-500", className)}>
        <BookOpen className="w-12 h-12 mx-auto mb-4 text-apple-gray-300" />
        <p>Структура документа не найдена</p>
      </div>
    );
  }

  return (
    <div className={cn("space-y-4", className)}>
      <div className="flex items-center gap-2 mb-4">
        <FileText className="w-5 h-5 text-apple-blue" />
        <h3 className="text-lg font-semibold text-apple-gray-900">
          Структура документа ({articles.length} статей)
        </h3>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Articles List */}
        <div className="space-y-2">
          {articles.map(([articleNumber, article]) => (
            <motion.div
              key={articleNumber}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="border border-apple-gray-200 rounded-lg overflow-hidden"
            >
              <button
                onClick={() => toggleArticle(articleNumber)}
                className={cn(
                  "w-full px-4 py-3 text-left flex items-center justify-between hover:bg-apple-gray-50 transition-colors",
                  selectedArticle === articleNumber && "bg-apple-blue/5 border-apple-blue"
                )}
              >
                <div className="flex items-center gap-3">
                  {expandedArticles.has(articleNumber) ? (
                    <ChevronDown className="w-4 h-4 text-apple-gray-400" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-apple-gray-400" />
                  )}
                  <span className="font-medium text-apple-gray-900">
                    Статья {articleNumber}
                  </span>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    selectArticle(articleNumber);
                  }}
                  className="px-3 py-1 text-sm bg-apple-blue text-white rounded-md hover:bg-apple-blue/90 transition-colors"
                >
                  Показать
                </button>
              </button>

              <AnimatePresence>
                {expandedArticles.has(articleNumber) && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="border-t border-apple-gray-200"
                  >
                    <div className="p-4 bg-apple-gray-50">
                      <h4 className="font-medium text-apple-gray-900 mb-2">
                        {article.title}
                      </h4>
                      <p className="text-sm text-apple-gray-600 line-clamp-3">
                        {article.content.substring(0, 200)}
                        {article.content.length > 200 && '...'}
                      </p>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ))}
        </div>

        {/* Selected Article Content */}
        {selectedArticle && structure[selectedArticle] && (
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="border border-apple-gray-200 rounded-lg p-6 bg-white"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-apple-gray-900">
                Статья {selectedArticle}
              </h3>
              <button
                onClick={() => setSelectedArticle(null)}
                className="text-apple-gray-400 hover:text-apple-gray-600"
              >
                ×
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <h4 className="font-medium text-apple-gray-900 mb-2">
                  {structure[selectedArticle].title}
                </h4>
                <div className="prose prose-sm max-w-none text-apple-gray-700 whitespace-pre-wrap">
                  {structure[selectedArticle].content}
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
};



