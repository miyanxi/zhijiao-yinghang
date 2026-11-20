const API_BASE = `${import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8001"}/api/v1`;

export async function downloadPdf(path: string, filename: string) {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "PDF 下载失败");
  }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

export type Teacher = {
  id: number;
  name: string;
  created_at: string;
};

export type ClassSummary = {
  id: number;
  name: string;
  grade: string;
  current_topic: string | null;
  current_progress: string | null;
  teacher_id: number;
  created_at: string;
};

export type Student = {
  id: number;
  name: string;
  student_no: string;
  class_id: number;
  status: string;
  created_at: string;
};

export type ClassDetail = ClassSummary & {
  teacher: Teacher;
  students: Student[];
};

export type ClassKnowledgePoint = {
  knowledge_point_id: number;
  name: string;
  category: string;
  attempts: number;
  correct_count: number;
  accuracy: number;
};

export type ClassLearningOverview = {
  demo_submission_count: number;
  class_id: number;
  assignment_count: number;
  average_score: number | null;
  completion_rate: number;
  knowledge_points: ClassKnowledgePoint[];
  attention_students: number;
  error_count: number;
  score_trend: ScoreTrendPoint[];
  teaching_notes: { lesson_plan_id: number; title: string; evaluation: string; reflection: string; updated_at: string }[];
};

export type ScoreTrendPoint = { assignment_id: number; title: string; assigned_at: string; score: number | null; submission_count: number | null };

export type StudentProfile = {
  id: number;
  student_id: number;
  knowledge_point_id: number;
  total_attempts: number;
  correct_count: number;
  accuracy: number;
  recent_accuracy: number;
  consecutive_weak_count: number;
  trend: string;
  attention_status: string;
  calculated_at: string;
  knowledge_point: { id: number; name: string; category: string };
};

export type StudentLearningRecord = {
  demo_simulated: boolean;
  id: number;
  assignment_id: number;
  assignment_title: string;
  question_id: number;
  knowledge_point_id: number;
  knowledge_point_name: string;
  is_correct: boolean;
  answer_text: string;
  score: number;
  occurred_at: string;
};

export type StudentLearningOverview = {
  student_id: number;
  assignment_count: number;
  average_score: number | null;
  completion_rate: number;
  profiles: StudentProfile[];
  recent_assignments: { id: number; title: string; assigned_at: string; status: string; mode: string }[];
  records: StudentLearningRecord[];
  score_trend: ScoreTrendPoint[];
};

export type AssignmentSummary = {
  id: number;
  title: string;
  assigned_at: string;
  status: string;
  mode: string;
  question_count: number;
  submission_count: number;
  average_score: number | null;
  source_draft_id: number | null;
};

export type AssignmentDetail = AssignmentSummary & {
  questions: { question_id: number; order_no: number; type: string; stem: string; options: string[]; answer: string; explanation: string; difficulty: string; knowledge_point_names: string[] }[];
  submissions: { id: number; student_id: number; student_name: string; submitted_at: string; total_score: number; answers: { question_id: number; question_stem: string; knowledge_point_names: string[]; answer_text: string; is_correct: boolean; score: number }[] }[];
};

