import { useEffect, useState } from "react";
import {
  AlertCircle,
  BarChart3,
  BookOpenCheck,
  CheckCircle2,
  ClipboardCheck,
  FileText,
  Gauge,
  LayoutDashboard,
  Menu,
  Pencil,
  Plus,
  Sparkles,
  Users,
} from "lucide-react";
import {
  api,
  type AssignmentDetail,
  type AssignmentSummary,
  type ClassDetail,
  type ClassLearningOverview,
  type ClassSummary,
  type Student,
  type StudentLearningOverview,
} from "./api/client";
import { TeachingGoalsPage } from "./pages/TeachingGoalsPage";
import { LessonPlansPage } from "./pages/LessonPlansPage";
import { SmartAssignmentsPage } from "./pages/SmartAssignmentsPage";
import { ClassDialog, StudentsManagement } from "./pages/Management";
import { ScoreTrend } from "./pages/ScoreTrend";

type View = "dashboard" | "goals" | "lesson-plans" | "smart-assignments" | "students" | "student-detail" | "assignments" | "assignment-detail" | "analytics" | "placeholder";

const navItems: { id: View; label: string; icon: typeof LayoutDashboard; soon?: boolean }[] = [
  { id: "dashboard", label: "首页", icon: LayoutDashboard },
  { id: "goals", label: "教学目标", icon: BookOpenCheck },
  { id: "lesson-plans", label: "智能教案", icon: FileText },
  { id: "smart-assignments", label: "智能作业", icon: ClipboardCheck },
  { id: "assignments", label: "作业管理", icon: BarChart3 },
  { id: "analytics", label: "学情分析", icon: Gauge },
  { id: "students", label: "学生管理", icon: Users },
];

