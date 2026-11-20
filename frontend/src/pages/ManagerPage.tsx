import { useState } from "react";
import { ArrowRight, Search, Sparkles } from "lucide-react";
import { api, type ManagerAction, type ManagerResponse } from "../api/client";

export function ManagerPage({ classId, className, onNavigate }: { classId: number; className: string; onNavigate: (action: ManagerAction) => Promise<void> }) {
  const [request, setRequest] = useState("");
  const [response, setResponse] = useState<ManagerResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const interpret = async () => {
    if (request.trim().length < 4) return;
    setBusy(true); setError(""); setResponse(null);
    try { setResponse(await api.interpretManagerRequest(classId, request.trim())); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "请求处理失败"); }
    finally { setBusy(false); }
  };

  const followAction = async (action: ManagerAction) => {
    setError("");
    try { await onNavigate(action); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "无法打开对应工作台"); }
  };

  return <>
    <div className="page-heading"><div><div className="eyebrow">教学空间 / {className}</div><h1>AI总管家</h1></div><span className="status-pill neutral">教师工作台入口</span></div>
    <form className="manager-request glass-panel" onSubmit={(event) => { event.preventDefault(); void interpret(); }}><label className="field"><span>教学请求</span><textarea rows={3} value={request} maxLength={500} onChange={(event) => setRequest(event.target.value)} placeholder="例如：帮我看看张同学最近有什么问题" /></label><div className="form-actions"><button className="primary-button" type="submit" disabled={busy || request.trim().length < 4}><Search size={16} />{busy ? "正在处理" : "查询"}</button></div></form>
    {error && <div className="form-error" role="alert">{error}</div>}
    {response && <section className="manager-result"><div className="manager-result-head"><div><span className="eyebrow">处理结果</span><h2>{response.title}</h2></div><span className="status-pill neutral">{response.source === "deepseek" ? "DeepSeek 识别" : response.source === "program" ? "程序校验" : "演示识别"}</span></div><p className="manager-summary">{response.summary}</p>
      {!!response.metrics.length && <div className="manager-metrics">{response.metrics.map((metric) => <div key={metric.label}><span>{metric.label}</span><strong>{metric.value}</strong></div>)}</div>}
      {!!response.evidence.length && <div className="manager-evidence"><div className="eyebrow">数据依据</div>{response.evidence.map((item, index) => <div key={index}><Sparkles size={14} /><span>{item}</span></div>)}</div>}
      {response.action && <div className="manager-action"><button className="primary-button" onClick={() => void followAction(response.action!)}>{response.action.label}<ArrowRight size={15} /></button>{response.action.requires_confirmation && <span>进入工作台后由教师核对并确认</span>}</div>}
    </section>}
  </>;
}
