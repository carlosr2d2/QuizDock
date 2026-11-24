export type PlanTier = "free" | "individual" | "team" | "enterprise";
export type MembershipRole = "owner" | "admin" | "member" | "auditor";
export type DocumentStatus = "uploaded" | "processing" | "ready" | "failed";
export type ExamKind = "quiz" | "exam";
export type ExamStatus = "draft" | "generating" | "ready" | "assigned" | "archived" | "failed";
export type JobStatus = "queued" | "running" | "succeeded" | "failed";

export type Organization = {
  id: string;
  name: string;
  slug: string;
  plan: PlanTier;
  is_personal: boolean;
};

export type Membership = {
  id: string;
  organization_id: string;
  role: MembershipRole;
  organization: Organization;
};

export type User = {
  id: string;
  email: string;
  full_name: string;
  locale: string;
  is_active: boolean;
  personal_organization_id: string | null;
  memberships: Membership[];
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: User;
  organization_id: string;
};

export type Document = {
  id: string;
  organization_id: string;
  owner_user_id: string;
  filename: string;
  display_title: string | null;
  title: string;
  content_type: string;
  status: DocumentStatus;
  language: string;
  page_count: number | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  has_cover: boolean;
  document_kind: string;
};

export type Exam = {
  id: string;
  organization_id: string;
  owner_user_id: string;
  document_id: string | null;
  title: string;
  kind: ExamKind;
  status: ExamStatus;
  time_limit_minutes: number | null;
  question_count: number;
  generated_count?: number;
  credit_cost: number;
  error_message: string | null;
  created_at: string;
  document_title: string | null;
  document_kind: string | null;
  has_cover: boolean;
  attempt_count: number;
  last_score: number | null;
  last_attempt_at: string | null;
  assigned_to_me: boolean;
  assignment_status: "pending" | "completed" | null;
  assignment_count: number;
  assignment_completed_count: number;
  can_assign: boolean;
  allow_pdf_download?: boolean;
  can_download_pdf?: boolean;
};

export type ExamAssignment = {
  id: string;
  user_id: string;
  email: string;
  full_name: string;
  status: "pending" | "completed" | string;
  completed_at: string | null;
  last_score: number | null;
  last_attempt_id: string | null;
};

export type QuestionKind = "true_false" | "single_choice" | "multiple_choice";

export type QuestionPublic = {
  id: string;
  prompt: string;
  kind?: QuestionKind;
  options: string[];
  difficulty: string;
  position: number;
};

export type AttemptSummary = {
  id: string;
  exam_id: string;
  score: number;
  completed_at: string;
};

export type ExamDetail = Exam & {
  questions: QuestionPublic[];
  attempts: AttemptSummary[];
  assignments: ExamAssignment[];
  assigned_group_ids?: string[];
};

export type Evidence = {
  quote: string;
  document_id?: string | null;
  document_title?: string | null;
  page_start?: number | null;
  page_end?: number | null;
  chapter?: string | null;
  section?: string | null;
  confidence?: number;
  relevance?: number | null;
  model?: string | null;
  generated_at?: string | null;
  verified?: boolean;
  source?: string | null;
};

export type ChatCitation = {
  chunk_id?: string | null;
  quote: string;
  page_start?: number | null;
  page_end?: number | null;
  chapter?: string | null;
  section?: string | null;
  confidence?: number | null;
};

export type ChatMessage = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system" | string;
  content: string;
  citations: ChatCitation[];
  refusal: boolean;
  model?: string | null;
  created_at: string;
};

export type ChatSession = {
  id: string;
  document_id: string;
  user_id: string;
  exam_id?: string | null;
  title?: string | null;
  created_at: string;
  updated_at: string;
};

export type ChatSessionDetail = ChatSession & {
  messages: ChatMessage[];
};

export type QuestionResult = {
  question_id: string;
  prompt: string;
  kind?: QuestionKind;
  options: string[];
  selected_index: number | null;
  selected_indices?: number[];
  correct_index: number;
  correct_indices?: number[];
  explanation: string | null;
  is_correct: boolean;
  evidence?: Evidence | null;
};

export type Attempt = AttemptSummary & {
  results: QuestionResult[];
  user_id: string;
  full_name: string;
  email: string;
  is_own: boolean;
};

export type ProgressAttempt = AttemptSummary & {
  exam_title: string;
};

export type WeakExam = {
  exam_id: string;
  exam_title: string;
  average_score: number;
  attempt_count: number;
};

export type KindAccuracy = {
  kind: QuestionKind;
  correct: number;
  total: number;
  accuracy: number | null;
};

export type MemberAssignmentProgress = {
  exam_id: string;
  exam_title: string;
  status: "pending" | "completed" | string;
  last_score: number | null;
  last_attempt_id: string | null;
  completed_at: string | null;
};