export type KnowledgePoint = { id: number; name: string; category: string };
export type GoalFields = {
  topic: string;
  knowledge_point_ids: number[];
  objectives: string[];
  key_points: string;
  difficult_points: string;
  class_context: string;
  teaching_advice: string;
  teacher_requirements: string;
};
export type GoalParsed = GoalFields & { source: string };
export type TeachingGoal = GoalFields & { id: number; class_id: number; raw_input: string; source: string; status: string; created_at: string };
export type LessonSection = { key: string; title: string; content: string; duration_minutes: number };
export type LessonPlan = { id: number; class_id: number; teaching_goal_id: number; title: string; sections: LessonSection[]; difficulty: string; duration_minutes: number; status: string; source: string; created_at: string; updated_at: string; post_evaluation: string | null; post_reflection: string | null; reviewed_at: string | null };
export type DraftQuestion = { id: number; order_no: number; type: string; stem: string; options: string[]; answer: string; explanation: string; knowledge_point_id: number; difficulty: string; quality_status: string; quality_issues: string[] };
export type AssignmentDraft = { id: number; class_id: number; teaching_goal_id: number; title: string; mode: string; difficulty: string; status: string; source: string; created_at: string; questions: DraftQuestion[] };
export type StudentWorks = { assignment_id: number; title: string; demo_upload_enabled: boolean; works: { id: number; student_id: number; file_name: string; status: string; extracted_answers: Record<string, string>; score: number | null; error_message: string | null; demo_simulated: boolean }[] };
export type TrainingCandidate = { student_id: number; student_name: string; knowledge_point_id: number; knowledge_point_name: string; accuracy: number; recent_accuracy: number; consecutive_weak_count: number; total_attempts: number };
export type TrainingQuestion = { order_no: number; type: string; stem: string; options: string[]; answer: string; explanation: string; knowledge_point_id: number; difficulty: string; quality_status: string; quality_issues: string[] };
export type TargetedTraining = { id: number; class_id: number; student_id: number; student_name: string; knowledge_point_id: number; knowledge_point_name: string; assignment_id: number | null; status: string; source: string | null; question_count: number; duration_minutes: number; baseline_accuracy: number; baseline_recent_accuracy: number; current_accuracy: number | null; current_recent_accuracy: number | null; training_score: number | null; training_accuracy: number | null; questions: TrainingQuestion[]; created_at: string };
export type ManagerAction = { view: "analytics" | "student-detail" | "goals" | "lesson-plans" | "smart-assignments" | "training"; label: string; requires_confirmation: boolean; student_id: number | null; knowledge_point_id: number | null; duration_minutes: number | null; question_count: number | null };
export type ManagerResponse = { intent: string; source: "demo" | "deepseek" | "program"; title: string; summary: string; metrics: { label: string; value: string }[]; evidence: string[]; action: ManagerAction | null };
export type AssessmentImport = { id: number; class_id: number; assignment_id: number; title: string; status: string; paper_file_name: string; answer_key_file_name: string; questions: AssignmentDetail["questions"]; works: { id: number; student_id: number; file_name: string; status: string; extracted_answers: Record<string, string>; score: number | null; error_message: string | null }[] };

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(typeof error?.detail === "string" ? error.detail : `请求失败（${response.status}）`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

async function upload<T>(path: string, form: FormData): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { method: "POST", body: form });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(typeof error?.detail === "string" ? error.detail : `上传失败（${response.status}）`);
  }
  return response.json() as Promise<T>;
}

