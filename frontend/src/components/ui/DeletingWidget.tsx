import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Trash2, Loader2, CheckCircle } from 'lucide-react';

interface DeletingWidgetProps {
  documentName: string;
  onComplete?: () => void;
}

export const DeletingWidget: React.FC<DeletingWidgetProps> = ({ documentName, onComplete }) => {
  const [progress, setProgress] = useState(0);
  const [isCompleted, setIsCompleted] = useState(false);

  useEffect(() => {
    // Более реалистичный прогресс-бар
    const interval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 90) {
          // Останавливаемся на 90% и ждем реального завершения
          return prev;
        }
        // Медленное увеличение с замедлением
        const increment = Math.max(0.5, Math.random() * 2);
        return Math.min(prev + increment, 90);
      });
    }, 300);

    return () => clearInterval(interval);
  }, []);

  // Функция для завершения прогресса
  const completeProgress = () => {
    setProgress(100);
    setIsCompleted(true);
    setTimeout(() => {
      onComplete?.();
    }, 500);
  };

  // Экспонируем функцию завершения через ref или callback
  useEffect(() => {
    if (onComplete) {
      // Если передан onComplete, завершаем через 3 секунды (примерное время удаления)
      const timer = setTimeout(completeProgress, 3000);
      return () => clearTimeout(timer);
    }
  }, [onComplete]);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      className={`border rounded-lg p-4 shadow-lg transition-colors ${
        isCompleted 
          ? 'bg-green-50 border-green-200' 
          : 'bg-red-50 border-red-200'
      }`}
    >
      <div className="flex items-center space-x-3">
        <div className="flex-shrink-0">
          <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
            isCompleted ? 'bg-green-100' : 'bg-red-100'
          }`}>
            {isCompleted ? (
              <CheckCircle className="w-4 h-4 text-green-600" />
            ) : (
              <Loader2 className="w-4 h-4 text-red-600 animate-spin" />
            )}
          </div>
        </div>
        <div className="flex-1 min-w-0">
          <h3 className={`text-sm font-medium ${
            isCompleted ? 'text-green-900' : 'text-red-900'
          }`}>
            {isCompleted ? 'Документ удален' : 'Удаление документа'}
          </h3>
          <p className={`text-sm truncate ${
            isCompleted ? 'text-green-700' : 'text-red-700'
          }`}>
            {documentName}
          </p>
          <div className="mt-2">
            <div className={`w-full rounded-full h-1.5 ${
              isCompleted ? 'bg-green-200' : 'bg-red-200'
            }`}>
              <motion.div
                className={`h-1.5 rounded-full ${
                  isCompleted ? 'bg-green-500' : 'bg-red-500'
                }`}
                style={{ width: `${progress}%` }}
                transition={{ duration: 0.3, ease: "easeOut" }}
              />
            </div>
            <div className={`mt-1 text-xs text-center ${
              isCompleted ? 'text-green-600' : 'text-red-600'
            }`}>
              {isCompleted ? 'Готово!' : `${Math.round(progress)}%`}
            </div>
          </div>
        </div>
        <div className="flex-shrink-0">
          {isCompleted ? (
            <CheckCircle className="w-5 h-5 text-green-500" />
          ) : (
            <Trash2 className="w-5 h-5 text-red-500" />
          )}
        </div>
      </div>
    </motion.div>
  );
};
