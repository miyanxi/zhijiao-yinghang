import { useEffect, useState } from "react";
import { CheckCircle2, FileUp, Save, Upload } from "lucide-react";
import { api, type AssessmentImport, type ClassDetail } from "../api/client";

export function AssessmentPage({ classroom, onUpdated }: { classroom: ClassDetail; onUpdated: () => Promise<void> }) {
  const [items, setItems] = useState<AssessmentImport[]>([]);
  const [selected, setSelected] = useState<AssessmentImport | null>(null);
  const [title, setTitle] = useState("");
  const [paper, setPaper] = useState<File | null>(null);
  const [answerKey, setAnswerKey] = useState<File | null>(null);
  const [studentId, setStudentId] = useState(classroom.students[0]?.id ?? 0);
  const [work, setWork] = useState<File | null>(null);
  const [corrections, setCorrections] = useState<Record<number, Record<string, string>>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refresh = async (id?: number) => {
    const next = await api.getAssessmentImports(classroom.id);
    setItems(next);
    setSelected(next.find((item) => item.id === id) ?? next[0] ?? null);
  };
  useEffect(() => { refresh().catch((reason: Error) => setError(reason.message)); }, [classroom.id]);
  const run = async (action: () => Promise<void>) => {
    setBusy(true); setError("");
    try { await action(); } catch (reason) { setError(reason instanceof Error ? reason.message : "操作失败"); }
    finally { setBusy(false); }
  };
  const create = () => run(async () => {
    if (!paper || !answerKey || !title.trim()) return;
    const item = await api.createAssessmentImport(classroom.id, title, paper, answerKey);
    setTitle(""); setPaper(null); setAnswerKey(null); await refresh(item.id);
  });
  const approve = () => run(async () => { if (selected) await refresh((await api.approveAssessmentImport(selected.id)).id); });
  const updateQuestion = (questionId: number, field: "stem" | "answer" | "explanation" | "knowledge_point_names", value: string) => {
    if (!selected) return;
    setSelected({ ...selected, questions: selected.questions.map((question) => question.question_id === questionId ? {
      ...question, [field]: field === "knowledge_point_names" ? [value] : value,
    } : question) });
  };
  const saveQuestion = (questionId: number) => run(async () => {
    if (!selected) return;
    const question = selected.questions.find((item) => item.question_id === questionId);
    if (!question) return;
    const next = await api.correctImportedQuestion(selected.id, questionId, {
      stem: question.stem, answer: question.answer, explanation: question.explanation,
      knowledge_point_name: question.knowledge_point_names[0],
    });
    setItems((items) => items.map((item) => item.id === next.id ? next : item));
    setSelected(next);
  });
  const uploadWork = () => run(async () => {
    if (!selected || !work || !studentId) return;
    const next = await api.uploadStudentWork(selected.id, studentId, work);
    setWork(null); await refresh(next.id);
  });
  const confirmWork = (workId: number, answers: Record<string, string>) => run(async () => {
    if (!selected) return;
    await api.correctStudentWork(selected.id, workId, answers);
    const next = await api.confirmStudentWork(selected.id, workId);
    await refresh(next.id); await onUpdated();
  });
  const pendingStudents = classroom.students.filter((student) => student.status === "在读" && !selected?.works.some((item) => item.student_id === student.id));
  const saved = items.find((item) => item.id === selected?.id);
  const unsavedQuestions = !!selected && !!saved && JSON.stringify(selected.questions) !== JSON.stringify(saved.questions);

  return <>
    <div className="page-heading"><div><div className="eyebrow">作业评价 / 文件阅卷</div><h1>智能阅卷</h1><p>上传试卷与参考答案，再上传学生作业；教师核对识别结果后由程序评分并更新学情。</p></div></div>
    {error && <div className="form-error" role="alert">{error}</div>}
    <section className="panel glass-panel import-create">
      <div className="panel-heading"><div><span className="eyebrow">第一步</span><h3>导入试卷与参考答案</h3></div><span className="status-pill neutral">PDF / Word / TXT</span></div>
      <div className="form-two"><label className="field"><span>试卷名称</span><input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="例如：Unit 3 语法检测" /></label><label className="field"><span>试卷文件</span><input type="file" accept=".pdf,.docx,.txt" onChange={(event) => setPaper(event.target.files?.[0] ?? null)} /></label></div>
      <label className="field"><span>参考答案文件</span><input type="file" accept=".pdf,.docx,.txt" onChange={(event) => setAnswerKey(event.target.files?.[0] ?? null)} /></label>
      <div className="form-actions"><button className="primary-button" disabled={busy || !title.trim() || !paper || !answerKey} onClick={create}><FileUp size={15} />上传并识别</button></div>
    </section>
    <div className="workbench-grid">
      <aside className="panel glass-panel workbench-list"><div className="panel-heading"><div><span className="eyebrow">已导入试卷</span><h3>当前班级</h3></div><span className="count-badge">{items.length}</span></div>
        {items.map((item) => <button key={item.id} className={`workbench-list-item clickable-card ${selected?.id === item.id ? "selected" : ""}`} onClick={() => setSelected(item)}><strong>{item.title}</strong><span>{item.questions.length} 题 · {item.status === "approved" ? "已确认" : "待确认"}</span></button>)}
        {!items.length && <div className="data-pending">暂无导入试卷</div>}
      </aside>
      <section className="panel glass-panel form-panel"><div className="panel-heading"><div><span className="eyebrow">试卷与作答</span><h3>{selected?.title ?? "选择试卷"}</h3></div>{selected && <span className="status-pill neutral">{selected.status === "approved" ? "已确认" : "待教师确认"}</span>}</div>
        {selected && <>
          <div className="source-note">试卷：{selected.paper_file_name} · 参考答案：{selected.answer_key_file_name}</div>
          <div className="question-import-list">{selected.questions.map((question) => <div className="question-row" key={question.question_id}><span className="question-number">{question.order_no}</span><div className="import-question-fields"><span className="question-meta">{question.type === "fill_blank" ? "填空题" : question.type === "multiple_choice" ? "多选题" : "单选题"}</span>{selected.status === "draft" ? <><label className="field"><span>题干</span><textarea value={question.stem} onChange={(event) => updateQuestion(question.question_id, "stem", event.target.value)} /></label><div className="form-two"><label className="field"><span>参考答案</span><input value={question.answer} onChange={(event) => updateQuestion(question.question_id, "answer", event.target.value)} /></label><label className="field"><span>知识点</span><input value={question.knowledge_point_names[0] ?? ""} onChange={(event) => updateQuestion(question.question_id, "knowledge_point_names", event.target.value)} /></label></div><label className="field"><span>解析</span><textarea value={question.explanation} onChange={(event) => updateQuestion(question.question_id, "explanation", event.target.value)} /></label><button className="secondary-button" disabled={busy} onClick={() => void saveQuestion(question.question_id)}><Save size={15} />保存第 {question.order_no} 题</button></> : <><strong>{question.stem}</strong><small>{question.knowledge_point_names.join("、")} · 标准答案：{question.answer}</small></>}</div></div>)}</div>
          {selected.status !== "approved" && <button className="primary-button" disabled={busy || unsavedQuestions} onClick={approve}><CheckCircle2 size={15} />教师确认试卷与答案</button>}
          {selected.status === "approved" && <>
            <div className="file-upload-row"><label className="field"><span>学生</span><select value={pendingStudents.some((student) => student.id === studentId) ? studentId : (pendingStudents[0]?.id ?? "")} onChange={(event) => setStudentId(Number(event.target.value))}>{pendingStudents.map((student) => <option key={student.id} value={student.id}>{student.name} · {student.student_no}</option>)}</select></label><label className="field"><span>学生作业文件</span><input type="file" accept=".pdf,.docx,.txt,.png,.jpg,.jpeg" onChange={(event) => setWork(event.target.files?.[0] ?? null)} /></label><button className="secondary-button" disabled={busy || !work || !pendingStudents.length} onClick={uploadWork}><Upload size={15} />上传作业</button></div>
            <div className="submission-list">{selected.works.map((item) => {
              const answers = corrections[item.id] ?? item.extracted_answers;
              return <div className="uploaded-work" key={item.id}><div className="submission-row"><div className="student-avatar">{classroom.students.find((student) => student.id === item.student_id)?.name.slice(0, 1)}</div><div><strong>{classroom.students.find((student) => student.id === item.student_id)?.name}</strong><span>{item.file_name} · {item.status === "graded" ? `已评分 ${item.score?.toFixed(1)} 分` : "待教师核对"}</span></div></div>
                {item.status === "pending_review" && <><div className="extracted-answer-list">{selected.questions.map((question) => <label className="field" key={question.question_id}><span>第 {question.order_no} 题 · {question.stem}</span><input value={answers[String(question.order_no)] ?? ""} onChange={(event) => setCorrections({ ...corrections, [item.id]: { ...answers, [String(question.order_no)]: event.target.value } })} /></label>)}</div><div className="form-actions"><button className="primary-button" disabled={busy || selected.questions.some((question) => !(answers[String(question.order_no)] ?? "").trim())} onClick={() => void confirmWork(item.id, answers)}><Save size={15} />核对并确认评分</button></div></>}
              </div>;
            })}</div>
          </>}
        </>}
      </section>
    </div>
  </>;
}