const send = <T>(path: string, method: "POST" | "PATCH" | "DELETE", body?: unknown) =>
  request<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  getClasses: () => request<ClassSummary[]>("/classes"),
  getClass: (id: number) => request<ClassDetail>(`/classes/${id}`),
  getClassStudents: (id: number) => request<Student[]>(`/classes/${id}/students`),
  getStudent: (id: number) => request<Student>(`/students/${id}`),
  getClassLearningOverview: (id: number) => request<ClassLearningOverview>(`/classes/${id}/learning-overview`),
  getStudentLearningOverview: (id: number) => request<StudentLearningOverview>(`/students/${id}/learning-overview`),
  getAssignments: (classId: number) => request<AssignmentSummary[]>(`/assignments?class_id=${classId}`),
  getAssignment: (id: number) => request<AssignmentDetail>(`/assignments/${id}`),
  getHealth: () => request<{ status: string; database: string }>("/health"),
  createClass: (body: { name: string; grade: string; current_topic?: string }) => send<ClassSummary>("/classes", "POST", body),
  updateClass: (id: number, body: Partial<Pick<ClassSummary, "name" | "grade" | "current_topic" | "current_progress">>) => send<ClassSummary>(`/classes/${id}`, "PATCH", body),
  createStudent: (classId: number, body: { name: string; student_no: string }) => send<Student>(`/classes/${classId}/students`, "POST", body),
  updateStudent: (id: number, body: Partial<Pick<Student, "name" | "student_no" | "status">>) => send<Student>(`/students/${id}`, "PATCH", body),
  getKnowledgePoints: () => request<KnowledgePoint[]>("/teaching-goals/knowledge-points/catalog"),
  createKnowledgePoint: (name: string, category: string) => send<KnowledgePoint>("/teaching-goals/knowledge-points", "POST", { name, category }),
  getGoals: (classId: number) => request<TeachingGoal[]>(`/teaching-goals?class_id=${classId}`),
  parseGoal: (classId: number, rawInput: string) => send<GoalParsed>("/teaching-goals/parse", "POST", { class_id: classId, raw_input: rawInput }),
  createGoal: (body: GoalFields & { class_id: number; raw_input: string; source: string }) => send<TeachingGoal>("/teaching-goals", "POST", body),
  updateGoal: (id: number, body: Partial<GoalFields>) => send<TeachingGoal>(`/teaching-goals/${id}`, "PATCH", body),
  confirmGoal: (id: number) => send<TeachingGoal>(`/teaching-goals/${id}/confirm`, "POST"),
  deleteGoal: (id: number) => send<void>(`/teaching-goals/${id}`, "DELETE"),
  getLessonPlans: (classId: number) => request<LessonPlan[]>(`/lesson-plans?class_id=${classId}`),
  generateLessonPlan: (goalId: number, difficulty: string, durationMinutes: number) => send<LessonPlan>("/lesson-plans/generate", "POST", { teaching_goal_id: goalId, difficulty, duration_minutes: durationMinutes }),
  updateLessonPlan: (id: number, body: Partial<Pick<LessonPlan, "title" | "difficulty" | "duration_minutes">>) => send<LessonPlan>(`/lesson-plans/${id}`, "PATCH", body),
  updateLessonSection: (planId: number, key: string, body: Pick<LessonSection, "content" | "duration_minutes">) => send<LessonPlan>(`/lesson-plans/${planId}/sections/${key}`, "PATCH", body),
  deleteLessonSection: (planId: number, key: string) => send<LessonPlan>(`/lesson-plans/${planId}/sections/${key}`, "DELETE"),
  regenerateLessonSection: (planId: number, key: string) => send<LessonPlan>(`/lesson-plans/${planId}/sections/${key}/regenerate`, "POST"),
  deleteLessonPlan: (id: number) => send<void>(`/lesson-plans/${id}`, "DELETE"),
  submitLessonReview: (id: number) => send<LessonPlan>(`/lesson-plans/${id}/submit-review`, "POST"),
  approveLessonPlan: (id: number) => send<LessonPlan>(`/lesson-plans/${id}/approve`, "POST"),
  savePostReview: (id: number, evaluation: string, reflection: string) => request<LessonPlan>(`/lesson-plans/${id}/post-review`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ evaluation, reflection }) }),
  getAssignmentDrafts: (classId: number) => request<AssignmentDraft[]>(`/assignment-drafts?class_id=${classId}`),
  generateAssignmentDraft: (goalId: number, questionCount: number, difficulty: string) => send<AssignmentDraft>("/assignment-drafts/generate", "POST", { teaching_goal_id: goalId, question_count: questionCount, difficulty }),
  updateDraftQuestion: (draftId: number, questionId: number, body: Partial<DraftQuestion>) => send<AssignmentDraft>(`/assignment-drafts/${draftId}/questions/${questionId}`, "PATCH", body),
  deleteDraftQuestion: (draftId: number, questionId: number) => send<AssignmentDraft>(`/assignment-drafts/${draftId}/questions/${questionId}`, "DELETE"),
  regenerateDraftQuestion: (draftId: number, questionId: number) => send<AssignmentDraft>(`/assignment-drafts/${draftId}/questions/${questionId}/regenerate`, "POST"),
  checkDraftQuestion: (draftId: number, questionId: number) => send<AssignmentDraft>(`/assignment-drafts/${draftId}/questions/${questionId}/check`, "POST"),
  submitAssignmentReview: (id: number) => send<AssignmentDraft>(`/assignment-drafts/${id}/submit-review`, "POST"),
  approveAssignmentDraft: (id: number) => send<AssignmentDraft>(`/assignment-drafts/${id}/approve`, "POST"),
  deleteAssignmentDraft: (id: number) => send<void>(`/assignment-drafts/${id}`, "DELETE"),
  publishAssignment: (draftId: number) => send<AssignmentSummary>(`/assignments/publish/${draftId}`, "POST"),
  getAssignmentStudentWorks: (assignmentId: number) => request<StudentWorks>(`/assignments/${assignmentId}/student-works`),
  uploadAssignmentStudentWork: (assignmentId: number, studentId: number, work: File) => {
    const form = new FormData(); form.set("student_id", String(studentId)); form.set("work", work);
    return upload<StudentWorks>(`/assignments/${assignmentId}/student-works`, form);
  },
  confirmAssignmentStudentWork: (assignmentId: number, workId: number) => send<StudentWorks>(`/assignments/${assignmentId}/student-works/${workId}/confirm`, "POST"),
  submitAnswers: (assignmentId: number, studentId: number, answers: { question_id: number; answer_text: string }[]) =>
    send<AssignmentDetail["submissions"][number]>(`/assignments/${assignmentId}/submissions`, "POST", { student_id: studentId, answers }),
  getTrainingCandidates: (classId: number) => request<TrainingCandidate[]>(`/targeted-trainings/candidates?class_id=${classId}`),
  getTargetedTrainings: (classId: number) => request<TargetedTraining[]>(`/targeted-trainings?class_id=${classId}`),
  getTargetedTraining: (id: number) => request<TargetedTraining>(`/targeted-trainings/${id}`),
  confirmTargetedTraining: (studentId: number, knowledgePointId: number, questionCount: number, durationMinutes: number) =>
    send<TargetedTraining>("/targeted-trainings/confirm", "POST", { student_id: studentId, knowledge_point_id: knowledgePointId, question_count: questionCount, duration_minutes: durationMinutes }),
  generateTargetedTraining: (id: number) => send<TargetedTraining>(`/targeted-trainings/${id}/generate`, "POST"),
  updateTrainingQuestion: (id: number, orderNo: number, body: Pick<TrainingQuestion, "stem" | "options" | "answer" | "explanation" | "difficulty">) =>
    send<TargetedTraining>(`/targeted-trainings/${id}/questions/${orderNo}`, "PATCH", body),
  checkTrainingQuestion: (id: number, orderNo: number) => send<TargetedTraining>(`/targeted-trainings/${id}/questions/${orderNo}/check`, "POST"),
  submitTrainingReview: (id: number) => send<TargetedTraining>(`/targeted-trainings/${id}/submit-review`, "POST"),
  approveTargetedTraining: (id: number) => send<TargetedTraining>(`/targeted-trainings/${id}/approve`, "POST"),
  publishTargetedTraining: (id: number) => send<TargetedTraining>(`/targeted-trainings/${id}/publish`, "POST"),
  interpretManagerRequest: (classId: number, message: string) => send<ManagerResponse>("/manager/interpret", "POST", { class_id: classId, message }),
  getAssessmentImports: (classId: number) => request<AssessmentImport[]>(`/assessment-imports?class_id=${classId}`),
  createAssessmentImport: (classId: number, title: string, paper: File, answerKey: File) => {
    const form = new FormData(); form.set("class_id", String(classId)); form.set("title", title); form.set("paper", paper); form.set("answer_key", answerKey);
    return upload<AssessmentImport>("/assessment-imports", form);
  },
  approveAssessmentImport: (id: number) => send<AssessmentImport>(`/assessment-imports/${id}/approve`, "POST"),
  correctImportedQuestion: (id: number, questionId: number, body: { stem: string; answer: string; explanation: string; knowledge_point_name: string }) => send<AssessmentImport>(`/assessment-imports/${id}/questions/${questionId}`, "PATCH", body),
  uploadStudentWork: (id: number, studentId: number, work: File) => {
    const form = new FormData(); form.set("student_id", String(studentId)); form.set("work", work);
    return upload<AssessmentImport>(`/assessment-imports/${id}/student-work`, form);
  },
  confirmStudentWork: (id: number, workId: number) => send<AssessmentImport>(`/assessment-imports/${id}/student-work/${workId}/confirm`, "POST"),
  correctStudentWork: (id: number, workId: number, answers: Record<string, string>) => send<AssessmentImport>(`/assessment-imports/${id}/student-work/${workId}`, "PATCH", { answers }),
};
