export type UserRole = "learner" | "admin" | "super_admin";
export type UserStatus = "active" | "deactivated";
export type FlashcardDifficulty = "hard" | "medium" | "easy";
export type FlashcardSetStatus = "processing" | "failed" | "active" | "done";
export type FlashcardSetSource = "manual" | "ai_list";
export type AssignmentSource = "manual" | "ai_text" | "ai_pdf";
export type AssignmentStatus = "processing" | "ready" | "failed" | "completed";
export type KoreanLevel = "beginner" | "intermediate" | "advanced";
export type QuestionType = "multiple_choice" | "fill_blank" | "short_answer";
export type ExtractionStatus = "pending" | "processing" | "ready" | "failed";
export type ExtractionMethod = "text" | "pymupdf4llm" | "ocrmypdf+pymupdf4llm";

export interface User {
  id: string;
  discord_id: string;
  email: string | null;
  username: string;
  avatar_url: string | null;
  discord_profile_snapshot: Record<string, unknown> | null;
  last_login_at: string | null;
  role: UserRole;
  status: UserStatus;
  created_at: string;
  updated_at: string;
}

export interface ProfileSummary {
  user: User;
  words_learned: number;
  assignments_completed: number;
  flashcard_count: number;
  flashcard_set_count: number;
  done_set_count: number;
  assignments_generated: number;
  assignments_manual: number;
}

export interface FlashcardGenerationFailure {
  stage: "generation";
  message: string;
  occurred_at: string;
}

export interface FlashcardSet {
  id: string;
  owner_id: string;
  source: FlashcardSetSource;
  name: string;
  description: string | null;
  tags: string[];
  status: FlashcardSetStatus;
  source_text: string | null;
  generation_error: string | null;
  generation_failed_at: string | null;
  generation_failures: FlashcardGenerationFailure[];
  created_at: string;
  updated_at: string;
}

export interface Flashcard {
  id: string;
  owner_id: string;
  set_id: string;
  korean: string;
  english: string;
  notes: string | null;
  example: string | null;
  difficulty: FlashcardDifficulty;
  tags: string[];
  starred: boolean;
  correct_reviews: number;
  incorrect_reviews: number;
  last_reviewed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface StudySession {
  flashcards: Flashcard[];
  set_status: FlashcardSetStatus;
}

export interface AssignmentQuestion {
  id: string;
  type: QuestionType;
  prompt: string;
  options: string[];
  correct_answer: string;
  accepted_answers: string[];
  explanation: string | null;
}

export interface GradedAnswer {
  question_id: string;
  answer: string;
  expected_answer: string;
  is_correct: boolean;
  score: number;
  feedback: string;
}

export interface AssignmentAttempt {
  id: string;
  assignment_id: string;
  owner_id: string;
  answers: { question_id: string; answer: string }[];
  graded_answers: GradedAnswer[];
  score: number;
  feedback: string;
  completed_at: string;
  created_at: string;
}

export interface AssignmentSourceFile {
  id: string;
  filename: string;
  size_bytes: number;
  content_type: string;
  sha256: string;
}

export interface AssignmentGenerationFailure {
  stage: "extraction" | "generation";
  message: string;
  occurred_at: string;
}

export interface Assignment {
  id: string;
  owner_id: string;
  source: AssignmentSource;
  title: string;
  instructions: string | null;
  target_level: KoreanLevel;
  status: AssignmentStatus;
  source_text: string | null;
  study_context: string | null;
  source_file: AssignmentSourceFile | null;
  source_extraction_status: ExtractionStatus;
  source_extraction_method: ExtractionMethod | null;
  source_markdown: string | null;
  source_extraction_summary: Record<string, unknown> | null;
  generation_error: string | null;
  generation_failed_at: string | null;
  generation_failures: AssignmentGenerationFailure[];
  completed_at: string | null;
  questions: AssignmentQuestion[];
  created_at: string;
  updated_at: string;
  latest_attempt: AssignmentAttempt | null;
  attempts: AssignmentAttempt[];
}

export interface AdminUserDetail {
  user: User;
  flashcard_sets: FlashcardSet[];
  flashcards: Flashcard[];
  assignments: Assignment[];
}
