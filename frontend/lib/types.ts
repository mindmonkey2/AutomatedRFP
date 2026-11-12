export type JobStatus = "queued" | "processing" | "ready" | "failed";

export interface LibraryDocument {
  id: number;
  filename: string;
  doc_type: string;
  status: JobStatus;
  error: string | null;
  page_count: number | null;
  chunk_count: number;
  empty_pages: number[];
  created_at: string;
}

export interface SavedAnswer {
  chunk_id: number;
  label: string;
  question: string;
  answer: string;
  bid_deleted: boolean;
}

export interface SearchHit {
  chunk_id: number;
  source_type: string;
  source_id: number;
  label: string;
  page: number | null;
  heading: string | null;
  text: string;
  score: number;
}

export interface Project {
  id: number;
  name: string;
  client: string | null;
  sector: string | null;
  contract_value: number | null;
  start_date: string | null;
  end_date: string | null;
  scope: string | null;
  reference_name: string | null;
  reference_contact: string | null;
}

export interface Credential {
  id: number;
  kind: "license" | "bond" | "insurance" | "certification" | "other";
  name: string;
  number: string | null;
  issuer: string | null;
  expires_on: string | null;
  notes: string | null;
  days_to_expiry: number | null;
}

export interface SolicitationFile {
  id: number;
  filename: string;
  kind: "base" | "addendum";
  sequence: number;
  status: JobStatus;
  error: string | null;
  change_summary: string | null;
  created_at: string;
}

export interface Bid {
  id: number;
  title: string;
  agency: string | null;
  due_date: string | null;
  status: string;
  summary: string | null;
  created_at: string;
  files: SolicitationFile[];
}

export interface BidListItem {
  id: number;
  title: string;
  agency: string | null;
  due_date: string | null;
  status: string;
  requirement_count: number;
  answered_count: number;
}

export interface Citation {
  marker: number;
  chunk_id: number | null;
  quote: string;
  verified: boolean;
  label: string;
  page: number | null;
}

export type AnswerStatus =
  | "queued" | "drafting" | "drafted" | "needs_review" | "accepted" | "approved" | "stale" | "failed";

export interface Answer {
  id: number;
  draft_text: string | null;
  final_text: string | null;
  confidence: number | null;
  confidence_reasons: string[];
  unsupported_claims: string[];
  status: AnswerStatus;
  error: string | null;
  assignee: string | null;
  due_date: string | null;
  citations: Citation[];
}

export interface Requirement {
  id: number;
  sequence: number;
  text: string;
  kind: string;
  section: string | null;
  page: number | null;
  source_quote: string | null;
  mandatory: boolean;
  needs_response: boolean;
  page_limit: number | null;
  status: "open" | "drafted" | "met" | "na" | "removed";
  change_type: "added" | "modified" | "removed" | null;
  changed_by_file_id: number | null;
  answer: Answer | null;
}

export interface Readiness {
  ready: boolean;
  issues: string[];
  requirements_total: number;
  response_items: number;
  estimated_pages: number;
  page_limit: number | null;
}
