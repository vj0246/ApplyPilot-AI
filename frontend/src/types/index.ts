export interface User {
  id: string;
  email: string;
  full_name: string;
  created_at: string;
}

export interface KnowledgeGraph {
  identity?: string;
  values?: string[];
  strengths?: string[];
  motivations?: string[];
  work_style?: string[];
  achievements?: { title: string; summary: string }[];
  goals?: string[];
  communication_style?: string;
}

export interface Profile {
  id: string;
  user_id: string;
  phone?: string;
  location?: string;
  linkedin_url?: string;
  github_url?: string;
  portfolio_url?: string;
  target_roles: string[];
  experience_level?: string;
  work_types: string[];
  salary_min?: number;
  salary_max?: number;
  tone_preference: string;
  skills: string[];
  onboarding_done: boolean;
  knowledge_graph?: KnowledgeGraph;
  email_account_configured?: boolean;
  sender_email?: string;
  updated_at?: string;
}

export type EmailSendStatus = "draft" | "sent" | "failed";

export interface EmailSend {
  id: string;
  status: EmailSendStatus;
  recipient_email: string;
  subject: string;
  body: string;
  error?: string;
  sent_at?: string;
  created_at: string;
}

export interface Resume {
  id: string;
  filename: string;
  label?: string;
  status: "processing" | "ready" | "failed";
  ats_score?: number;
  is_primary: boolean;
  file_size: number;
  mime_type: string;
  parsed_data?: Record<string, unknown>;
  error_msg?: string;
  created_at: string;
}

export interface Job {
  id: string;
  source: string;
  url?: string;
  title?: string;
  company?: string;
  location?: string;
  work_type?: string;
  salary_min?: number;
  salary_max?: number;
  salary_currency?: string;
  required_skills: string[];
  keywords: string[];
  status: "processing" | "ready" | "failed";
  parsed_data?: Record<string, unknown>;
  error_msg?: string;
  created_at: string;
}

export interface FitBreakdown {
  overall: number;
  skills_match: number;
  experience_match: number;
  matched_skills: string[];
  missing_required: string[];
}

export interface Answer {
  question: string;
  answer: string;
}

export type AppStatus =
  | "generating" | "ready" | "approved"
  | "submitted" | "screening" | "interviewing"
  | "offered" | "rejected" | "withdrew" | "failed";

export interface Application {
  id: string;
  status: AppStatus;
  fit_score?: number;
  fit_breakdown?: FitBreakdown;
  skill_gaps?: { skill: string; type: string }[];
  strategy?: string;
  cover_letter?: string;
  email_subject?: string;
  email_body?: string;
  resume_adapted?: string;
  answers?: Answer[];
  user_notes?: string;
  error_msg?: string;
  submitted_at?: string;
  created_at: string;
  updated_at: string;
  job?: Job;
}