function App() {
  const [classes, setClasses] = useState<ClassSummary[]>([]);
  const [selectedClass, setSelectedClass] = useState<ClassDetail | null>(null);
  const [classOverview, setClassOverview] = useState<ClassLearningOverview | null>(null);
  const [assignments, setAssignments] = useState<AssignmentSummary[]>([]);
  const [studentOverviews, setStudentOverviews] = useState<Record<number, StudentLearningOverview>>({});
  const [selectedStudent, setSelectedStudent] = useState<Student | null>(null);
  const [selectedStudentOverview, setSelectedStudentOverview] = useState<StudentLearningOverview | null>(null);
  const [selectedAssignment, setSelectedAssignment] = useState<AssignmentDetail | null>(null);
  const [view, setView] = useState<View>("dashboard");
  const [classDialog, setClassDialog] = useState<"create" | "edit" | null>(null);
  const [placeholderLabel, setPlaceholderLabel] = useState("");
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const items = await api.getClasses();
        if (!items[0]) throw new Error("当前没有可用班级，请先初始化演示数据");
        const detail = await api.getClass(items[0].id);
        const [overview, assignmentItems, overviewEntries] = await Promise.all([
          api.getClassLearningOverview(detail.id),
          api.getAssignments(detail.id),
          Promise.all(detail.students.map(async (student) => [student.id, await api.getStudentLearningOverview(student.id)] as const)),
        ]);
        if (!cancelled) {
          setClasses(items);
          setSelectedClass(detail);
          setClassOverview(overview);
          setAssignments(assignmentItems.filter((item) => item.mode === "class_unified"));
          setStudentOverviews(Object.fromEntries(overviewEntries));
        }
      } catch (reason) {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "教学数据加载失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, []);

  const refreshClassData = async (classId: number) => {
    const [detail, overview, assignmentItems] = await Promise.all([
      api.getClass(classId),
      api.getClassLearningOverview(classId),
      api.getAssignments(classId),
    ]);
    const entries = await Promise.all(detail.students.map(async (student) => [student.id, await api.getStudentLearningOverview(student.id)] as const));
    setSelectedClass(detail);
    setClassOverview(overview);
    setAssignments(assignmentItems.filter((item) => item.mode === "class_unified"));
    setStudentOverviews(Object.fromEntries(entries));
  };

  const refreshClasses = async (classId: number) => {
    setClasses(await api.getClasses());
    await refreshClassData(classId);
  };

  const openStudent = async (student: Student) => {
    setActionLoading(true);
    setError(null);
    try {
      setSelectedStudent(student);
      setSelectedStudentOverview(await api.getStudentLearningOverview(student.id));
      setView("student-detail");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "学生画像加载失败");
    } finally {
      setActionLoading(false);
    }
  };

  const openAssignment = async (assignment: AssignmentSummary) => {
    setActionLoading(true);
    setError(null);
    try {
      setSelectedAssignment(await api.getAssignment(assignment.id));
      setView("assignment-detail");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "作业详情加载失败");
    } finally {
      setActionLoading(false);
    }
  };


  const currentLabel = view === "students" || view === "student-detail" ? "学生管理" : view === "assignments" || view === "assignment-detail" ? "作业管理" : view === "analytics" ? "学情分析" : view === "goals" ? "教学目标" : view === "lesson-plans" ? "智能教案" : view === "smart-assignments" ? "智能作业" : view === "placeholder" ? placeholderLabel : "首页";

  if (loading) return <div className="screen-state">正在加载教学工作台...</div>;
  if (error && !selectedClass) return <div className="screen-state error-state"><strong>暂时无法连接系统</strong><span>{error}</span><span>请确认后端服务已启动。</span></div>;
  if (!selectedClass) return <div className="screen-state error-state"><strong>当前没有可用班级</strong></div>;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark"><Sparkles size={18} /></div><div><strong>智教英航</strong><span>高中英语教学工作台</span></div></div>
        <div className="nav-section-label">教学空间</div>
        <nav className="main-nav">
          {navItems.map((item, index) => {
            const Icon = item.icon;
            const active = item.label === currentLabel;
            return <button key={`${item.label}-${index}`} className={`nav-item ${active ? "active" : ""}`} onClick={() => { setView(item.id); setPlaceholderLabel(item.label); setSelectedStudent(null); setSelectedAssignment(null); }}><Icon size={17} /><span>{item.label}</span>{item.soon && <span className="nav-soon">即将</span>}</button>;
          })}
        </nav>
        <div className="sidebar-footer"><div className="user-chip"><div className="avatar">英</div><div><strong>{selectedClass.teacher.name}</strong><span>教师账户</span></div></div></div>
      </aside>
      <main className="main-area">
        <header className="topbar"><div className="mobile-brand"><Menu size={18} /><strong>智教英航</strong></div><div className="context-select"><span>当前班级</span><select value={selectedClass.id} onChange={async (event) => { const next = classes.find((item) => item.id === Number(event.target.value)); if (!next) return; setLoading(true); try { await refreshClassData(next.id); } catch (reason) { setError(reason instanceof Error ? reason.message : "班级切换失败"); } finally { setLoading(false); } }}>{classes.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select><button className="icon-button" title="新增班级" aria-label="新增班级" onClick={() => setClassDialog("create")}><Plus size={16} /></button><button className="icon-button" title="编辑班级" aria-label="编辑班级" onClick={() => setClassDialog("edit")}><Pencil size={15} /></button></div><div className="topbar-actions"><span className="connection-dot"><i />系统正常</span><div className="top-avatar">英</div></div></header>
        <div className="content-wrap">
          {!!classOverview?.demo_submission_count && <div className="demo-disclosure" role="note">本班数据包含 {classOverview.demo_submission_count} 份演示模拟提交；相关成绩和画像不是对上传 PDF 的真实识别结果。</div>}
          {error && <div className="inline-error" role="alert">{error}<button onClick={() => setError(null)} aria-label="关闭提示">×</button></div>}
          {actionLoading && <div className="inline-loading">正在读取数据...</div>}
          {view === "dashboard" && <Dashboard classDetail={selectedClass} overview={classOverview} assignments={assignments} onStudents={() => setView("students")} onAssignments={() => setView("assignments")} onAnalytics={() => setView("analytics")} />}
          {view === "goals" && <TeachingGoalsPage classId={selectedClass.id} />}
          {view === "lesson-plans" && <LessonPlansPage classId={selectedClass.id} />}
          {view === "smart-assignments" && <SmartAssignmentsPage classId={selectedClass.id} onPublished={async () => { await refreshClassData(selectedClass.id); setView("assignments"); }} />}
          {view === "students" && <StudentsManagement classroom={selectedClass} overviews={studentOverviews} onStudent={openStudent} onRefresh={() => refreshClassData(selectedClass.id)} />}
          {view === "student-detail" && selectedStudent && selectedStudentOverview && <>{selectedStudentOverview.records.some((record) => record.demo_simulated) && <div className="demo-disclosure" role="note">演示模拟记录：本页部分作答来自预设示例，并非上传 PDF 的真实识别结果。</div>}<StudentDetail student={selectedStudent} overview={selectedStudentOverview} className={selectedClass.name} onBack={() => setView("students")} /></>}
          {view === "student-detail" && selectedStudentOverview && <ScoreTrend title="学生作业成绩趋势" points={selectedStudentOverview.score_trend} />}
          {view === "assignments" && <AssignmentsPage assignments={assignments} onAssignment={openAssignment} />}
          {view === "assignment-detail" && selectedAssignment && <AssignmentDetailPage assignment={selectedAssignment} students={selectedClass?.students ?? []} onBack={() => setView("assignments")} onUpdated={() => refreshClassData(selectedClass?.id ?? 1)} />}
          {view === "analytics" && <AnalyticsPage overview={classOverview} students={selectedClass.students} studentOverviews={studentOverviews} onStudent={openStudent} />}
          {view === "analytics" && <ScoreTrend title="班级作业平均分趋势" points={classOverview?.score_trend ?? []} errorCount={classOverview?.error_count ?? 0} />}
          {view === "placeholder" && <Placeholder label={placeholderLabel} />}
        </div>
      </main>
      {classDialog && <ClassDialog current={selectedClass} mode={classDialog} onClose={() => setClassDialog(null)} onSaved={refreshClasses} />}
    </div>
  );
}

