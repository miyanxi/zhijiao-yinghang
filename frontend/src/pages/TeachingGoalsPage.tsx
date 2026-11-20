import { useEffect, useState } from "react";
import { Check, Plus, Save, Sparkles, Trash2 } from "lucide-react";
import { api, type GoalFields, type TeachingGoal } from "../api/client";

type EditableGoal = GoalFields & { raw_input: string; source: string; id?: number; status?: string };

const emptyGoal: EditableGoal = {
  raw_input: "", source: "teacher", topic: "", knowledge_point_ids: [], objectives: [],
  key_points: "", difficult_points: "", class_context: "", teaching_advice: "", teacher_requirements: "",
};

export function TeachingGoalsPage({ classId }: { classId: number }) {
  const [goals, setGoals] = useState<TeachingGoal[]>([]);
  const [current, setCurrent] = useState<EditableGoal>({ ...emptyGoal });
  const [objectiveText, setObjectiveText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getGoals(classId)
      .then((items) => { setGoals(items); if (items[0]) selectGoal(items[0]); else selectGoal(null); })
      .catch((reason: Error) => setError(reason.message));
  }, [classId]);

  const selectGoal = (goal: TeachingGoal | null) => {
    const value = goal ?? { ...emptyGoal };
    if (goal) value.teaching_advice = goal.teaching_advice || goal.teacher_requirements;
    setCurrent({ ...value, knowledge_point_ids: [...value.knowledge_point_ids], objectives: [...value.objectives] });
    setObjectiveText(value.objectives.join("\n"));
    setError("");
  };

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try { await action(); } catch (reason) { setError(reason instanceof Error ? reason.message : "操作失败"); }
    finally { setBusy(false); }
  };

  const refresh = async (selectedId?: number) => {
    const items = await api.getGoals(classId);
    setGoals(items);
    const match = items.find((item) => item.id === selectedId) ?? items[0];
    if (match) selectGoal(match);
  };

  const parse = () => run(async () => {
    const parsed = await api.parseGoal(classId, current.raw_input);
    setCurrent({ ...current, ...parsed, id: undefined, status: undefined });
    setObjectiveText(parsed.objectives.join("\n"));
  });

  const save = () => run(async () => {
    const fields = { ...current, teacher_requirements: current.teaching_advice, objectives: objectiveText.split("\n").map((value) => value.trim()).filter(Boolean) };
    if (current.id) {
      const updated = await api.updateGoal(current.id, fields);
      await refresh(updated.id);
    } else {
      const created = await api.createGoal({ ...fields, class_id: classId, raw_input: current.raw_input || fields.topic, source: current.source });
      await refresh(created.id);
    }
  });

  const confirm = () => run(async () => {
    if (!current.id) return;
    await api.updateGoal(current.id, {
      topic: current.topic, knowledge_point_ids: current.knowledge_point_ids,
      objectives: objectiveText.split("\n").map((value) => value.trim()).filter(Boolean),
      key_points: current.key_points, difficult_points: current.difficult_points,
      class_context: current.class_context, teaching_advice: current.teaching_advice,
    });
    await api.confirmGoal(current.id);
    await refresh(current.id);
  });

  const removeGoal = (goal: TeachingGoal) => run(async () => {
    if (!window.confirm(`确定删除“${goal.topic}”吗？已生成教案或作业的目标不可删除。`)) return;
    await api.deleteGoal(goal.id);
    const items = await api.getGoals(classId);
    setGoals(items);
    selectGoal(items[0] ?? null);
  });

  const editable = current.status !== "confirmed";
  return <>
    <div className="page-heading"><div><div className="eyebrow">教学准备 / 教学目标</div><h1>教学目标</h1><p>依据课程内容和班级长期学习记录准备本节课目标。</p></div><button className="secondary-button" onClick={() => selectGoal(null)}><Plus size={15} />新建目标</button></div>
    <div className="workbench-grid">
      <aside className="panel glass-panel workbench-list"><div className="panel-heading"><div><span className="eyebrow">历史目标</span><h3>当前班级</h3></div><span className="count-badge">{goals.length}</span></div>{goals.length ? goals.map((goal) => <div key={goal.id} className="goal-list-row"><button className={`workbench-list-item clickable-card ${current.id === goal.id ? "selected" : ""}`} onClick={() => selectGoal(goal)}><strong>{goal.topic}</strong><span>{goal.status === "confirmed" ? "已确认" : "草稿"} · {goal.source === "demo" ? "演示生成" : goal.source === "deepseek" ? "DeepSeek" : "教师创建"}</span></button><button className="icon-button" title={`删除${goal.topic}`} aria-label={`删除${goal.topic}`} onClick={() => removeGoal(goal)}><Trash2 size={15} /></button></div>) : <div className="data-pending">暂无教学目标</div>}</aside>
      <section className="panel glass-panel form-panel"><div className="panel-heading"><div><span className="eyebrow">{current.id ? "目标详情" : "新建目标"}</span><h3>结构化教学目标</h3></div>{current.source === "demo" && <span className="status-pill neutral">演示生成</span>}{current.status === "confirmed" && <span className="status-pill success">已确认</span>}</div>
        {error && <div className="form-error" role="alert">{error}</div>}
        <label className="field"><span>教师原始要求</span><textarea rows={3} value={current.raw_input} disabled={!editable || !!current.id} onChange={(event) => setCurrent({ ...current, raw_input: event.target.value })} placeholder="例如：这周讲谓语动词，重点掌握一般现在时和一般过去时..." /></label>
        {!current.id && <button className="secondary-button" disabled={busy || current.raw_input.trim().length < 5} onClick={parse}><Sparkles size={15} />解析为目标草稿</button>}
        <label className="field"><span>教学主题</span><input value={current.topic} disabled={!editable} onChange={(event) => setCurrent({ ...current, topic: event.target.value })} /></label>
        <label className="field"><span>教学目标（每行一项）</span><textarea rows={3} value={objectiveText} disabled={!editable} onChange={(event) => setObjectiveText(event.target.value)} /></label>
        <div className="form-two"><label className="field"><span>教学重点</span><textarea rows={3} value={current.key_points} disabled={!editable} onChange={(event) => setCurrent({ ...current, key_points: event.target.value })} /></label><label className="field"><span>教学难点</span><textarea rows={3} value={current.difficult_points} disabled={!editable} onChange={(event) => setCurrent({ ...current, difficult_points: event.target.value })} /></label></div>
        <div className="form-two"><label className="field"><span>相关班级学情</span><textarea rows={3} value={current.class_context} disabled={!editable} onChange={(event) => setCurrent({ ...current, class_context: event.target.value })} /></label><label className="field"><span>本课上课建议</span><textarea rows={3} value={current.teaching_advice} disabled={!editable} onChange={(event) => setCurrent({ ...current, teaching_advice: event.target.value })} /></label></div>
        <div className="form-actions">{editable && <button className="secondary-button" disabled={busy || !current.topic.trim() || !objectiveText.trim()} onClick={save}><Save size={15} />保存草稿</button>}{current.id && current.status === "draft" && <button className="primary-button" disabled={busy} onClick={confirm}><Check size={15} />教师确认目标</button>}</div>
      </section>
    </div>
  </>;
}
