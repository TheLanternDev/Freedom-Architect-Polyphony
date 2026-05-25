export type AgentStatus = "idle" | "analyzing" | "speaking" | "done" | "error";

export interface AgentState {
  name: string;
  status: AgentStatus;
  text: string;
  /** 0–100 heurystyka z liczby chunków SSE (do paska postępu). */
  progress?: number;
}

export type DebateStatus =
  | "idle"
  | "agents_speaking"
  | "synthesizing"
  | "done"
  | "error";

// ── AKSJOMAT 1: Architektura Marzenia ──────────────────────────────────────

export interface MilestonePayload {
  title: string;
  due?: string | null;
  why_it_matters?: string;
}

export interface NextMovePayload {
  action: string;
  when: string;
  smallest_form?: string;
}

export interface DreamArchitecturePayload {
  dream_id: string;
  core_dream: string;
  value_anchor: string;
  pillars: string[];
  milestones: MilestonePayload[];
  next_move: NextMovePayload;
  completion_criteria: string[];
  functionality_checklist: string[];
}

// ── AKSJOMAT 2: Doprowadzanie Projektów Do Końca ───────────────────────────

export interface FunctionalityItemPayload {
  id: number;
  description: string;
  is_done: 0 | 1 | boolean;
  done_at?: string | null;
  evidence_url?: string | null;
}

export interface ProjectStatePayload {
  id: number;
  dream_id: string;
  status:
    | "dreaming"
    | "in_progress"
    | "at_risk"
    | "stuck"
    | "completed"
    | "archived_consciously";
  started_at?: string | null;
  last_progress_at?: string | null;
  completed_at?: string | null;
  archived_reason?: string | null;
  archived_at?: string | null;
  functionality: FunctionalityItemPayload[];
}

export interface CompletionAuditPayload {
  functionality_checklist_remaining: string[];
  blocked_by: string[];
  smallest_next_functional_increment: string;
}

export interface SynthesisStructuredPayload {
  insights_per_agent?: Array<{ agent: string; insight: string }>;
  tensions?: Array<{ between: string[]; why: string }>;
  recommendations?: string[];
  open_questions?: string[];
  action_steps?: Array<{ step: string; due?: string; priority?: string }>;
  commitments?: Array<{ text: string; follow_up_at?: string }>;
  completion_audit?: CompletionAuditPayload;
}

export interface CompletionAuditViolationPayload {
  kind: string;
  message: string;
  details?: Record<string, unknown>;
}

// ── Stan UI debaty ─────────────────────────────────────────────────────────

export interface LiveTensionPair {
  a: string;
  b: string;
  intensity: number;
}

export interface DebateState {
  status: DebateStatus;
  agents: Record<string, AgentState>;
  synthesis: string;
  error?: string;
  debateId?: number;
  debateCost?: number;
  budgetWarning?: string;
  /** Pary agentów z heurystyki backendu — przed syntezą */
  liveTensions?: LiveTensionPair[];
  /** Debata źródłowa przy kontynuacji wątku */
  continuationParentId?: number | null;
  // AKSJOMATY 1+2:
  dream?: DreamArchitecturePayload;
  dreamError?: string;
  project?: ProjectStatePayload;
  synthesisStructured?: SynthesisStructuredPayload;
  auditViolation?: CompletionAuditViolationPayload;
  /** Tryb debaty z SSE `debate_start` — np. `schematy` wymusza follow-up 72h przy zobowiązaniu. */
  debateMode?: string;
  /** Ostatnie auto-zobowiązanie z SSE (tryb schematy). */
  lastCommitmentEcho?: Record<string, unknown>;
}

// ── SSE event payloads ─────────────────────────────────────────────────────

export interface DebateStartPayload {
  agents: string[];
  synthesizer: string;
  context_preview: string;
  mode?: string;
  category?: string;
  dream_id?: string | null;
  continuation_parent_id?: number | null;
}
export interface AgentChunkPayload {
  agent: string;
  chunk: string;
}
export interface AgentDonePayload {
  agent: string;
  full_text: string;
}
export interface SynthesisChunkPayload {
  chunk: string;
}
export interface SynthesisDonePayload {
  full_text: string;
}
export interface DebateDonePayload {
  debate_id?: number | null;
  agent_count: number;
  synthesizer?: string;
  timestamp: string;
  dream_id?: string | null;
  project_id?: number | null;
  continuation_parent_id?: number | null;
  cost_usd?: number | null;
}

export interface BudgetWarningPayload {
  spent_usd: number;
  ceiling_usd: number;
  message: string;
}

export interface LiveTensionsPayload {
  pairs: LiveTensionPair[];
}

// ── Brief (request body do POST /debate/stream) ────────────────────────────

export interface Brief {
  description: string;
  category?: "decyzja" | "projekt" | "marzenie" | "schemat";
  mode?: "pelna" | "marzen" | "schematy" | "codzienny";
  language?: "pl" | "en";
  intention?: string;
  extra_context?: string;
  // legacy (zachowane dla kompatybilności):
  scale?: "startup" | "enterprise" | "small";
  budget?: "low" | "medium" | "high";
}

export interface DebateContinueBody {
  previous_debate_id: number;
  follow_up: string;
}
