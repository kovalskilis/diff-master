import axios from 'axios';
import type {
  User,
  Document,
  TaxUnitHierarchy,
  WorkspaceFile,
  EditTarget,
  DiffItem,
  Snapshot,
  TaskStatus,
  SearchResult,
  ArticleSearchResult,
} from '@/types';

// Single source of truth for API base URL
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Auth token interceptor removed - authentication disabled

// Normalize error responses to human-readable messages
api.interceptors.response.use(
  (res) => res,
  (error) => {
    // 401 handling removed - authentication disabled
    
    const data = error?.response?.data;
    const msg =
      data?.message ||
      data?.detail ||
      (Array.isArray(data?.errors)
        ? data.errors
            .map((e: any) => (e.field ? `${e.field}: ${e.message}` : e.message))
            .join(', ')
        : null) ||
      'Произошла ошибка запроса';
    error.normalizedMessage = msg;
    return Promise.reject(error);
  }
);

// Auth API removed - authentication disabled
// All auth endpoints are no longer available
export const authAPI = {
  login: async () => {
    throw new Error('Authentication is disabled');
  },
  register: async () => {
    throw new Error('Authentication is disabled');
  },
  requestVerify: async () => {
    throw new Error('Authentication is disabled');
  },
  logout: async () => {
    // No-op
  },
  getMe: async (): Promise<User> => {
    // Return dummy user
    return {
      id: '00000000-0000-0000-0000-000000000001',
      email: 'dummy@example.com',
      is_active: true,
      is_superuser: false,
      is_verified: true,
    };
  },
};

// Documents API
export const documentsAPI = {
  import: async (file: File): Promise<Document> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/api/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  list: async (): Promise<Document[]> => {
    const response = await api.get('/api/documents');
    return response.data;
  },

  get: async (id: number): Promise<Document> => {
    const response = await api.get(`/api/documents/${id}`);
    return response.data;
  },

  getStructure: async (id: number): Promise<TaxUnitHierarchy[]> => {
    const response = await api.get(`/api/documents/${id}/structure`);
    return response.data;
  },

  getArticles: async (id: number): Promise<{ document_id: number; structure: Record<string, { title: string; content: string }> }> => {
    const response = await api.get(`/api/documents/${id}/articles`);
    return response.data;
  },
  extractEdits: async (formData: FormData): Promise<{ filename: string; file_type: string; articles: Record<string, string>; total_articles: number; has_unknown: boolean }> => {
    const response = await api.post('/api/edits/extract', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },
  processApprovedEdits: async (data: { articles: Record<string, string>; document_id: number }): Promise<{ task_id: string; message: string }> => {
    const response = await api.post('/api/edits/process', data);
    return response.data;
  },

  delete: async (id: number) => {
    await api.delete(`/api/documents/${id}`);
  },
};

// Workspace API
export const workspaceAPI = {
  uploadFile: async (documentId: number, file: File): Promise<WorkspaceFile> => {
    const formData = new FormData();
    formData.append('base_document_id', documentId.toString());
    formData.append('file', file);
    const response = await api.post('/api/workspace/file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  uploadText: async (documentId: number, text: string): Promise<WorkspaceFile> => {
    const formData = new FormData();
    formData.append('base_document_id', documentId.toString());
    formData.append('text_content', text);
    const response = await api.post('/api/workspace/file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  list: async (documentId?: number): Promise<WorkspaceFile[]> => {
    const params = documentId ? { base_document_id: documentId } : {};
    const response = await api.get('/api/workspace/files', { params });
    return response.data;
  },

  get: async (id: number): Promise<WorkspaceFile> => {
    const response = await api.get(`/api/workspace/file/${id}`);
    return response.data;
  },

  delete: async (id: number) => {
    await api.delete(`/api/workspace/file/${id}`);
  },
};

// Edits API
export const editsAPI = {
  startPhase1: async (workspaceFileId: number) => {
    const response = await api.post('/api/edits/apply/phase1', {
      workspace_file_id: workspaceFileId,
    });
    return response.data;
  },

  getTargets: async (workspaceFileId: number): Promise<EditTarget[]> => {
    const response = await api.get(`/api/edits/targets/${workspaceFileId}`);
    return response.data;
  },

  // Update target by binding to a specific article
  updateTarget: async (targetId: number, articleId: number): Promise<EditTarget> => {
    const response = await api.put(`/api/edits/target/${targetId}`, {
      article_id: articleId,
    });
    return response.data;
  },

  deleteTarget: async (targetId: number) => {
    await api.delete(`/api/edits/target/${targetId}`);
  },

  createTarget: async (workspaceFileId: number, instructionText: string, articleId: number): Promise<EditTarget> => {
    const response = await api.post(`/api/edits/target`, {
      workspace_file_id: workspaceFileId,
      instruction_text: instructionText,
      article_id: articleId,
    });
    return response.data;
  },

  startPhase2: async (workspaceFileId: number) => {
    const response = await api.post('/api/edits/apply/phase2', {
      workspace_file_id: workspaceFileId,
    });
    return response.data;
  },

  getTaskStatus: async (taskId: string): Promise<TaskStatus> => {
    const response = await api.get(`/api/edits/task/${taskId}`);
    return response.data;
  },
};

// Diff API
export const diffAPI = {
  getByWorkspaceFile: async (workspaceFileId: number): Promise<DiffItem[]> => {
    const response = await api.get('/api/diff', {
      params: { workspace_file_id: workspaceFileId },
    });
    return response.data;
  },

  getBySnapshot: async (snapshotId: number): Promise<DiffItem[]> => {
    const response = await api.get('/api/diff', {
      params: { snapshot_id: snapshotId },
    });
    return response.data;
  },
};

// Versions API
export const versionsAPI = {
  list: async (documentId: number): Promise<Snapshot[]> => {
    const response = await api.get('/api/versions', {
      params: { document_id: documentId },
    });
    return response.data;
  },

  get: async (snapshotId: number): Promise<Snapshot> => {
    const response = await api.get(`/api/versions/${snapshotId}`);
    return response.data;
  },

  commit: async (workspaceFileId: number, comment: string = '') => {
    const response = await api.post('/api/versions/commit', null, {
      params: { workspace_file_id: workspaceFileId, comment },
    });
    return response.data;
  },
};

// Search API
export const searchAPI = {
  search: async (query: string, documentId?: number, limit: number = 20): Promise<SearchResult[]> => {
    const params: any = { q: query, limit };
    if (documentId) params.document_id = documentId;
    const response = await api.get('/api/search', { params });
    return response.data;
  },

  // Autocomplete/search for articles by number/title/content snippet
  searchArticles: async (query: string, documentId: number, limit: number = 50): Promise<ArticleSearchResult[]> => {
    const response = await api.get('/api/search/articles', {
      params: { q: query, document_id: documentId, limit },
    });
    return response.data;
  },
};

// Export API
export const exportAPI = {
  exportText: async (snapshotId: number, format: 'txt' | 'docx') => {
    const response = await api.post(
      '/api/export/text',
      null,
      {
        params: { snapshot_id: snapshotId, format },
        responseType: 'blob',
      }
    );
    return response.data;
  },

  exportExcel: async (snapshotId?: number, workspaceFileId?: number) => {
    const params: any = {};
    if (snapshotId) params.snapshot_id = snapshotId;
    if (workspaceFileId) params.workspace_file_id = workspaceFileId;
    const response = await api.post('/api/export/excel', null, {
      params,
      responseType: 'blob',
    });
    return response.data;
  },
};

export default api;

