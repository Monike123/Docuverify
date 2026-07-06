import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 300000, // 5 min — OCR on cold start can take 20-30s, pre-warmed ~3-8s
});

// Add API key to requests if configured
api.interceptors.request.use((config) => {
  const apiKey = localStorage.getItem('docverify_api_key');
  if (apiKey) {
    config.headers['X-Api-Key'] = apiKey;
  }
  return config;
});

// ── Types ──
export interface ScoreBreakdown {
  ocr_quality: number;
  field_completeness: number;
  validation: number;
  image_quality: number;
  overall: number;
}

export interface DocumentResult {
  doc_id: string;
  doc_type: string;
  status: string;
  confidence_score: number | null;
  flags: string[];
  extracted_fields: Record<string, any>;
  text_source: string | null;
  verification_status: string | null;
  masked_image_path: string | null;
  created_at: string | null;
  score_breakdown: ScoreBreakdown | null;
  full_text: string | null;
  ocr_confidence: number | null;
  reviewer_notes: string | null;
  reviewed_by: string | null;
  original_filename: string | null;
  // AI / Gemini fields
  ai_powered?: boolean;
  forgery_score?: number;
  forgery_reason?: string;
}

export interface AnalyzeResult extends DocumentResult {}


export interface DashboardStats {
  total: number;
  verified: number;
  pending_review: number;
  rejected: number;
  pending: number;
  avg_confidence: number;
  avg_ocr_accuracy: number;
  by_doc_type: Record<string, number>;
  recent_uploads: DocumentResult[];
}

// ── API Functions ──

export async function healthCheck() {
  const { data } = await api.get('/health');
  return data;
}

export async function uploadDocument(file: File, docType: string) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('doc_type', docType);
  const { data } = await api.post('/upload', formData);
  return data as { doc_id: string; doc_type: string };
}

export async function analyzeDocument(docId: string) {
  const { data } = await api.post<AnalyzeResult>(`/analyze/${docId}`);
  return data;
}

export async function getDocumentStatus(docId: string) {
  const { data } = await api.get<DocumentResult>(`/status/${docId}`);
  return data;
}

export async function listDocuments() {
  const { data } = await api.get<DocumentResult[]>('/documents');
  return data;
}

export async function getQueue() {
  const { data } = await api.get<DocumentResult[]>('/queue');
  return data;
}

export async function getDashboardStats() {
  const { data } = await api.get<DashboardStats>('/documents/stats');
  return data;
}

export async function manualReview(docId: string, action: string, notes?: string, reviewerName?: string, editedFields?: Record<string, any>) {
  const { data } = await api.post<DocumentResult>(`/manual-review/${docId}`, {
    action,
    notes,
    reviewer_name: reviewerName,
    edited_fields: editedFields,
  });
  return data;
}

export async function verifyExperience(docId: string) {
  const { data } = await api.post(`/verify-experience/${docId}`);
  return data;
}

export async function govVerify(docId: string) {
  const { data } = await api.post(`/gov-verify/${docId}`);
  return data;
}

export function getOriginalUrl(docId: string) {
  return `${API_BASE}/original/${docId}`;
}

export function getMaskedUrl(docId: string) {
  return `${API_BASE}/masked/${docId}`;
}

export function getDownloadTextUrl(docId: string) {
  return `${API_BASE}/download/text/${docId}`;
}

export function getDownloadJsonUrl(docId: string) {
  return `${API_BASE}/download/json/${docId}`;
}

export function getDownloadMaskedUrl(docId: string) {
  return `${API_BASE}/download/masked/${docId}`;
}

export async function getImageBase64(docId: string) {
  const { data } = await api.get(`/image-base64/${docId}`);
  return data as { doc_id: string; image_base64: string | null; masked_image_base64: string | null };
}

export default api;
