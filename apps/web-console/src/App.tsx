import { useEffect, useState } from 'react'
import { Activity, Bot, Database, GitBranch, Play, ShieldCheck } from 'lucide-react'

type Task = { task_id: string; status: string; trace_id: string; result?: { message?: string } }

const API = import.meta.env.VITE_PLATFORM_API ?? 'http://127.0.0.1:8000/v1'

export default function App() {
  const [task, setTask] = useState<Task | null>(null)
  const [health, setHealth] = useState('检查中')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetch(`${API.replace(/\/v1$/, '')}/health`).then((r) => r.json()).then(() => setHealth('在线')).catch(() => setHealth('离线'))
  }, [])

  async function startTask() {
    setLoading(true)
    const created = await fetch(`${API}/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': `web-${Date.now()}` },
      body: JSON.stringify({
        tenant_id: 'oem-demo', project_id: 'welding-quality', agent_ref: 'data-explorer@1.0.0',
        goal: '检查焊点质量数据并生成探查计划', input: { dataset_id: 'sample-welding' },
      }),
    }).then((r) => r.json())
    setTask(created)
    setLoading(false)
  }

  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark">AI</div><div><b>Industrial AI</b><span>Agent Platform</span></div></div>
      <nav><a className="active"><Activity size={17}/>总览</a><a><Database size={17}/>数据与探查</a><a><GitBranch size={17}/>特征与实验</a><a><Bot size={17}/>智能体运行</a><a><ShieldCheck size={17}/>治理与审计</a></nav>
      <div className="sidebar-foot"><span className="dot"/>中心开发环境</div>
    </aside>
    <main className="content">
      <header><div><p className="eyebrow">CONTROL PLANE / OVERVIEW</p><h1>工业智能体平台</h1><p className="muted">生产级控制面基线 · 云边协同 · 可审计运行</p></div><div className="status"><span className="dot"/>{health}</div></header>
      <section className="hero"><div><p className="eyebrow">GOLDEN PATH</p><h2>从数据到可追溯的智能任务</h2><p className="muted">通过受治理的 Agent、工具和工作流，完成数据探查、模型实验和工业应用编排。</p><button onClick={startTask} disabled={loading}><Play size={16}/>{loading ? '执行中…' : '启动数据探查任务'}</button></div><div className="hero-orbit"><div className="orbit-center">AI</div><div className="orbit-node n1">数据</div><div className="orbit-node n2">模型</div><div className="orbit-node n3">知识</div></div></section>
      <section className="grid"><Metric label="Agent 运行" value="12" delta="今日 +4"/><Metric label="模型版本" value="8" delta="3 个影子发布"/><Metric label="数据质量" value="96.4%" delta="最近检查"/><Metric label="审计覆盖" value="100%" delta="策略已启用"/></section>
      <section className="panel"><div className="panel-head"><div><p className="eyebrow">TASK RUNTIME</p><h3>最近一次任务</h3></div><span className={`badge ${task?.status === 'SUCCEEDED' ? 'green' : ''}`}>{task?.status ?? '尚未运行'}</span></div>{task ? <div className="task-row"><code>{task.task_id}</code><span>{task.result?.message ?? '任务已进入运行时'}</span><small>{task.trace_id}</small></div> : <div className="empty">启动任务后，这里会显示 Task、Trace 和 Artifact 关联。</div>}</section>
    </main>
  </div>
}

function Metric({ label, value, delta }: { label: string; value: string; delta: string }) { return <div className="metric"><span>{label}</span><strong>{value}</strong><small>{delta}</small></div> }

