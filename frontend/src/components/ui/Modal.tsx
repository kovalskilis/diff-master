import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';
import { cn } from '@/utils/cn';
import type { ReactNode } from 'react';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  children: ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
}

export const Modal = ({ 
  isOpen, 
  onClose, 
  title, 
  description, 
  children, 
  size = 'md' 
}: ModalProps) => {
  const sizes = {
    sm: 'max-w-md',
    md: 'max-w-2xl',
    lg: 'max-w-4xl',
    xl: 'max-w-6xl',
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40"
          />
          
          {/* Modal */}
          <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            onClick={onClose}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              transition={{ type: 'spring', duration: 0.3 }}
              onClick={(e) => e.stopPropagation()}
              className={cn(
                'bg-white dark:bg-apple-gray-800 rounded-3xl shadow-apple-lg w-full',
                'max-h-[90vh] overflow-hidden flex flex-col',
                sizes[size]
              )}
            >
              {/* Header */}
              {(title || description) && (
                <div className="px-8 pt-8 pb-6 border-b border-apple-gray-100 dark:border-apple-gray-700">
                  <div className="flex items-start justify-between">
                    <div>
                      {title && (
                        <h2 className="text-2xl font-semibold text-apple-gray-900 dark:text-apple-gray-50">
                          {title}
                        </h2>
                      )}
                      {description && (
                        <p className="mt-1 text-sm text-apple-gray-600 dark:text-apple-gray-400">
                          {description}
                        </p>
                      )}
                    </div>
                    <button
                      onClick={onClose}
                      className="p-2 rounded-full hover:bg-apple-gray-100 dark:hover:bg-apple-gray-700 transition-colors"
                    >
                      <X className="w-5 h-5 text-apple-gray-500 dark:text-apple-gray-400" />
                    </button>
                  </div>
                </div>
              )}
              
              {/* Content */}
              <div className="px-8 py-6 overflow-y-auto scrollbar-apple flex-1">
                {children}
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
};

