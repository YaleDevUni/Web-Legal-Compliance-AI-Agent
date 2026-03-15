export interface Citation {
  article_id: string;
  law_name: string;
  article_number: string;
  sha256: string;
  url: string;
  updated_at: string;
  article_content?: string;
  // 판례 필드
  case_number?: string;
  court?: string;
  decision_date?: string;
}

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[]; // 해당 메시지에서 인용된 목록
}

export interface ChatRequest {
  question: string;
  session_id?: string;
}

export interface ChatContentEvent {
  text: string;
}

export interface ChatCitationsEvent {
  citations: Citation[];
  related_citations?: Citation[];
  related_articles: string[];
  session_id: string;
}
