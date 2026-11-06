// HTTP contract — keep in sync with app/api_models.py.

export interface Health {
  online: boolean;
  model_count: number;
}

export interface Models {
  supported: string[];
  installed: string[];
  catalogue?: ModelInfo[];
}

export interface ModelInfo {
  id: string; installed: boolean; availability: string;
  recommended_use: string; tools: boolean | null;
  structured_output: boolean | null; resources: string;
}

export interface PullResponse {
  ok: boolean;
  message: string;
}

export interface CountResponse {
  count: number;
}

export interface IngestResponse {
  chunks_added: number;
  detail: string;
}

export interface IngestionJob {
  id: string; state: 'pending' | 'running' | 'completed' | 'failed';
  attempts?: number; result?: { chunks_added?: number }; error?: string;
}

export interface KBSource {
  source: string;
  chunks: number;
  type: string;
}

export interface SourcesResponse {
  sources: KBSource[];
}

export type ChatMode = "langchain" | "langgraph";

export interface Source {
  source: string;
  page: number | string;
}

export type QuestionType = "mcq" | "true_false" | "short_answer" | "mixed";
export type Difficulty = "easy" | "medium" | "hard" | "mixed";

export interface QuizQuestion {
  drawing_required?: boolean;
  drawing_prompt?: string;
  type: QuestionType;
  question: string;
  options?: Record<string, string>;
  correct?: string;
  sample_answer?: string;
  explanation?: string;
  source?: string;
  difficulty?: string;
}

export interface ValidationResult {
  score: number;
  is_correct: boolean;
  feedback: string;
  key_missed: string[];
  hint: string;
}

// SSE event frames emitted by streaming endpoints.
export type StreamEvent =
  | { type: 'progress'; status: string; completed: number; total: number }
  | { type: "token"; text: string }
  | { type: "sources"; sources: Source[] }
  | { type: "tool"; name: string }
  | { type: "questions"; questions: QuizQuestion[] }
  | { type: "error"; message: string }
  | { type: "done" };

export interface Flashcard {
  id: string;
  front: string;
  back: string;
  created_at: number;
}

export interface Deck {
  id: string;
  name: string;
  created_at: number;
  cards: Flashcard[];
}

export interface DeckSummary {
  id: string;
  name: string;
  card_count: number;
  created_at: number;
}

export interface ChatMessage {
  questions?: QuizQuestion[];
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  tools?: string[];
  model?: string;
  streaming?: boolean;
  error?: boolean;
}
export interface PromptProfile {
  discipline?: string;
  level?: 'beginner' | 'intermediate' | 'advanced';
  objectives?: string[];
  language?: string;
  notation?: string;
  exam_context?: string;
}
