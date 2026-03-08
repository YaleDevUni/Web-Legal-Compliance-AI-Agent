export type ComplianceStatus = 'compliant' | 'violation' | 'unverifiable';

export interface Citation {
  article_id: string;
  law_name: string;
  article_number: string;
  sha256: string;
  url: string;
  updated_at: string;
  article_content?: string;
}

export interface SourceLocation {
  line_start: number;
  line_end: number;
  snippet: string;
}

export interface ComplianceReport {
  status: ComplianceStatus;
  description: string;
  citations: Citation[];
  recommendation?: string;
  source_location?: SourceLocation;
}

export interface AnalyzeRequest {
  code_text: string;
  url?: string;
}
