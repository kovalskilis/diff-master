import { Moon, Sun } from 'lucide-react';
import { Button } from './Button';
import { useThemeStore } from '@/hooks/useTheme';

export const ThemeToggle = () => {
  const { theme, toggleTheme } = useThemeStore();
  
  return (
    <Button
      variant="ghost"
      onClick={toggleTheme}
      className="p-2"
      title={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
    >
      {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
    </Button>
  );
};