function Dashboard({ classDetail, overview, assignments, onStudents, onAssignments, onAnalytics }: { classDetail: ClassDetail; overview: ClassLearningOverview | null; assignments: AssignmentSummary[]; onStudents: () => void; onAssignments: () => void; onAnalytics: () => void }) {
  const weakPoint = overview?.knowledge_points[0];
  return <>
    <div className="page-heading"><div><div className="eyebrow">教学驾驶舱 / {classDetail.name}</div><h1>老师，欢迎回来</h1><p>班级学习数据已经开始沉淀，重点信息会随着作业和答题记录持续更新。</p></div><button className="secondary-button" onClick={onStudents}><Users size={16} />查看学生</button></div>
    <section className="hero-strip"><div className="hero-icon"><BookOpenCheck size={25} /></div><div><span className="label">当前教学主题</span><h2>{classDetail.current_topic ?? "尚未设置"}</h2><p>{classDetail.current_progress ?? "请先设置教学目标和教学进度。"}</p></div><div className="hero-status"><span>数据沉淀中</span><strong>{overview?.assignment_count ?? 0} 次历史作业</strong></div></section>
    <div className="metric-grid"><Metric clickable onClick={onStudents} icon={<Users />} label="班级学生" value={String(classDetail.students.length)} suffix="人" detail="查看学生档案" tone="blue" /><Metric clickable onClick={onAssignments} icon={<BarChart3 />} label="班级平均分" value={formatScore(overview?.average_score)} suffix="分" detail="来自历史作业" tone="purple" /><Metric clickable onClick={onAssignments} icon={<ClipboardCheck />} label="作业完成率" value={formatPercent(overview?.completion_rate)} suffix="%" detail={`${overview?.assignment_count ?? 0} 次统一作业`} tone="green" /><Metric clickable onClick={onAnalytics} icon={<Sparkles />} label="待关注学生" value={String(overview?.attention_students ?? 0)} suffix="人" detail="程序规则识别" tone="orange" /></div>
    <div className="dashboard-grid"><section className="panel glass-panel progress-panel"><div className="panel-heading"><div><span className="eyebrow">班级学习情况</span><h3>知识点掌握概览</h3></div><span className="status-pill neutral">真实答题数据</span></div><div className="knowledge-list">{overview?.knowledge_points.slice(0, 4).map((point) => <div className="knowledge-row" key={point.knowledge_point_id}><div><span>{point.name}</span><strong>{formatPercent(point.accuracy)}%</strong></div><div className="progress-track"><i style={{ width: `${point.accuracy * 100}%` }} /></div></div>)}</div>{!overview?.knowledge_points.length && <EmptyMessage text="完成作业后生成知识点统计。" />}</section><section className="panel glass-panel focus-panel"><div className="panel-heading"><div><span className="eyebrow">最近作业</span><h3>班级统一作业</h3></div><button className="link-button" onClick={onAssignments}>查看全部</button></div>{assignments.slice(0, 3).map((assignment) => <button className="mini-assignment clickable-card" key={assignment.id} onClick={onAssignments}><div className="mini-assignment-icon"><ClipboardCheck size={16} /></div><div><strong>{assignment.title}</strong><span>{assignment.submission_count} 人已完成 · 平均 {formatScore(assignment.average_score)} 分</span></div><span className="arrow">→</span></button>)}</section></div>
    {weakPoint && <div className="insight-strip"><AlertCircle size={17} /><span>当前班级正确率最低的知识点是 <strong>{weakPoint.name}</strong>，整体正确率为 {formatPercent(weakPoint.accuracy)}%。</span><button onClick={onAnalytics}>查看依据</button></div>}
  </>;
}

