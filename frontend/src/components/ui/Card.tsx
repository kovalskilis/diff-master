import { motion } from 'framer-motion';
import { cn } from '@/utils/cn';
import type { ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  className?: string;
  hover?: boolean;
  onClick?: () => void;
}

export const Card = ({ children, className, hover = false, onClick }: CardProps) => {
  const Component = onClick ? motion.button : motion.div;
  
  return (
    <Component
      onClick={onClick}
      className={cn(
        'card-apple',
        hover && 'cursor-pointer',
        onClick && 'w-full text-left',
        className
      )}
      whileHover={hover ? { y: -4 } : undefined}
      transition={{ duration: 0.2 }}
    >
      {children}
    </Component>
  );
};

export const CardHeader = ({ children, className }: { children: ReactNode; className?: string }) => (
  <div className={cn('border-b border-apple-gray-100 dark:border-apple-gray-700 pb-4 mb-4', className)}>
    {children}
  </div>
);

export const CardTitle = ({ children, className }: { children: ReactNode; className?: string }) => (
  <h3 className={cn('text-xl font-semibold text-apple-gray-900 dark:text-apple-gray-50', className)}>
    {children}
  </h3>
);

export const CardDescription = ({ children, className }: { children: ReactNode; className?: string }) => (
  <p className={cn('text-sm text-apple-gray-600 dark:text-apple-gray-400 mt-1', className)}>
    {children}
  </p>
);

export const CardContent = ({ children, className }: { children: ReactNode; className?: string }) => (
  <div className={cn('', className)}>
    {children}
  </div>
);

