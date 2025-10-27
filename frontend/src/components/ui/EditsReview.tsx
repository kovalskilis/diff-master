import React, { useState } from 'react';
import { Card } from './Card';
import { Button } from './Button';

interface EditsReviewProps {
  articles: Record<string, string>;
  onApprove: (articles: Record<string, string>) => void;
  onCancel: () => void;
  filename: string;
  totalArticles: number;
  hasUnknown: boolean;
}

interface ArticleEditProps {
  articleNum: string;
  content: string;
  onEdit: (content: string) => void;
}

const ArticleEdit: React.FC<ArticleEditProps> = ({ articleNum, content, onEdit }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editedContent, setEditedContent] = useState(content);

  const handleSave = () => {
    onEdit(editedContent);
    setIsEditing(false);
  };

  const handleCancel = () => {
    setEditedContent(content);
    setIsEditing(false);
  };

  // Parse content to highlight changes like PyCharm
  const parseContent = (text: string) => {
    const lines = text.split('\n');
    const parsedLines = lines.map((line, index) => {
      // Highlight article headers
      if (line.match(/^Статья\s+\d+/)) {
        return (
          <div key={index} className="font-bold text-blue-600 bg-blue-50 px-2 py-1 rounded">
            {line}
          </div>
        );
      }
      
      // Highlight numbered items (edits)
      if (line.match(/^\d+[\)\.]\s*/)) {
        return (
          <div key={index} className="ml-4 border-l-2 border-green-400 pl-3 py-1 bg-green-50">
            <span className="font-semibold text-green-700">{line.match(/^\d+[\)\.]\s*/)?.[0]}</span>
            <span className="text-gray-800">{line.replace(/^\d+[\)\.]\s*/, '')}</span>
          </div>
        );
      }
      
      // Highlight sub-items (а), б), etc.)
      if (line.match(/^[а-я]\)\s*/)) {
        return (
          <div key={index} className="ml-8 border-l-2 border-yellow-400 pl-3 py-1 bg-yellow-50">
            <span className="font-semibold text-yellow-700">{line.match(/^[а-я]\)\s*/)?.[0]}</span>
            <span className="text-gray-800">{line.replace(/^[а-я]\)\s*/, '')}</span>
          </div>
        );
      }
      
      // Highlight action words
      const actionWords = ['изложить', 'дополнить', 'исключить', 'заменить', 'внести', 'исключить'];
      const hasAction = actionWords.some(word => line.toLowerCase().includes(word));
      
      if (hasAction) {
        return (
          <div key={index} className="ml-4 pl-3 py-1 bg-orange-50 border-l-2 border-orange-400">
            <span className="text-orange-800">{line}</span>
          </div>
        );
      }
      
      // Regular text
      return (
        <div key={index} className="ml-4 pl-3 py-1 text-gray-700">
          {line}
        </div>
      );
    });
    
    return parsedLines;
  };

  return (
    <Card className="p-4 mb-4">
      <div className="flex justify-between items-center mb-3">
        <h3 className="text-lg font-semibold text-gray-800">
          {articleNum === 'unknown' ? 'Неизвестные правки' : `Статья ${articleNum}`}
        </h3>
        <div className="flex gap-2">
          {!isEditing ? (
            <Button
              onClick={() => setIsEditing(true)}
              variant="outline"
              size="sm"
            >
              Редактировать
            </Button>
          ) : (
            <>
              <Button
                onClick={handleSave}
                variant="default"
                size="sm"
              >
                Сохранить
              </Button>
              <Button
                onClick={handleCancel}
                variant="outline"
                size="sm"
              >
                Отмена
              </Button>
            </>
          )}
        </div>
      </div>
      
      {isEditing ? (
        <textarea
          value={editedContent}
          onChange={(e) => setEditedContent(e.target.value)}
          className="w-full h-64 p-3 border border-gray-300 rounded-md font-mono text-sm"
          placeholder="Введите содержимое статьи..."
        />
      ) : (
        <div className="bg-gray-50 rounded-md p-3 font-mono text-sm">
          {parseContent(content)}
        </div>
      )}
    </Card>
  );
};

export const EditsReview: React.FC<EditsReviewProps> = ({
  articles,
  onApprove,
  onCancel,
  filename,
  totalArticles,
  hasUnknown
}) => {
  const [editedArticles, setEditedArticles] = useState<Record<string, string>>(articles);

  const handleArticleEdit = (articleNum: string, content: string) => {
    setEditedArticles(prev => ({
      ...prev,
      [articleNum]: content
    }));
  };

  const handleApprove = () => {
    onApprove(editedArticles);
  };

  const sortedArticles = Object.entries(editedArticles).sort(([a], [b]) => {
    if (a === 'unknown') return 1;
    if (b === 'unknown') return -1;
    return a.localeCompare(b, undefined, { numeric: true });
  });

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-800 mb-2">
          Обзор правок
        </h2>
        <div className="text-gray-600 space-y-1">
          <p><strong>Файл:</strong> {filename}</p>
          <p><strong>Найдено статей:</strong> {totalArticles}</p>
          {hasUnknown && <p className="text-orange-600"><strong>Внимание:</strong> Есть правки без указания статьи</p>}
        </div>
      </div>

      <div className="space-y-4">
        {sortedArticles.map(([articleNum, content]) => (
          <ArticleEdit
            key={articleNum}
            articleNum={articleNum}
            content={content}
            onEdit={(newContent) => handleArticleEdit(articleNum, newContent)}
          />
        ))}
      </div>

      <div className="flex justify-end gap-4 mt-8 pt-6 border-t border-gray-200">
        <Button
          onClick={onCancel}
          variant="outline"
        >
          Отмена
        </Button>
        <Button
          onClick={handleApprove}
          variant="default"
          className="bg-green-600 hover:bg-green-700"
        >
          Подтвердить и отправить на обработку
        </Button>
      </div>
    </div>
  );
};