function Metric({ icon, label, value, suffix, detail, tone, clickable, onClick }: { icon: React.ReactNode; label: string; value: string; suffix: string; detail: string; tone: string; clickable?: boolean; onClick?: () => void }) { const content = <><div className={`metric-icon ${tone}`}>{icon}</div><div className="metric-copy"><span>{label}</span><div><strong>{value}</strong><small>{suffix}</small></div><em>{detail}</em></div></>; return clickable ? <button className="metric-card clickable-card" onClick={onClick}>{content}</button> : <div className="metric-card">{content}</div>; }

function StudentDetail({ student, overview, className, onBack }: { student: Student; overview: StudentLearningOverview; className: string; onBack: () => void }) { const focus = overview.profiles.filter((profile) => profile.attention_status === "重点关注"); return <><div className="page-heading"><div><button className="back-button" onClick={onBack}>← 返回学生列表</button><div className="eyebrow">学生学习画像</div><h1>{student.name}</h1><p>{student.student_no} · {className} · 基于 {overview.assignment_count} 次作业记录</p></div><span className={focus.length ? "status-pill warning" : "status-pill success"}>{focus.length ? "重点关注" : "状态正常"}</span></div><div className="student-metric-grid"><SmallMetric label="历史平均分" value={formatScore(overview.average_score)} suffix="分" /><SmallMetric label="作业完成" value={formatPercent(overview.completion_rate)} suffix="%" /><SmallMetric label="知识点记录" value={String(overview.profiles.length)} suffix="项" /><SmallMetric label="重点问题" value={String(focus.length)} suffix="项" /></div><div className="detail-grid"><section className="panel glass-panel profile-card"><div className="panel-heading"><div><span className="eyebrow">知识点画像</span><h3>掌握情况</h3></div><Gauge size={20} className="muted-icon" /></div><div className="profile-list">{overview.profiles.map((profile) => <div className="profile-row" key={profile.id}><div className="profile-row-title"><span>{profile.knowledge_point.name}</span><em className={profile.attention_status === "重点关注" ? "warning-text" : ""}>{profile.attention_status}</em></div><div className="profile-bar"><i style={{ width: `${profile.accuracy * 100}%` }} /></div><div className="profile-row-meta"><span>正确率 {formatPercent(profile.accuracy)}% · 最近 {formatPercent(profile.recent_accuracy)}%</span><span>{profile.trend}</span></div></div>)}</div></section><section className="panel glass-panel next-card"><div className="panel-heading"><div><span className="eyebrow">最近答题</span><h3>学习记录</h3></div><span className="status-pill neutral">逐题保留</span></div><div className="record-list">{overview.records.slice(0, 8).map((record) => <div className="record-row" key={record.id}><span className={`record-result ${record.is_correct ? "correct" : "wrong"}`}>{record.is_correct ? <CheckCircle2 size={14} /> : "×"}</span><div><strong>{record.knowledge_point_name}</strong><span>{record.assignment_title}</span></div><em>{record.is_correct ? "正确" : "错误"}</em></div>)}</div></section></div></>; }
function SmallMetric({ label, value, suffix }: { label: string; value: string; suffix: string }) { return <div className="small-metric glass-panel"><span>{label}</span><div><strong>{value}</strong><small>{suffix}</small></div></div>; }