export type MemberProgress = {
  user_id: string;
  full_name: string;
  email: string;
  role: MembershipRole | string;
  attempt_count: number;
  exams_taken: number;
  average_score: number | null;
  best_score: number | null;
  last_score: number | null;
  assigned_count: number;
  assigned_pending_count: number;
  recent: ProgressAttempt[];
  assignments: MemberAssignmentProgress[];
};

export type TeamMemberAnalytics = {
  user_id: string;
  full_name: string;
  email: string;
  role: MembershipRole | string;
  attempt_count: number;
  exams_taken: number;
  average_score: number | null;
  assigned_count: number;
  assigned_pending_count: number;
};

export type TeamExamAnalytics = {
  exam_id: string;
  title: string;
  assigned_count: number;
  completed_count: number;
  average_score: number | null;
};

export type TeamRecentAttempt = {
  id: string;
  exam_id: string;
  exam_title: string;
  user_id: string;
  full_name: string;
  score: number;
  completed_at: string;
};

export type TeamAnalytics = {
  member_count: number;
  attempt_count: number;
  exams_taken: number;
  assigned_count: number;
  completed_count: number;
  pending_count: number;
  completion_rate: number | null;
  average_score: number | null;
  best_score: number | null;
  members: TeamMemberAnalytics[];
  exams: TeamExamAnalytics[];
  recent: TeamRecentAttempt[];
};

export type Progress = {
  attempt_count: number;
  exams_taken: number;
  average_score: number | null;
  best_score: number | null;
  last_score: number | null;
  recent: ProgressAttempt[];
  trend: ProgressAttempt[];
  weak_exams: WeakExam[];
  kind_accuracy: KindAccuracy[];
  study_streak_days: number;
  flashcard_count: number;
  flashcard_due: number;
  flashcard_reviewed: number;
  flashcard_mastered: number;
  flashcard_last_reviewed_at: string | null;
};

export type Flashcard = {
  id: string;
  organization_id: string;
  owner_user_id: string;
  document_id: string | null;
  front: string;
  back: string;
  interval_days: number;
  ease_factor: number;
  repetitions: number;
  next_review_at: string | null;
  last_reviewed_at: string | null;
  created_at: string;
  document_title: string | null;
  document_kind: string | null;
  has_cover: boolean;
  is_due: boolean;
};

export type FlashcardDeck = {
  document_id: string | null;
  document_title: string;
  document_kind: string | null;
  has_cover: boolean;
  card_count: number;
  due_count: number;
  last_reviewed_at: string | null;
};

export type GenerationJob = {
  id: string;
  organization_id: string;
  document_id: string;
  kind: string;
  status: JobStatus | string;
  credit_cost: number;
  item_count: number;
  result_id: string | null;
  error_message: string | null;
  created_at: string;
};

export type CreditBalance = {
  organization_id: string;
  balance: number;
  plan: string;
  plan_sku?: string | null;
  plan_renews_at?: string | null;
  monthly_credits?: number | null;
};

export type PaymentProviderId = "stripe" | "wompi" | "simulated" | string;

export type PackPrice = {
  provider: PaymentProviderId;
  amount: number;
  currency: string;
};

export type CreditPack = {
  id: string;
  credits: number;
  prices: PackPrice[];
};

export type SubscriptionPlan = {
  id: string;
  tier: string;
  monthly_credits: number;
  seats: number | null;
  personal_only: boolean;
  available: boolean;
  prices: PackPrice[];
};

export type BillingSubscription = {
  plan: string;
  sku: string | null;
  renews_at: string | null;
  monthly_credits: number | null;
  cancelable: boolean;
};

export type PaymentProvider = {
  id: PaymentProviderId;
  label: string;
  recommended: boolean;
  currencies: string[];
};

export type BillingCatalog = {
  billing_country: string;
  default_provider: PaymentProviderId | null;
  can_purchase: boolean;
  is_personal?: boolean;
  subscription?: BillingSubscription | null;
  providers: PaymentProvider[];
  plans?: SubscriptionPlan[];
  packs: CreditPack[];
};

export type PaymentOrder = {
  id: string;
  provider: PaymentProviderId;
  kind?: "pack" | "plan" | string;
  pack_id: string;
  credits: number;
  amount: number;
  currency: string;
  status: "pending" | "completed" | "failed" | "canceled" | string;
  checkout_url: string | null;
  created_at: string;
  completed_at: string | null;
};

export type CreditTransaction = {
  id: string;
  amount: number;
  reason: string;
  balance_after: number;
  created_at: string;
};

export type InvitationStatus = "pending" | "accepted" | "revoked" | "expired";

export type TeamMember = {
  id: string;
  user_id: string;
  email: string;
  full_name: string;
  role: MembershipRole;
  last_seen_at?: string | null;
};

export type TeamGroup = {
  id: string;
  organization_id: string;
  name: string;
  member_count: number;
  members: TeamMember[];
};

