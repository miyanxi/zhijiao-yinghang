import { useEffect, useState } from "react";
import { Check, ClipboardCheck, Download, RotateCw, Save, Sparkles, Trash2 } from "lucide-react";
import { api, downloadPdf, type AssignmentDraft, type DraftQuestion, type KnowledgePoint, type TeachingGoal, type StudentWorks } from "../api/client";

export function SmartAssignmentsPage({ classId, onPublished }: { classId: number; onPublished: () => Promise<void> }) {
  const [goals, setGoals] = useState<TeachingGoal[]>([]);
  const [points, setPoints] = useState<KnowledgePoint[]>([]);
  const [drafts, setDrafts] = useState<AssignmentDraft[]>([]);
  const [selected, setSelected] = useState<AssignmentDraft | null>(null);
  const [goalId, setGoalId] = useState<number | null>(null);
  const [count, setCount] = useState(5);
  const [difficulty, setDifficulty] = useState("中等");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [studentWorks, setStudentWorks] = useState<StudentWorks | null>(null);
  const [studentId, setStudentId] = useState<number | null>(null);

  useEffect(() => {
    Promise.all([api.getGoals(classId), api.getKnowledgePoints(), api.getAssignmentDrafts(classId)])
      .then(([goalItems, catalog, draftItems]) => {
        const confirmed = goalItems.filter((item) => item.status === "confirmed");
        setGoals(confirmed);
        const initialGoalId = confirmed[0]?.id ?? null;
        setGoalId(initialGoalId);
        setPoints(catalog);
        setDrafts(draftItems);
        setSelected(draftItems.find((item) => item.teaching_goal_id === initialGoalId) ?? null);
      })
      .catch((reason: Error) => setError(reason.message));
  }, [classId]);

  const run = async (action: () => Promise<void>) => {
    setBusy(true); setError("");
    try { await action(); } catch (reason) { setError(reason instanceof Error ? reason.message : "操作失败"); }
    finally { setBusy(false); }
  };

  const refresh = async (id: number) => {
    const items = await api.getAssignmentDrafts(classId);
    setDrafts(items);
    setSelected(items.find((item) => item.id === id) ?? null);
  };

  const generate = () => run(async () => {
    if (!goalId) return;
    setSelected(null);
    const created = await api.generateAssignmentDraft(goalId, count, difficulty);
    await refresh(created.id);
  });

  const selectGoal = (id: number) => {
    setGoalId(id);
    setError("");
    setSelected(drafts.find((draft) => draft.teaching_goal_id === id) ?? null);
  };

  const visibleDrafts = drafts.filter((draft) => draft.teaching_goal_id === goalId);

  const updateQuestion = (questionId: number, patch: Partial<DraftQuestion>) => {
    if (!selected) return;
    setSelected({ ...selected, questions: selected.questions.map((question) =>
      question.id === questionId ? { ...question, ...patch } : question,
    ) });
  };

  const questionFields = (question: DraftQuestion) => ({
    stem: question.stem, options: question.options, answer: question.answer,
    explanation: question.explanation, knowledge_point_id: question.knowledge_point_id,
    difficulty: question.difficulty,
  });

  const questionAction = (question: DraftQuestion, action: "save" | "check" | "regenerate" | "delete") => run(async () => {
    if (!selected) return;
    let updated: AssignmentDraft;
    if (action === "save") updated = await api.updateDraftQuestion(selected.id, question.id, questionFields(question));
    else if (action === "check") {
      await api.updateDraftQuestion(selected.id, question.id, questionFields(question));
      updated = await api.checkDraftQuestion(selected.id, question.id);
    } else if (action === "regenerate") updated = await api.regenerateDraftQuestion(selected.id, question.id);
    else updated = await api.deleteDraftQuestion(selected.id, question.id);
    await refresh(updated.id);
  });

  const review = (action: "submit" | "approve") => run(async () => {
    if (!selected) return;
    if (action === "submit") {
      const saved = drafts.find((item) => item.id === selected.id);
      for (const question of selected.questions) {
        const original = saved?.questions.find((item) => item.id === question.id);
        if (!original || JSON.stringify(questionFields(question)) !== JSON.stringify(questionFields(original))) {
          await api.updateDraftQuestion(selected.id, question.id, questionFields(question));
          await api.checkDraftQuestion(selected.id, question.id);
        }
      }
    }
    const updated = action === "submit" ? await api.submitAssignmentReview(selected.id) : await api.approveAssignmentDraft(selected.id);
    await refresh(updated.id);
  });

  const publish = () => run(async () => {
    if (!selected || selected.status !== "approved") return;
    await api.publishAssignment(selected.id);
    await refresh(selected.id);
    await onPublished();
  });

  const locked = selected?.status === "approved" || selected?.status === "published";

  return <>
    <div className="page-heading"><div><div className="eyebrow">教学准备 / 智能作业</div><h1>智能作业</h1><p>每次生成均调用 DeepSeek，围绕所选课程目标生成多题型班级统一作业。</p></div><div className="heading-actions"><span className="status-pill neutral">班级统一模式</span>{selected && <><button className="secondary-button" disabled={busy} onClick={() => void run(() => downloadPdf(`/assignment-drafts/${selected.id}/pdf`, `班级统一作业-${selected.id}.pdf`))}><Download size={15} />PDF</button><button className="secondary-button" disabled={busy} onClick={() => void run(() => downloadPdf(`/assignment-drafts/${selected.id}/docx`, `班级统一作业-${selected.id}.docx`))}>Word</button></>}{selected?.status === "draft" && <button className="icon-button" title="删除整份作业" aria-label="删除整份作业" onClick={() => void run(async () => { if (!window.confirm("确定删除整份作业吗？")) return; await api.deleteAssignmentDraft(selected.id); const items = await api.getAssignmentDrafts(classId); setDrafts(items); setSelected(items[0] ?? null); })}><Trash2 size={15} /></button>}{selected?.status === "approved" && <button className="primary-button" disabled={busy} onClick={publish}>教师发布作业</button>}{selected?.status === "published" && <span className="status-pill success">已发布</span>}</div></div>
    <section className="panel glass-panel generation-bar"><label className="field"><span>已确认教学目标</span><select value={goalId ?? ""} onChange={(event) => selectGoal(Number(event.target.value))}>{goals.length ? goals.map((goal) => <option value={goal.id} key={goal.id}>{goal.topic}</option>) : <option value="">请先确认教学目标</option>}</select></label><label className="field"><span>题量</span><input type="number" min={3} max={20} value={count} onChange={(event) => setCount(Number(event.target.value))} /></label><label className="field"><span>难度</span><select value={difficulty} onChange={(event) => setDifficulty(event.target.value)}><option>基础</option><option>中等</option><option>提高</option></select></label><button className="primary-button" disabled={busy || !goalId || count < 3 || count > 20} onClick={generate}><Sparkles size={15} />生成统一作业草稿</button></section>
    <div className="workbench-grid">
      <aside className="panel glass-panel workbench-list"><div className="panel-heading"><div><span className="eyebrow">作业草稿</span><h3>当前教学目标</h3></div><span className="count-badge">{visibleDrafts.length}</span></div>{visibleDrafts.map((draft) => <button key={draft.id} className={`workbench-list-item clickable-card ${selected?.id === draft.id ? "selected" : ""}`} onClick={() => setSelected(draft)}><strong>{draft.title}</strong><span>{draft.questions.length} 题 · {statusText(draft.status)}</span></button>)}{!visibleDrafts.length && <div className="data-pending">当前目标暂无作业草稿</div>}</aside>
      <section className="panel glass-panel form-panel"><div className="panel-heading"><div><span className="eyebrow">题目检查与教师审核</span><h3>{selected?.title ?? "等待生成"}</h3></div>{selected && <span className="status-pill neutral">{statusText(selected.status)}</span>}</div>
        {error && <div className="form-error" role="alert">{error}</div>}
        {selected ? <>
          <div className="source-note">{selected.status === "published" ? "这套统一作业已经发布，题目与答案不可再修改。" : selected.source === "demo" ? "当前为演示生成和程序校验；正式 AI 质量检查需配置 DeepSeek。教师审核后才可发布。" : "题目经过程序与 AI 质量检查，教师仍需核对答案和解析后发布。"}</div>
          <div className="form-actions top-actions">{selected.status === "draft" && <button className="primary-button" disabled={busy} onClick={() => review("submit")}>提交教师审核</button>}{selected.status === "pending_review" && <button className="primary-button" disabled={busy} onClick={() => review("approve")}><Check size={15} />教师确认作业</button>}{selected.status === "approved" && <span className="status-pill success">已审核，尚未发布</span>}</div>
          <div className="question-editor-list">{selected.questions.map((question) => <article className="question-editor" key={question.id}><div className="question-editor-header"><div><span className="question-number">{question.order_no}</span><strong>{question.type === "multiple_choice" ? "多项选择题" : question.type === "fill_blank" ? "填空题" : "单项选择题"}</strong></div><span className={`quality-badge ${question.quality_status === "needs_revision" ? "needs-work" : ""}`}>{qualityText(question.quality_status)}</span></div>
            <label className="field"><span>题干</span><textarea rows={2} value={question.stem} disabled={locked} onChange={(event) => updateQuestion(question.id, { stem: event.target.value })} /></label>
            <div className="option-grid">{question.options.map((option, index) => <label className="field" key={index}><span>选项 {String.fromCharCode(65 + index)}</span><input value={option} disabled={locked} onChange={(event) => updateQuestion(question.id, { options: question.options.map((item, itemIndex) => itemIndex === index ? event.target.value : item) })} /></label>)}</div>
            <div className="form-two"><label className="field"><span>标准答案{question.type === "multiple_choice" ? "（多个答案用 || 分隔）" : ""}</span>{question.type === "single_choice" ? <select value={question.answer} disabled={locked} onChange={(event) => updateQuestion(question.id, { answer: event.target.value })}>{question.options.map((option, index) => <option key={index} value={option}>{String.fromCharCode(65 + index)} · {option}</option>)}</select> : <input value={question.answer} disabled={locked} onChange={(event) => updateQuestion(question.id, { answer: event.target.value })} />}</label><label className="field"><span>知识点</span><select value={question.knowledge_point_id} disabled={locked} onChange={(event) => updateQuestion(question.id, { knowledge_point_id: Number(event.target.value) })}>{points.map((point) => <option value={point.id} key={point.id}>{point.name}</option>)}</select></label></div>
            <label className="field"><span>解析</span><textarea rows={2} value={question.explanation} disabled={locked} onChange={(event) => updateQuestion(question.id, { explanation: event.target.value })} /></label>
            {!!question.quality_issues.length && <div className="quality-issues">{question.quality_issues.join("；")}</div>}
            {!locked && <div className="section-tools"><button title="保存题目" aria-label={`保存第${question.order_no}题`} disabled={busy} onClick={() => questionAction(question, "save")}><Save size={15} /></button><button title="重新检查题目" aria-label={`检查第${question.order_no}题`} disabled={busy} onClick={() => questionAction(question, "check")}><ClipboardCheck size={15} /></button><button title="重新生成题目" aria-label={`重新生成第${question.order_no}题`} disabled={busy} onClick={() => questionAction(question, "regenerate")}><RotateCw size={15} /></button><button title="删除题目" aria-label={`删除第${question.order_no}题`} disabled={busy} onClick={() => questionAction(question, "delete")}><Trash2 size={15} /></button></div>}
          </article>)}</div>
        </> : <div className="empty-message">选择已确认目标后生成班级统一作业。</div>}
      </section>
    </div>
  </>;
}

function statusText(status: string) { return status === "published" ? "已发布" : status === "approved" ? "已审核" : status === "pending_review" ? "待教师审核" : "草稿"; }
function qualityText(status: string) { return status === "demo_checked" ? "演示校验" : status === "passed" ? "检查通过" : status === "needs_revision" ? "需要修改" : "待重新检查"; }