function AssignmentsPage({ assignments, onAssignment }: { assignments: AssignmentSummary[]; onAssignment: (assignment: AssignmentSummary) => void }) { return <><div className="page-heading"><div><div className="eyebrow">教学数据 / 班级统一作业</div><h1>作业管理</h1><p>查看已经完成的班级统一作业、提交情况和程序统计结果。</p></div><span className="count-badge">{assignments.length} 次作业</span></div><div className="assignment-grid">{assignments.map((assignment) => <button className="assignment-card glass-panel clickable-card" key={assignment.id} onClick={() => onAssignment(assignment)}><div className="assignment-card-top"><span className="assignment-icon"><ClipboardCheck size={18} /></span><span className="status-pill neutral">{assignmentStatus(assignment.status)}</span></div><h3>{assignment.title}</h3><p>{formatDate(assignment.assigned_at)} · {assignmentMode(assignment.mode)}</p><div className="assignment-stats"><div><strong>{assignment.question_count}</strong><span>题目</span></div><div><strong>{assignment.submission_count}</strong><span>份提交</span></div><div><strong>{formatScore(assignment.average_score)}</strong><span>平均分</span></div></div><div className="assignment-card-footer"><span>查看作业与逐题记录</span><span>→</span></div></button>)}</div></>; }