export type Invitation = {
  id: string;
  organization_id: string;
  email: string;
  role: MembershipRole;
  status: InvitationStatus;
  token: string | null;
  expires_at: string;
  created_at: string;
  email_sent?: boolean | null;
};

export type InvitationPublic = {
  organization_id: string;
  organization_name: string;
  email: string;
  role: MembershipRole;
  status: InvitationStatus;
  expires_at: string;
};

export type MyInvitation = InvitationPublic & {
  id: string;
  token: string;
};

export type InvitationAccept = {
  organization: Organization;
  role: MembershipRole;
};

export type TeamSnapshot = {
  organization: Organization;
  role: MembershipRole;
  can_manage: boolean;
  can_create_content: boolean;
  can_invite?: boolean;
  seat_limit?: number | null;
  seat_used?: number;
  members: TeamMember[];
  invitations: Invitation[];
  groups?: TeamGroup[];
};

export type AuditAction =
  | "member.invited"
  | "member.invite_resent"
  | "member.invite_revoked"
  | "member.joined"
  | "member.removed"
  | "group.created"
  | "group.renamed"
  | "group.deleted"
  | "group.members_updated"
  | "document.uploaded"
  | "document.deleted"
  | "exam.generation_requested"
  | "exam.assigned"
  | "exam.unassigned"
  | "flashcard.generation_requested"
  | "organization.created"
  | string;

export type AuditEvent = {
  id: string;
  organization_id: string;
  actor_user_id: string | null;
  actor_email: string | null;
  actor_full_name: string | null;
  actor_role: MembershipRole | null;
  action: AuditAction;
  target_type: string;
  target_id: string | null;
  summary: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type AuditEventList = {
  items: AuditEvent[];
  total: number;
  limit: number;
  offset: number;
};

export type AiFeature = "generation" | "evidence" | "chat" | "appeal_review" | string;

export type AiDecisionEvent = {
  id: string;
  organization_id: string;
  actor_user_id?: string | null;
  actor_email?: string | null;
  actor_full_name?: string | null;
  feature: AiFeature;
  document_id?: string | null;
  conversation_id?: string | null;
  model: string;
  prompt_hash?: string | null;
  chunk_ids: string[];
  confidence?: number | null;
  relevance?: number | null;
  outcome: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type AiDecisionEventList = {
  items: AiDecisionEvent[];
  total: number;
  limit: number;
  offset: number;
};

export type AppealStatus =
  | "pending"
  | "in_review"
  | "needs_info"
  | "accepted"
  | "rejected"
  | "closed";

export type AppealEvidence = {
  id: string;
  appeal_id: string;
  submitted_by_user_id: string;
  chunk_id?: string | null;
  quote: string;
  page_start?: number | null;
  page_end?: number | null;
  chapter?: string | null;
  section?: string | null;
  argument?: string | null;
  source: "student" | "system" | "teacher" | string;
  created_at: string;
};

export type AppealResolution = {
  id: string;
  appeal_id: string;
  resolver_user_id: string;
  decision: "accepted" | "rejected" | "needs_info" | string;
  rationale: string;
  score_adjustment?: number | null;
  resolved_at: string;
};

export type AppealAction = {
  id: string;
  appeal_id: string;
  actor_user_id?: string | null;
  action: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type Appeal = {
  id: string;
  organization_id: string;
  attempt_id: string;
  question_id: string;
  exam_id: string;
  student_user_id: string;
  status: AppealStatus;
  student_argument: string;
  selected_indices: number[];
  correct_indices: number[];
  system_evidence_snapshot: Record<string, unknown>;
  question_prompt: string;
  exam_title: string;
  created_at: string;
  updated_at: string;
  student_name: string;
  student_email: string;
};

export type AppealComment = {
  id: string;
  appeal_id: string;
  author_user_id: string;
  body: string;
  attachment_keys: string[];
  created_at: string;
  author_name: string;
  author_email: string;
};

export type AppealAttachment = {
  storage_key: string;
  filename: string;
  content_type: string;
  size: number;
};

export type AppealAiRecommendation = {
  id: string;
  appeal_id: string;
  requested_by_user_id: string;
  status: "queued" | "running" | "ready" | "failed" | string;
  recommendation?: "accepted" | "rejected" | "needs_info" | string | null;
  confidence?: number | null;
  rationale: string;
  ambiguity: boolean;
  alt_chunk_ids: string[];
  system_quote?: string | null;
  student_quote?: string | null;
  model: string;
  error_message?: string | null;
  credit_cost: number;
  created_at: string;
  updated_at: string;
};

export type AppealDetail = Appeal & {
  document_id?: string | null;
  evidence: AppealEvidence[];
  comments: AppealComment[];
  ai_recommendation?: AppealAiRecommendation | null;
  resolution?: AppealResolution | null;
  actions: AppealAction[];
};

export type DocumentChunkPreview = {
  id: string;
  position: number;
  content: string;
  page_start?: number | null;
  page_end?: number | null;
  chapter?: string | null;
  section?: string | null;
};
