const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export type DocumentProfile = {
  document_id: string;
  document_name: string;
  page_count: number;
  heading_count: number;
  table_count: number;
  avg_page_chars: number;
  chunk_counts?: Record<string, number>;
  detected_structure: string;
  recommended_strategy: string;
  recommended_top_k: number;
  reason: string;
};

export type UploadedDocument = {
  document_id: string;
  original_filename: string;
  status: string;
  parsing?: unknown;
  chunking_results?: unknown[];
  embedding_results?: unknown[];
  indexing_results?: unknown[];

  document_profile?: DocumentProfile | null;
  profile_path?: string | null;
  recommended_strategy?: string | null;
  recommended_top_k?: number | null;
};
export type UploadResponse = {
  status: string;
  uploaded_count: number;
  failed_count: number;
  documents: UploadedDocument[];
  errors: unknown[];
};

export type ChatSource = {
  score: number;
  chunk_id: string;
  document_id: string;
  document_name: string;
  strategy: string;
  chunk_type: string;
  section_title?: string | null;
  page_number?: number | null;
  chunk_index: number;
  text: string;

  similarity_score?: number | null;
  rerank_score?: number | null;
  original_rank?: number | null;
};

export type ChatResponse = {
  question: string;
  answer: string;
  strategy: string;
  provider: string;
  document_id?: string | null;
  sources: ChatSource[];
  used_strategy?: string | null;
  used_top_k?: number | null;

  used_reranking?: boolean | null;
  rerank_candidate_limit?: number | null;
};

export type EvaluationQuestionResult = {
  question_id: string;
  question: string;
  expected_answer: string;
  expected_keywords: string[];
  retrieved_text_preview: string;
  matched_keywords: string[];
  missing_keywords: string[];
  keyword_recall: number;
  top_score?: number | null;
  passed: boolean;
};

export type EvaluationStrategyResult = {
  strategy: string;
  questions_evaluated: number;
  average_keyword_recall: number;
  average_top_score?: number | null;
  pass_rate: number;
  overall_score: number;
  strengths: string[];
  weaknesses: string[];
  recommendation: string;
  results: EvaluationQuestionResult[];
};

export type EvaluationResponse = {
  document_id?: string | null;
  limit: number;
  strategies_evaluated: string[];
  best_strategy?: string | null;
  best_strategy_reason?: string | null;
  strategy_results: EvaluationStrategyResult[];
};

export async function uploadDocuments(files: FileList): Promise<UploadResponse> {
  const formData = new FormData();

  Array.from(files).forEach((file) => {
    formData.append("files", file);
  });

  const response = await fetch(`${API_BASE_URL}/documents/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  return response.json();
}

export async function chatWithDocument(params: {
  question: string;
  documentId?: string;
  strategy: string;
  provider: string;
  limit: number;
  rerank?: boolean;
  rerankCandidateLimit?: number;
}): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      question: params.question,
      document_id: params.documentId || null,
      strategy: params.strategy,
      provider: params.provider,
      limit: params.limit,
      rerank: params.rerank,
      rerank_candidate_limit: params.rerankCandidateLimit,
    }),
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  return response.json();
}

export async function runEvaluation(params: {
  documentId?: string;
  strategies: string[];
  limit: number;
}): Promise<EvaluationResponse> {
  const response = await fetch(`${API_BASE_URL}/evaluation/run`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      document_id: params.documentId || null,
      strategies: params.strategies,
      limit: params.limit,
    }),
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  return response.json();
}

export type IndexedDocument = {
  document_id: string;
  document_name: string;
  strategies: string[];
  chunk_count: number;
};

export type ListDocumentsResponse = {
  documents: IndexedDocument[];
};

export async function listDocuments(): Promise<ListDocumentsResponse> {
  const response = await fetch(`${API_BASE_URL}/documents`);

  if (!response.ok) {
    throw new Error(await response.text());
  }

  return response.json();
}