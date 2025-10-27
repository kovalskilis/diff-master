import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Trash2, Loader2, CheckCircle } from 'lucide-react';

interface DeletingWidgetProps {
  documentName: string;
  onComplete?: () => void;
}

export const DeletingWidget: React.FC<DeletingWidgetProps> = ({ documentName, onComplete }) => {
  const [isCompleted, setIsCompleted] = useState(false);

  // Функция для завершения
  const completeProgress = () => {
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
            {isCompleted ? 'Документ удален' : 'Удаление документа...'}
          </h3>
          <p className={`text-sm truncate ${
            isCompleted ? 'text-green-700' : 'text-red-700'
          }`}>
            {documentName}
          </p>
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
