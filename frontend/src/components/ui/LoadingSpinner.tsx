import { motion } from 'framer-motion';

export const LoadingSpinner = ({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) => {
  const sizes = {
    sm: 'w-4 h-4',
    md: 'w-8 h-8',
    lg: 'w-12 h-12',
  };

  return (
    <div className="flex items-center justify-center">
      <motion.div
        className={`${sizes[size]} border-3 border-apple-blue border-t-transparent rounded-full`}
        animate={{ rotate: 360 }}
        transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
      />
    </div>
  );
};

export const LoadingOverlay = ({ message }: { message?: string }) => {
  return (
    <div className="fixed inset-0 bg-white/80 backdrop-blur-sm z-50 flex items-center justify-center">
      <div className="text-center">
        <LoadingSpinner size="lg" />
        {message && (
          <p className="mt-4 text-apple-gray-700 font-medium">{message}</p>
        )}
      </div>
    </div>
  );
};

export const SkeletonCard = () => {
  return (
    <div className="card-apple animate-pulse">
      <div className="h-6 bg-apple-gray-200 rounded w-3/4 mb-4" />
      <div className="h-4 bg-apple-gray-100 rounded w-full mb-2" />
      <div className="h-4 bg-apple-gray-100 rounded w-5/6" />
    </div>
  );
};

