import { useState } from "react";
import { Pencil, Plus, Search, X } from "lucide-react";
import { api, type ClassDetail, type Student, type StudentLearningOverview } from "../api/client";

type DialogMode = "create" | "edit";

export function ClassDialog({ current, mode, onClose, onSaved }: { current: ClassDetail; mode: DialogMode; onClose: () => void; onSaved: (classId: number) => Promise<void> }) {
  const [name, setName] = useState(mode === "edit" ? current.name : "");
  const [grade, setGrade] = useState(mode === "edit" ? current.grade : "高一");
  const [topic, setTopic] = useState(mode === "edit" ? current.current_topic ?? "" : "");
  const [progress, setProgress] = useState(mode === "edit" ? current.current_progress ?? "" : "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const save = async () => {
    setBusy(true); setError("");
    try {
      const classroom = mode === "create"
        ? await api.createClass({ name: name.trim(), grade: grade.trim(), current_topic: topic.trim() })
        : await api.updateClass(current.id, { name: name.trim(), grade: grade.trim(), current_topic: topic.trim(), current_progress: progress.trim() });
      await onSaved(classroom.id);
      onClose();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "保存失败"); }
    finally { setBusy(false); }
  };
  return <div className="dialog-backdrop" onMouseDown={onClose}><div className="dialog glass-panel" role="dialog" aria-modal="true" aria-label={mode === "create" ? "新增班级" : "编辑班级"} onMouseDown={(event) => event.stopPropagation()}><div className="dialog-head"><div><span className="eyebrow">班级管理</span><h2>{mode === "create" ? "新增班级" : "编辑班级"}</h2></div><button className="icon-button" title="关闭" onClick={onClose}><X size={18} /></button></div>{error && <div className="form-error" role="alert">{error}</div>}<div className="form-two"><label className="field"><span>班级名称</span><input value={name} onChange={(event) => setName(event.target.value)} placeholder="例如：高一（4）班" /></label><label className="field"><span>年级</span><input value={grade} onChange={(event) => setGrade(event.target.value)} /></label></div><label className="field"><span>当前教学主题</span><input value={topic} onChange={(event) => setTopic(event.target.value)} placeholder="可稍后设置" /></label>{mode === "edit" && <label className="field"><span>教学进度</span><textarea rows={3} value={progress} onChange={(event) => setProgress(event.target.value)} /></label>}<div className="form-actions"><button className="secondary-button" onClick={onClose}>取消</button><button className="primary-button" disabled={busy || !name.trim() || !grade.trim()} onClick={save}>保存班级</button></div></div></div>;
}

export function StudentsManagement({ classroom, overviews, onStudent, onRefresh }: { classroom: ClassDetail; overviews: Record<number, StudentLearningOverview>; onStudent: (student: Student) => void; onRefresh: () => Promise<void> }) {
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState<Student | null | "create">(null);
  const students = classroom.students.filter((student) => `${student.name}${student.student_no}`.toLowerCase().includes(query.trim().toLowerCase()));
  return <><div className="page-heading"><div><div className="eyebrow">班级管理 / {classroom.name}</div><h1>学生管理</h1><p>维护学生基础档案，学习画像随着后续答题记录形成。</p></div><button className="primary-button" onClick={() => setEditing("create")}><Plus size={15} />新增学生</button></div><section className="panel glass-panel table-panel"><div className="table-toolbar"><div><h3>班级学生</h3><span>{classroom.students.length} 名学生</span></div><label className="search-box"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索姓名或学号" /></label></div><div className="table-wrap"><table><thead><tr><th>学生</th><th>学号</th><th>历史平均分</th><th>重点知识点</th><th>状态</th><th>操作</th></tr></thead><tbody>{students.map((student) => { const learning = overviews[student.id]; const focus = learning?.profiles.find((profile) => profile.attention_status === "重点关注"); return <tr key={student.id}><td><div className="student-cell"><div className="student-avatar">{student.name.slice(0, 1)}</div><strong>{student.name}</strong></div></td><td className="muted-cell">{student.student_no}</td><td><strong>{learning?.average_score == null ? "--" : learning.average_score.toFixed(1)}</strong></td><td>{focus ? <span className="focus-tag">{focus.knowledge_point.name}</span> : <span className="data-pending">暂无重点问题</span>}</td><td><span className="status-pill success">{student.status}</span></td><td><div className="row-actions"><button className="text-button" onClick={() => onStudent(student)}>查看画像 →</button><button className="icon-button" title={`编辑${student.name}`} aria-label={`编辑${student.name}`} onClick={() => setEditing(student)}><Pencil size={15} /></button></div></td></tr>; })}</tbody></table></div>{!students.length && <div className="table-empty">没有找到匹配的学生。</div>}</section>{editing && <StudentDialog classroom={classroom} student={editing === "create" ? null : editing} onClose={() => setEditing(null)} onSaved={onRefresh} />}</>;
}

function StudentDialog({ classroom, student, onClose, onSaved }: { classroom: ClassDetail; student: Student | null; onClose: () => void; onSaved: () => Promise<void> }) {
  const [name, setName] = useState(student?.name ?? "");
  const [studentNo, setStudentNo] = useState(student?.student_no ?? "");
  const [status, setStatus] = useState(student?.status ?? "在读");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const save = async () => {
    setBusy(true); setError("");
    try {
      if (student) await api.updateStudent(student.id, { name: name.trim(), student_no: studentNo.trim(), status });
      else await api.createStudent(classroom.id, { name: name.trim(), student_no: studentNo.trim() });
      await onSaved();
      onClose();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "保存失败"); }
    finally { setBusy(false); }
  };
  return <div className="dialog-backdrop" onMouseDown={onClose}><div className="dialog glass-panel" role="dialog" aria-modal="true" aria-label={student ? "编辑学生" : "新增学生"} onMouseDown={(event) => event.stopPropagation()}><div className="dialog-head"><div><span className="eyebrow">{classroom.name}</span><h2>{student ? "编辑学生" : "新增学生"}</h2></div><button className="icon-button" title="关闭" onClick={onClose}><X size={18} /></button></div>{error && <div className="form-error" role="alert">{error}</div>}<div className="form-two"><label className="field"><span>学生姓名</span><input value={name} onChange={(event) => setName(event.target.value)} /></label><label className="field"><span>学号</span><input value={studentNo} onChange={(event) => setStudentNo(event.target.value)} /></label></div>{student && <label className="field"><span>状态</span><select value={status} onChange={(event) => setStatus(event.target.value)}><option>在读</option><option>停用</option></select></label>}<div className="form-actions"><button className="secondary-button" onClick={onClose}>取消</button><button className="primary-button" disabled={busy || !name.trim() || !studentNo.trim()} onClick={save}>保存学生</button></div></div></div>;
}
