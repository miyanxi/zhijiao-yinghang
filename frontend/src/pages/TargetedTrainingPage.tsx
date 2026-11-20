import { useEffect, useState } from "react";
import { Check, ClipboardCheck, RotateCw, Save, Sparkles } from "lucide-react";
import { api, type AssignmentDetail, type ClassDetail, type TargetedTraining, type TrainingCandidate, type TrainingQuestion } from "../api/client";

const percent = (value: number | null) => value === null ? "--" : `${(value * 100).toFixed(1)}%`;
const statusText = (status: string) => ({ confirmed: "教师已确认", draft: "题目草稿", pending_review: "待教师审核", approved: "已审核", published: "训练中", completed: "已再评价" })[status] ?? status;
const qualityText = (status: string) => ({ demo_checked: "演示校验", passed: "检查通过", needs_revision: "需要修改", unchecked: "待重新检查" })[status] ?? status;

export function TargetedTrainingPage({ classroom, suggestion, onUpdated }: { classroom: ClassDetail; suggestion?: { studentId: number; knowledgePointId: number; durationMinutes: number | null; questionCount: number | null } | null; onUpdated: () => Promise<void> }) {
  const [candidates, setCandidates] = useState<TrainingCandidate[]>([]);
  const [trainings, setTrainings] = useState<TargetedTraining[]>([]);
  const [selected, setSelected] = useState<TargetedTraining | null>(null);
  const [detail, setDetail] = useState<AssignmentDetail | null>(null);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [questionCount, setQuestionCount] = useState(10);
  const [duration, setDuration] = useState(15);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState("");

  useEffect(() => {
    Promise.all([api.getTrainingCandidates(classroom.id), api.getTargetedTrainings(classroom.id)])
      .then(([candidateItems, trainingItems]) => {
        setCandidates(candidateItems);
        setTrainings(trainingItems);
        setSelected(trainingItems[0] ?? null);
      })
      .catch((reason: Error) => setError(reason.message));
  }, [classroom.id]);

  useEffect(() => {
    if (suggestion?.durationMinutes) setDuration(suggestion.durationMinutes);
    if (suggestion?.questionCount) setQuestionCount(suggestion.questionCount);
  }, [suggestion]);

  useEffect(() => {
    setDetail(null); setAnswers({});
    if (!selected?.assignment_id) return;
    api.getAssignment(selected.assignment_id).then(setDetail).catch((reason: Error) => setError(reason.message));
  }, [selected?.assignment_id]);

  const refresh = async (id: number) => {
    const [candidateItems, trainingItems] = await Promise.all([
      api.getTrainingCandidates(classroom.id), api.getTargetedTrainings(classroom.id),
    ]);
    setCandidates(candidateItems);
    setTrainings(trainingItems);
    setSelected(trainingItems.find((item) => item.id === id) ?? null);
  };

  const run = async (action: () => Promise<void>) => {
    setBusy(true); setError("");
    try { await action(); } catch (reason) { setError(reason instanceof Error ? reason.message : "操作失败"); }
    finally { setBusy(false); }
  };

  const confirm = (candidate: TrainingCandidate) => run(async () => {
    const created = await api.confirmTargetedTraining(candidate.student_id, candidate.knowledge_point_id, questionCount, duration);
    await refresh(created.id);
  });

  const act = (action: "generate" | "submit" | "approve" | "publish") => run(async () => {
    if (!selected) return;
    let updated: TargetedTraining;
    if (action === "generate") updated = await api.generateTargetedTraining(selected.id);
    else if (action === "submit") {
      const saved = trainings.find((item) => item.id === selected.id);
      for (const question of selected.questions) {
        const original = saved?.questions.find((item) => item.order_no === question.order_no);
        if (!original || JSON.stringify(questionFields(question)) !== JSON.stringify(questionFields(original))) {
          await api.updateTrainingQuestion(selected.id, question.order_no, questionFields(question));
          await api.checkTrainingQuestion(selected.id, question.order_no);
        }
      }
      updated = await api.submitTrainingReview(selected.id);
    } else if (action === "approve") updated = await api.approveTargetedTraining(selected.id);
    else updated = await api.publishTargetedTraining(selected.id);
    await refresh(updated.id);
  });

  const questionFields = (question: TrainingQuestion) => ({
    stem: question.stem, options: question.options, answer: question.answer,
    explanation: question.explanation, difficulty: question.difficulty,
  });

  const updateLocalQuestion = (orderNo: number, patch: Partial<TrainingQuestion>) => {
    if (!selected) return;
    setSelected({ ...selected, questions: selected.questions.map((item) =>
      item.order_no === orderNo ? { ...item, ...patch } : item,
    ) });
  };

  const saveQuestion = (question: TrainingQuestion, check: boolean) => run(async () => {
    if (!selected) return;
    await api.updateTrainingQuestion(selected.id, question.order_no, questionFields(question));
    const updated = check ? await api.checkTrainingQuestion(selected.id, question.order_no) : await api.getTargetedTraining(selected.id);
    await refresh(updated.id);
  });

  const submitAnswers = () => run(async () => {
    if (!selected?.assignment_id || !detail) return;
    const submission = await api.submitAnswers(selected.assignment_id, selected.student_id,
      detail.questions.map((question) => ({ question_id: question.question_id, answer_text: answers[question.question_id] })));
    setResult(`${selected.student_name}：${submission.total_score.toFixed(1)} 分，${submission.answers.filter((item) => item.is_correct).length} / ${submission.answers.length} 题正确`);
    setDetail(await api.getAssignment(selected.assignment_id));
    await refresh(selected.id);
    await onUpdated();
  });

  const locked = selected?.status !== "draft" && selected?.status !== "pending_review";
  const delta = selected?.status === "completed" && selected.current_recent_accuracy !== null
    ? selected.current_recent_accuracy - selected.baseline_recent_accuracy : null;

  return <>
    <div className="page-heading"><div><div className="eyebrow">学情干预 / 个体专项训练</div><h1>专项训练</h1><p>仅对程序识别出持续性问题的少数学生，由教师确认后额外安排训练。</p></div></div>
    {error && <div className="form-error" role="alert">{error}</div>}
    <section className="training-candidates"><div className="panel-heading"><div><span className="eyebrow">学习画像筛选</span><h3>待教师确认</h3></div><span className="status-pill neutral">程序规则识别</span></div>
      <div className="training-controls"><label className="field"><span>题量</span><input type="number" min={3} max={20} value={questionCount} onChange={(event) => setQuestionCount(Number(event.target.value))} /></label><label className="field"><span>训练时间（分钟）</span><input type="number" min={5} max={60} value={duration} onChange={(event) => setDuration(Number(event.target.value))} /></label></div>
      <div className="candidate-list">{candidates.map((candidate) => { const active = trainings.some((item) => item.student_id === candidate.student_id && item.knowledge_point_id === candidate.knowledge_point_id && item.status !== "completed"); const suggested = suggestion?.studentId === candidate.student_id && suggestion.knowledgePointId === candidate.knowledge_point_id; return <div className={`candidate-row ${suggested ? "suggested" : ""}`} key={`${candidate.student_id}-${candidate.knowledge_point_id}`}><div className="student-avatar">{candidate.student_name.slice(0, 1)}</div><div><strong>{candidate.student_name} · {candidate.knowledge_point_name}</strong><span>近期正确率 {percent(candidate.recent_accuracy)} · 连续薄弱 {candidate.consecutive_weak_count} 次 · {candidate.total_attempts} 次练习记录</span></div><button className="secondary-button" disabled={busy || active || questionCount < 3 || questionCount > 20 || duration < 5 || duration > 60} onClick={() => confirm(candidate)}>{active ? "训练进行中" : "教师确认"}</button></div>; })}{!candidates.length && <div className="empty-message">当前没有符合持续性问题规则的学生。</div>}</div>
    </section>
    <div className="workbench-grid"><aside className="panel glass-panel workbench-list"><div className="panel-heading"><div><span className="eyebrow">干预记录</span><h3>专项训练</h3></div><span className="count-badge">{trainings.length}</span></div>{trainings.map((item) => <button className={`workbench-list-item clickable-card ${selected?.id === item.id ? "selected" : ""}`} key={item.id} onClick={() => { setSelected(item); setResult(""); }}><strong>{item.student_name} · {item.knowledge_point_name}</strong><span>{statusText(item.status)} · {item.question_count} 题 / {item.duration_minutes} 分钟</span></button>)}{!trainings.length && <div className="data-pending">教师确认对象后，训练记录会显示在这里。</div>}</aside>
      <section className="panel glass-panel form-panel"><div className="panel-heading"><div><span className="eyebrow">训练内容与再评价</span><h3>{selected ? `${selected.student_name} · ${selected.knowledge_point_name}` : "等待教师确认"}</h3></div>{selected && <span className="status-pill neutral">{statusText(selected.status)}</span>}</div>
        {selected && <><div className="training-baseline"><div><span>训练前总体正确率</span><strong>{percent(selected.baseline_accuracy)}</strong></div><div><span>训练前近期正确率</span><strong>{percent(selected.baseline_recent_accuracy)}</strong></div><div><span>当前近期正确率</span><strong>{selected.status === "completed" ? percent(selected.current_recent_accuracy) : "待再评价"}</strong></div><div><span>近期变化</span><strong>{delta === null ? "--" : `${delta >= 0 ? "+" : ""}${(delta * 100).toFixed(1)} 个百分点`}</strong></div></div>
          {selected.status === "completed" && <div className="grade-result"><Check size={17} />训练正确率 {percent(selected.training_accuracy)} · 得分 {selected.training_score?.toFixed(1)} 分</div>}
          {result && <div className="grade-result" role="status">{result}</div>}
          {selected.source === "demo" && <div className="source-note">演示题库与程序校验；教师须核对题目并最终审核。正式 AI 生成需配置 DeepSeek。</div>}
          <div className="form-actions top-actions">{selected.status === "confirmed" && <button className="primary-button" disabled={busy} onClick={() => act("generate")}><Sparkles size={15} />生成专项训练草稿</button>}{selected.status === "draft" && <button className="primary-button" disabled={busy} onClick={() => act("submit")}>提交教师审核</button>}{selected.status === "pending_review" && <button className="primary-button" disabled={busy} onClick={() => act("approve")}><Check size={15} />教师确认训练</button>}{selected.status === "approved" && <button className="primary-button" disabled={busy} onClick={() => act("publish")}>发布给目标学生</button>}</div>
          {selected.status === "published" && detail && <><div className="source-note">教师代录目标学生的演示作答，程序阅卷后更新长期画像。</div><div className="assessment-questions">{detail.questions.map((question) => <fieldset className="assessment-question" key={question.question_id}><legend>第 {question.order_no} 题</legend><strong>{question.stem}</strong><div className="answer-options">{question.options.map((option, index) => <label key={index}><input type="radio" name={`training-${question.question_id}`} checked={answers[question.question_id] === option} onChange={() => setAnswers({ ...answers, [question.question_id]: option })} /><span>{String.fromCharCode(65 + index)}. {option}</span></label>)}</div></fieldset>)}</div><div className="form-actions"><button className="primary-button" disabled={busy || detail.questions.some((question) => !answers[question.question_id])} onClick={submitAnswers}><ClipboardCheck size={15} />提交训练并再评价</button></div></>}
          {selected.status !== "published" && selected.status !== "completed" && <div className="question-editor-list">{selected.questions.map((question) => <article className="question-editor" key={question.order_no}><div className="question-editor-header"><div><span className="question-number">{question.order_no}</span><strong>单项选择题</strong></div><span className={`quality-badge ${question.quality_status === "needs_revision" ? "needs-work" : ""}`}>{qualityText(question.quality_status)}</span></div><label className="field"><span>题干</span><textarea rows={2} value={question.stem} disabled={locked} onChange={(event) => updateLocalQuestion(question.order_no, { stem: event.target.value })} /></label><div className="option-grid">{question.options.map((option, index) => <label className="field" key={index}><span>选项 {String.fromCharCode(65 + index)}</span><input value={option} disabled={locked} onChange={(event) => updateLocalQuestion(question.order_no, { options: question.options.map((item, itemIndex) => itemIndex === index ? event.target.value : item) })} /></label>)}</div><div className="form-two"><label className="field"><span>标准答案</span><select value={question.answer} disabled={locked} onChange={(event) => updateLocalQuestion(question.order_no, { answer: event.target.value })}>{question.options.map((option, index) => <option key={index} value={option}>{String.fromCharCode(65 + index)} · {option}</option>)}</select></label><label className="field"><span>难度</span><select value={question.difficulty} disabled={locked} onChange={(event) => updateLocalQuestion(question.order_no, { difficulty: event.target.value })}><option>基础</option><option>中等</option><option>提高</option></select></label></div><label className="field"><span>解析</span><textarea rows={2} value={question.explanation} disabled={locked} onChange={(event) => updateLocalQuestion(question.order_no, { explanation: event.target.value })} /></label>{!!question.quality_issues.length && <div className="quality-issues">{question.quality_issues.join("；")}</div>}{!locked && <div className="section-tools"><button title="保存本题" aria-label={`保存训练第${question.order_no}题`} disabled={busy} onClick={() => saveQuestion(question, false)}><Save size={15} /></button><button title="保存并检查本题" aria-label={`检查训练第${question.order_no}题`} disabled={busy} onClick={() => saveQuestion(question, true)}><RotateCw size={15} /></button></div>}</article>)}</div>}
        </>}
      </section>
    </div>
  </>;
}
