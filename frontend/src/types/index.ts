export interface User {
  id: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
}

export interface Document {
  id: number;
  name: string;
  source_type: string;
  imported_at: string;
  structure?: Record<string, { title: string; content: string }>;
}

export interface TaxUnit {
  id: number;
  type: 'section' | 'chapter' | 'article' | 'clause' | 'sub_clause';
  title: string | null;
  breadcrumbs_path: string | null;
  parent_id: number | null;
  current_text?: string;
}

export interface TaxUnitHierarchy extends TaxUnit {
  children: TaxUnitHierarchy[];
}

export interface WorkspaceFile {
  id: number;
  base_document_id: number | null;
  source_type: string;
  filename: string | null;
  created_at: string;
}

export interface EditTarget {
  id: number;
  workspace_file_id: number;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'review';
  instruction_text: string;
  article_number?: string;
  article_id: number | null;
  conflicts_json: Record<string, any> | null;
  article_title?: string;
  base_document_id?: number | null;
  confirmed_tax_unit_breadcrumbs?: string | null;
  // Whether the referenced article exists in the current document
  article_exists?: boolean;
}

export interface DiffItem {
  tax_unit_id: number;
  title: string | null;
  breadcrumbs_path: string | null;
  before_text: string;
  after_text: string;
  change_type: 'added' | 'modified' | 'deleted';
  diff_html?: string;
}

export interface Snapshot {
  id: number;
  base_document_id: number;
  created_at: string;
  comment: string | null;
}

export interface TaskStatus {
  task_id: string;
  status: string;
  result?: any;
  error?: string;
}

export interface SearchResult {
  tax_unit_id: number;
  title: string | null;
  breadcrumbs_path: string | null;
  text_snippet: string;
  rank: number;
}

// Search results for articles endpoint (/api/search/articles)
export interface ArticleSearchResult {
  article_id: number;
  title: string | null;
  article_number: string | null;
  text_snippet: string;
  rank: number;
}

