import { motion } from 'framer-motion';
import { cn } from '@/utils/cn';
import type { ButtonHTMLAttributes, ReactNode } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  icon?: ReactNode;
  children: ReactNode;
}

export const Button = ({
  variant = 'primary',
  size = 'md',
  isLoading = false,
  icon,
  children,
  className,
  disabled,
  ...props
}: ButtonProps) => {
  const baseStyles = 'font-medium rounded-xl transition-all duration-200 inline-flex items-center justify-center gap-2';
  
  const variants = {
    primary: 'bg-apple-blue text-white hover:bg-apple-blue-hover shadow-sm hover:shadow-apple disabled:opacity-50',
    secondary: 'bg-apple-gray-100 text-apple-gray-900 hover:bg-apple-gray-200 disabled:opacity-50',
    ghost: 'bg-transparent text-apple-gray-700 hover:bg-apple-gray-50 disabled:opacity-50',
  };
  
  const sizes = {
    sm: 'px-4 py-2 text-sm',
    md: 'px-6 py-3 text-base',
    lg: 'px-8 py-4 text-lg',
  };

  const MotionButton = motion.button as any;
  
  return (
    <MotionButton
      whileTap={{ scale: disabled || isLoading ? 1 : 0.98 }}
      className={cn(
        baseStyles,
        variants[variant],
        sizes[size],
        className
      )}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <div className="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin" />
      ) : icon ? (
        <span className="w-5 h-5">{icon}</span>
      ) : null}
      {children}
    </MotionButton>
  );
};