function AssignmentDetailPage({ assignment, onBack, students, onUpdated }: { assignment: AssignmentDetail; onBack: () => void; students: Student[]; onUpdated: () => Promise<void> }) {
  const [studentId, setStudentId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [works, setWorks] = useState<import("./api/client").StudentWorks | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    api.getAssignmentStudentWorks(assignment.id).then(setWorks).catch((reason: Error) => setError(reason.message));
  }, [assignment.id]);
  const run = async (action: () => Promise<void>) => {
    setBusy(true); setError("");
    try { await action(); } catch (reason) { setError(reason instanceof Error ? reason.message : "操作失败"); }
    finally { setBusy(false); }
  };
  const upload = () => run(async () => {
    if (!studentId || !file) return;
    const next = await api.uploadAssignmentStudentWork(assignment.id, Number(studentId), file);
    setWorks(next);
    setFile(null);
  });
  const refreshWorks = () => run(async () => setWorks(await api.getAssignmentStudentWorks(assignment.id)));
  const confirmWork = (id: number) => run(async () => {
    await api.confirmAssignmentStudentWork(assignment.id, id);
    await onUpdated();
    setWorks(await api.getAssignmentStudentWorks(assignment.id));
  });
  const selectedStudent = students.find((student) => student.id === Number(studentId));
  const demoForZhang = !!works?.demo_upload_enabled && selectedStudent?.name === "张同学" && selectedStudent.student_no === "G1-001";
  const simulatedIds = new Set(works?.works.filter((work) => work.demo_simulated && work.status === "graded").map((work) => work.student_id));
  return <>
    <div className="page-heading">
      <div><button className="back-button" onClick={onBack}>← 返回作业管理</button><div className="eyebrow">作业详情 / 班级统一作业</div><h1>{assignment.title}</h1><p>{formatDate(assignment.assigned_at)} · {assignment.submission_count} 份提交 · 平均 {formatScore(assignment.average_score)} 分</p></div>
      <span className="status-pill neutral">{assignmentStatus(assignment.status)}</span>
    </div>
    <div className="assignment-detail-grid">
      <section className="panel glass-panel">
        <div className="panel-heading"><div><span className="eyebrow">题目内容</span><h3>共 {assignment.questions.length} 题</h3></div><span className="status-pill success"><i />已保留知识点</span></div>
        {assignment.questions.map((question) => <div className="question-row" key={question.question_id}><div className="question-number">{question.order_no}</div><div><strong>{question.stem}</strong><div className="question-meta">{question.knowledge_point_names.join(" · ")} · {question.difficulty}</div></div></div>)}
      </section>
      <section className="panel glass-panel">
        <div className="panel-heading"><div><span className="eyebrow">提交概览</span><h3>学生作答</h3></div><span className="status-pill neutral">逐题记录</span></div>
        <div className="submission-list">{assignment.submissions.map((submission) => <details className="submission-entry" key={submission.id}><summary className="submission-row"><div className="student-avatar">{submission.student_name.slice(0, 1)}</div><div><strong>{submission.student_name}{simulatedIds.has(submission.student_id) && <span className="demo-inline">演示模拟</span>}</strong><span>{submission.answers.filter((answer) => answer.is_correct).length} / {submission.answers.length} 题正确</span></div><b>{formatScore(submission.total_score)}</b></summary><div className="answer-list">{submission.answers.map((answer, index) => <div className="answer-row" key={answer.question_id}><span>第 {index + 1} 题 · {answer.knowledge_point_names.join("、")}</span><strong>{answer.answer_text}</strong><em className={answer.is_correct ? "answer-correct" : "answer-wrong"}>{answer.is_correct ? "正确" : "错误"}</em></div>)}</div></details>)}</div>
      </section>
    </div>
    <section className="panel glass-panel upload-panel">
      <div className="panel-heading"><div><span className="eyebrow">课后批改</span><h3>上传学生作业并更新学情</h3></div><button className="secondary-button" onClick={refreshWorks}>查看待确认</button></div>
      <div className="form-actions"><select value={studentId} onChange={(event) => setStudentId(event.target.value)}><option value="">选择学生</option>{students.filter((student) => student.status === "在读").map((student) => <option key={student.id} value={student.id}>{student.name}</option>)}</select><input key={studentId} type="file" accept={demoForZhang ? ".pdf" : ".pdf,.docx,.txt"} onChange={(event) => setFile(event.target.files?.[0] ?? null)} /><button className="primary-button" disabled={busy || !studentId || !file || (demoForZhang && !file.name.toLowerCase().endsWith(".pdf"))} onClick={upload}>{demoForZhang ? "上传演示 PDF" : "上传并识别"}</button></div>
      {demoForZhang && <div className="demo-disclosure" role="note">演示模拟批改：上传 PDF 后使用与本作业题目对应的预设示例答案；不解析 PDF 中的学生作答。教师确认后，模拟记录将计入张同学画像。</div>}
      {error && <div className="form-error">{error}</div>}
      {works?.works.map((work) => <div className="submission-row" key={work.id}><div>{work.file_name}{work.demo_simulated && <span className="demo-inline">演示模拟，非 PDF 识别结果</span>}</div><div>{work.status === "pending_review" ? "待教师确认" : "已计入学情"}</div>{work.score !== null && <b>{work.score} 分</b>}{work.status === "pending_review" && <button className="secondary-button" onClick={() => confirmWork(work.id)}>{work.demo_simulated ? "确认模拟批改并更新画像" : "确认批改并更新画像"}</button>}</div>)}
    </section>
  </>;
}

