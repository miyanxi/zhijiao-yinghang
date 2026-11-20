import type { ScoreTrendPoint } from "../api/client";

export function ScoreTrend({ title, points, errorCount }: { title: string; points: ScoreTrendPoint[]; errorCount?: number }) {
  const values = points.filter((point) => point.score !== null);
  const coordinates = values.map((point, index) => `${values.length === 1 ? 50 : 8 + index * 84 / (values.length - 1)},${90 - (point.score ?? 0) * .8}`).join(" ");
  return <section className="panel glass-panel trend-panel"><div className="panel-heading"><div><span className="eyebrow">近期变化</span><h3>{title}</h3></div>{errorCount !== undefined && <span className="status-pill neutral">累计错题 {errorCount}</span>}</div>
    {values.length ? <div className="line-chart"><svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label={`${title}折线图`}><line x1="8" y1="90" x2="92" y2="90" className="chart-axis" /><line x1="8" y1="50" x2="92" y2="50" className="chart-grid" /><line x1="8" y1="10" x2="92" y2="10" className="chart-grid" /><polyline points={coordinates} className="chart-line" />{values.map((point, index) => <circle key={point.assignment_id} cx={values.length === 1 ? 50 : 8 + index * 84 / (values.length - 1)} cy={90 - (point.score ?? 0) * .8} r="1.5" className="chart-dot" />)}</svg><div className="line-chart-labels">{values.map((point) => <div key={point.assignment_id} title={point.title}><strong>{point.score?.toFixed(1)}</strong><span>{new Date(point.assigned_at).toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" })}</span></div>)}</div></div> : <div className="empty-message">暂无作业趋势数据。</div>}
  </section>;
}
