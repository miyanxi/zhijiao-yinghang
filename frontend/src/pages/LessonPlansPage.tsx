import { useEffect, useState } from "react";
import { Check, Download, RotateCw, Save, Sparkles, Trash2 } from "lucide-react";
import { api, downloadPdf, type LessonPlan, type TeachingGoal } from "../api/client";

function fitTextarea(element: HTMLTextAreaElement | null) {
  if (!element) return;
  element.style.height = "auto";
  element.style.height = `${element.scrollHeight}px`;
}

export function LessonPlansPage({ classId }: { classId: number }) {
  const [goals, setGoals] = useState<TeachingGoal[]>([]);
  const [plans, setPlans] = useState<LessonPlan[]>([]);
  const [selected, setSelected] = useState<LessonPlan | null>(null);
  const [goalId, setGoalId] = useState<number | null>(null);
  const [difficulty, setDifficulty] = useState("中等");
  const [duration, setDuration] = useState(45);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [evaluation, setEvaluation] = useState("");
  const [reflection, setReflection] = useState("");

  useEffect(() => {
    document.querySelectorAll<HTMLTextAreaElement>(".section-editor .auto-grow, .post-review .auto-grow").forEach(fitTextarea);
  }, [selected, evaluation, reflection]);

  useEffect(() => {
    Promise.all([api.getGoals(classId), api.getLessonPlans(classId)])
      .then(([goalItems, planItems]) => {
        const confirmed = goalItems.filter((goal) => goal.status === "confirmed");
        setGoals(confirmed);
        setGoalId(confirmed[0]?.id ?? null);
        setPlans(planItems);
        setSelected(planItems[0] ?? null);
        setEvaluation(planItems[0]?.post_evaluation ?? "");
        setReflection(planItems[0]?.post_reflection ?? "");
      })
      .catch((reason: Error) => setError(reason.message));
  }, [classId]);

  const run = async (action: () => Promise<void>) => {
    setBusy(true); setError("");
    try { await action(); } catch (reason) { setError(reason instanceof Error ? reason.message : "操作失败"); }
    finally { setBusy(false); }
  };
  const refresh = async (id: number) => {
    const items = await api.getLessonPlans(classId);
    setPlans(items);
    const next = items.find((item) => item.id === id) ?? null;
    setSelected(next);
    setEvaluation(next?.post_evaluation ?? "");
    setReflection(next?.post_reflection ?? "");
  };
  const generate = () => run(async () => {
    if (!goalId) return;
    const plan = await api.generateLessonPlan(goalId, difficulty, duration);
    await refresh(plan.id);
  });
  const saveSettings = () => run(async () => {
    if (!selected) return;
    const updated = await api.updateLessonPlan(selected.id, { title: selected.title, difficulty: selected.difficulty, duration_minutes: selected.duration_minutes });
    await refresh(updated.id);
  });
  const sectionAction = (key: string, action: "save" | "regenerate" | "delete") => run(async () => {
    if (!selected) return;
    const section = selected.sections.find((item) => item.key === key);
    if (!section) return;
    const updated = action === "save"
      ? await api.updateLessonSection(selected.id, key, { content: section.content, duration_minutes: section.duration_minutes })
      : action === "regenerate"
        ? await api.regenerateLessonSection(selected.id, key)
        : await api.deleteLessonSection(selected.id, key);
    await refresh(updated.id);
  });

  const saveReview = () => run(async () => {
    if (!selected) return;
    const updated = await api.savePostReview(selected.id, evaluation, reflection);
    setSelected(updated);
  });
  const statusAction = (action: "submit" | "approve") => run(async () => {
    if (!selected) return;
    if (action === "submit") {
      await api.updateLessonPlan(selected.id, { title: selected.title, difficulty: selected.difficulty, duration_minutes: selected.duration_minutes });
      const saved = plans.find((plan) => plan.id === selected.id);
      for (const section of selected.sections) {
        const original = saved?.sections.find((item) => item.key === section.key);
        if (!original || original.content !== section.content || original.duration_minutes !== section.duration_minutes) {
          await api.updateLessonSection(selected.id, section.key, { content: section.content, duration_minutes: section.duration_minutes });
        }
      }
    }
    const updated = action === "submit" ? await api.submitLessonReview(selected.id) : await api.approveLessonPlan(selected.id);
    await refresh(updated.id);
  });

  return <>
    <div className="page-heading"><div><div className="eyebrow">教学准备 / 智能教案</div><h1>智能教案</h1><p>结合已确认目标与本班历史学情生成分章节草稿，教师逐项修改并审核。</p></div>{selected && <div className="heading-actions"><button className="secondary-button" disabled={busy} onClick={() => void run(() => downloadPdf(`/lesson-plans/${selected.id}/pdf`, `教案-${selected.id}.pdf`))}><Download size={15} />PDF</button><button className="secondary-button" disabled={busy} onClick={() => void run(() => downloadPdf(`/lesson-plans/${selected.id}/docx`, `教案-${selected.id}.docx`))}>Word</button>{selected.status === "draft" && <button className="icon-button" title="删除整份教案" aria-label="删除整份教案" onClick={() => void run(async () => { if (!window.confirm("确定删除整份教案吗？")) return; await api.deleteLessonPlan(selected.id); const items = await api.getLessonPlans(classId); setPlans(items); setSelected(items[0] ?? null); })}><Trash2 size={15} /></button>}</div>}</div>
    <section className="panel glass-panel generation-bar"><div className="field"><span>已确认教学目标</span><select value={goalId ?? ""} onChange={(event) => setGoalId(Number(event.target.value))}>{goals.length ? goals.map((goal) => <option value={goal.id} key={goal.id}>{goal.topic}</option>) : <option value="">请先确认教学目标</option>}</select></div><div className="field"><span>难度</span><select value={difficulty} onChange={(event) => setDifficulty(event.target.value)}><option>基础</option><option>中等</option><option>提高</option></select></div><div className="field"><span>课堂时间</span><input type="number" min={20} max={120} value={duration} onChange={(event) => setDuration(Number(event.target.value))} /></div><button className="primary-button" disabled={busy || !goalId} onClick={generate}><Sparkles size={15} />生成教案草稿</button></section>
    <div className="workbench-grid">
      <aside className="panel glass-panel workbench-list"><div className="panel-heading"><div><span className="eyebrow">教案记录</span><h3>当前班级</h3></div><span className="count-badge">{plans.length}</span></div>{plans.map((plan) => <button key={plan.id} className={`workbench-list-item clickable-card ${selected?.id === plan.id ? "selected" : ""}`} onClick={() => { setSelected(plan); setEvaluation(plan.post_evaluation ?? ""); setReflection(plan.post_reflection ?? ""); }}><strong>{plan.title}</strong><span>{statusText(plan.status)} · {plan.source === "demo" ? "演示生成" : "DeepSeek"}</span></button>)}{!plans.length && <div className="data-pending">暂无教案草稿</div>}</aside>
      <section className="panel glass-panel form-panel"><div className="panel-heading"><div><span className="eyebrow">教案编辑与审核</span><h3>{selected?.title ?? "等待生成"}</h3></div>{selected && <span className="status-pill neutral">{statusText(selected.status)}</span>}</div>
        {error && <div className="form-error" role="alert">{error}</div>}
        {selected ? <><div className="source-note">{selected.source === "demo" ? "演示生成内容，请教师核对后再确认。" : "DeepSeek 生成草稿，请教师核对后再确认。"}</div><div className="form-two"><label className="field"><span>教案标题</span><input value={selected.title} disabled={selected.status === "approved"} onChange={(event) => setSelected({ ...selected, title: event.target.value })} /></label><label className="field"><span>总时长（分钟）</span><input type="number" min={20} max={120} value={selected.duration_minutes} disabled={selected.status === "approved"} onChange={(event) => setSelected({ ...selected, duration_minutes: Number(event.target.value) })} /></label></div><div className="form-actions top-actions"><button className="secondary-button" disabled={busy || selected.status === "approved"} onClick={saveSettings}><Save size={15} />保存设置</button>{selected.status === "draft" && <button className="primary-button" disabled={busy} onClick={() => statusAction("submit")}>提交审核</button>}{selected.status === "pending_review" && <button className="primary-button" disabled={busy} onClick={() => statusAction("approve")}><Check size={15} />教师确认教案</button>}</div><div className="section-list">{selected.sections.filter((section) => !["evaluation", "reflection"].includes(section.key)).map((section) => <div className="section-editor" key={section.key}><div className="section-editor-head"><strong>{section.title}</strong><span>{section.duration_minutes} 分钟</span></div><textarea className="auto-grow" rows={1} value={section.content} disabled={selected.status === "approved"} onChange={(event) => { event.currentTarget.style.height = "auto"; event.currentTarget.style.height = `${event.currentTarget.scrollHeight}px`; setSelected({ ...selected, sections: selected.sections.map((item) => item.key === section.key ? { ...item, content: event.target.value } : item) }); }} /><div className="section-tools"><label>时间 <input type="number" min={0} max={180} value={section.duration_minutes} disabled={selected.status === "approved"} onChange={(event) => setSelected({ ...selected, sections: selected.sections.map((item) => item.key === section.key ? { ...item, duration_minutes: Number(event.target.value) } : item) })} /></label><button title="保存本模块" aria-label={`保存${section.title}`} disabled={busy || selected.status === "approved"} onClick={() => sectionAction(section.key, "save")}><Save size={15} /></button><button title="单独重新生成" aria-label={`重新生成${section.title}`} disabled={busy || selected.status === "approved"} onClick={() => sectionAction(section.key, "regenerate")}><RotateCw size={15} /></button><button title="删除本模块" aria-label={`删除${section.title}`} disabled={busy || selected.status === "approved"} onClick={() => sectionAction(section.key, "delete")}><Trash2 size={15} /></button></div></div>)}</div><div className="post-review panel glass-panel"><div className="panel-heading"><div><span className="eyebrow">课后复盘</span><h3>上完课后再填写</h3></div>{selected.reviewed_at && <span className="status-pill success">已同步学情</span>}</div><label className="field"><span>课堂评价</span><textarea className="auto-grow" rows={1} value={evaluation} disabled={selected.status !== "approved"} onChange={(event) => setEvaluation(event.target.value)} placeholder="记录学生是否达成本节课目标，以及课堂中出现的共性表现" /></label><label className="field"><span>教学反思</span><textarea className="auto-grow" rows={1} value={reflection} disabled={selected.status !== "approved"} onChange={(event) => setReflection(event.target.value)} placeholder="记录本节课后需要调整的讲解、练习或节奏" /></label>{selected.status === "approved" && <button className="secondary-button" disabled={busy || !evaluation.trim() || !reflection.trim()} onClick={saveReview}><Save size={15} />保存课后复盘</button>}</div></> : <div className="empty-message">选择已确认目标后生成教案。</div>}
      </section>
    </div>
  </>;
}

function statusText(status: string) { return status === "approved" ? "已审核" : status === "pending_review" ? "待教师审核" : "草稿"; }