function AnalyticsPage({ overview, students, studentOverviews, onStudent }: { overview: ClassLearningOverview | null; students: Student[]; studentOverviews: Record<number, StudentLearningOverview>; onStudent: (student: Student) => void }) { const attention = students.filter((student) => studentOverviews[student.id]?.profiles.some((profile) => profile.attention_status === "重点关注")); return <><div className="page-heading"><div><div className="eyebrow">班级数据 / 学习画像</div><h1>学情分析</h1><p>统计结果由程序根据学生逐题学习记录计算，文字判断交由后续 AI 教学服务处理。</p></div><span className="count-badge">{overview?.assignment_count ?? 0} 次作业</span></div><div className="analytics-top"><SmallMetric label="班级平均分" value={formatScore(overview?.average_score)} suffix="分" /><SmallMetric label="完成率" value={formatPercent(overview?.completion_rate)} suffix="%" /><SmallMetric label="薄弱知识点" value={overview?.knowledge_points[0]?.name ?? "--"} suffix="" /><SmallMetric label="待关注学生" value={String(overview?.attention_students ?? 0)} suffix="人" /></div><div className="analytics-grid"><section className="panel glass-panel"><div className="panel-heading"><div><span className="eyebrow">知识点表现</span><h3>班级正确率</h3></div><span className="status-pill neutral">程序计算</span></div><div className="analytics-bars">{overview?.knowledge_points.map((point) => <div className="analytics-bar-row" key={point.knowledge_point_id}><div><span>{point.name}</span><strong>{formatPercent(point.accuracy)}%</strong></div><div className="progress-track"><i style={{ width: `${point.accuracy * 100}%` }} /></div><small>{point.correct_count} / {point.attempts} 次正确</small></div>)}</div></section><section className="panel glass-panel"><div className="panel-heading"><div><span className="eyebrow">需要关注</span><h3>持续性问题学生</h3></div><AlertCircle size={19} className="warning-icon" /></div>{attention.length ? <div className="attention-list">{attention.map((student) => { const focus = studentOverviews[student.id].profiles.find((profile) => profile.attention_status === "重点关注"); return <button className="attention-row clickable-card" key={student.id} onClick={() => onStudent(student)}><div className="student-avatar">{student.name.slice(0, 1)}</div><div><strong>{student.name}</strong><span>{focus?.knowledge_point.name} · 最近 {formatPercent(focus?.recent_accuracy)}%</span></div><span>查看 →</span></button>; })}</div> : <EmptyMessage text="当前没有达到重点关注规则的学生。" />}</section></div></>; }

function EmptyMessage({ text }: { text: string }) { return <div className="empty-message"><div className="empty-icon"><BarChart3 size={19} /></div><span>{text}</span></div>; }
function Placeholder({ label }: { label: string }) { return <div className="placeholder-page"><div className="placeholder-mark"><Sparkles size={24} /></div><div className="eyebrow">功能准备中</div><h1>{label}</h1><p>这个模块将在后续 Phase 中接入真实业务数据，当前先保留清晰的导航位置。</p></div>; }
function formatScore(value: number | null | undefined) { return value === null || value === undefined ? "--" : value.toFixed(1); }
function formatPercent(value: number | null | undefined) { return value === null || value === undefined ? "--" : `${(value * 100).toFixed(1)}`; }
function formatDate(value: string) { return new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(value)); }
function assignmentStatus(value: string) { return value === "analyzed" ? "已分析" : value; }
function assignmentMode(value: string) { return value === "class_unified" ? "班级统一作业" : value === "targeted_training" ? "个体专项训练" : value; }

export default App;
