import { ChangeEvent, FormEvent, ReactNode, useEffect, useState } from "react";
import { Link, NavLink, Outlet, Route, Routes, useNavigate, useParams } from "react-router-dom";
import {
  ApiError,
  AgentChatResponse,
  AgentConversation,
  AgentMessage,
  apiFetch,
  analyzeRecording,
  authenticate,
  CopilotPrep,
  CopilotResult,
  CopilotStreamEvent,
  createCoreKnowledge,
  createTopic,
  chatWithAgent,
  deleteCoreKnowledge,
  deleteTopic,
  DueReview,
  Profile,
  JobPreview,
  getCoreKnowledge,
  getAgentConversation,
  getAgentConversations,
  getCopilotPrepHistory,
  getDueReviews,
  getHighFreq,
  getTopics,
  KnowledgeFile,
  ResumeStatus,
  Session,
  Settings,
  Topic,
  User,
  deleteResume,
  getResumeStatus,
  previewJobPrep,
  startJobPrep,
  streamCopilot,
  updateCoreKnowledge,
  updateHighFreq,
  uploadResume,
} from "./api";

const TOKEN_KEY = "rebuild_access_token";
const COPILOT_JOB_CONTEXT_KEY = "stepwise_copilot_job_context";

function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState<User | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(Boolean(token));

  async function loadAccount(currentToken: string) {
    setLoading(true);
    try {
      const [account, currentSettings] = await Promise.all([
        apiFetch<User>("/me", {}, currentToken),
        apiFetch<Settings>("/settings", {}, currentToken),
      ]);
      setUser(account);
      setSettings(currentSettings);
    } catch {
      localStorage.removeItem(TOKEN_KEY);
      setToken(null);
      setUser(null);
      setSettings(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (token) void loadAccount(token);
    else setLoading(false);
  }, [token]);

  function onAuthenticated(nextToken: string, nextUser: User) {
    localStorage.setItem(TOKEN_KEY, nextToken);
    setToken(nextToken);
    setUser(nextUser);
  }

  function signOut() {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
    setSettings(null);
  }

  if (loading) return <div className="center-screen">正在读取本地账户…</div>;
  if (!token || !user) return <LoginPage onAuthenticated={onAuthenticated} />;
  if (!settings) return <div className="center-screen">正在读取模型配置…</div>;
  if (settings.needs_onboarding) {
    return (
      <OnboardingPage
        token={token}
        user={user}
        settings={settings}
        onConfigured={(next) => setSettings(next)}
        onSignOut={signOut}
      />
    );
  }

  return (
    <Routes>
      <Route element={<WorkspaceLayout user={user} onSignOut={signOut} />}>
        <Route index element={<Dashboard token={token} />} />
        <Route path="topic-drill" element={<TopicDrillPage token={token} />} />
        <Route path="job-prep" element={<JobPrepPage token={token} />} />
        <Route path="copilot" element={<CopilotPage token={token} />} />
        <Route path="agent" element={<AgentPage token={token} />} />
        <Route path="recording" element={<RecordingPage token={token} />} />
        <Route path="knowledge" element={<KnowledgePage token={token} />} />
        <Route path="interview/:sessionId" element={<InterviewPage token={token} />} />
        <Route path="review/:sessionId" element={<ReviewPage token={token} />} />
        <Route path="history" element={<HistoryPage token={token} />} />
        <Route path="profile" element={<ProfilePage token={token} />} />
        <Route path="settings" element={<SettingsPage token={token} />} />
        <Route path="*" element={<Dashboard token={token} />} />
      </Route>
    </Routes>
  );
}

function LoginPage({ onAuthenticated }: { onAuthenticated: (token: string, user: User) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("demo@example.test");
  const [password, setPassword] = useState("demo-pass-123");
  const [name, setName] = useState("Interview Learner");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await authenticate(mode, { email, password, name });
      onAuthenticated(result.access_token, result.user);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "请求失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-screen">
      <section className="hero-copy">
        <p className="eyebrow">QTRACE / GROWTH STAGE 1</p>
        <h1>把一次面试，变成一条可追踪的成长链。</h1>
        <p className="muted large">这是从空目录自主复现的学习版本。先用本地演示模型跑通认证、状态机和复盘，再逐步接入真实模型与更多功能。</p>
      </section>
      <form className="card auth-card" onSubmit={submit}>
        <div className="tab-row">
          <button type="button" className={mode === "login" ? "tab active" : "tab"} onClick={() => setMode("login")}>登录</button>
          <button type="button" className={mode === "register" ? "tab active" : "tab"} onClick={() => setMode("register")}>注册</button>
        </div>
        {mode === "register" && <label>称呼<input value={name} onChange={(e) => setName(e.target.value)} /></label>}
        <label>邮箱<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
        <label>密码<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={6} required /></label>
        {error && <p className="error">{error}</p>}
        <button className="primary wide" disabled={busy}>{busy ? "处理中…" : mode === "login" ? "进入学习工程" : "创建本地账户"}</button>
        <p className="hint">数据只写入本地 QTrace 数据库，不上传任何内容。</p>
      </form>
    </main>
  );
}

function OnboardingPage({ token, user, settings, onConfigured, onSignOut }: { token: string; user: User; settings: Settings; onConfigured: (settings: Settings) => void; onSignOut: () => void }) {
  const [mode, setMode] = useState<"stub" | "openai">("stub");
  const [apiBase, setApiBase] = useState(settings.llm_api_base || "https://api.openai.com/v1");
  const [model, setModel] = useState(settings.llm_model);
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function configure(payload: Record<string, unknown>) {
    setBusy(true);
    setError("");
    try {
      const next = await apiFetch<Settings>("/settings", { method: "PUT", body: JSON.stringify(payload) }, token);
      onConfigured(next);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "配置失败");
    } finally {
      setBusy(false);
    }
  }
  async function enableStub() {
    await configure({ use_stub_provider: true });
  }
  async function enableOpenAI(event: FormEvent) {
    event.preventDefault();
    await configure({ use_stub_provider: false, llm_api_base: apiBase, llm_model: model, llm_api_key: apiKey });
  }
  return (
    <main className="center-screen">
      <section className="card onboarding-card">
        <p className="eyebrow">WELCOME, {user.name.toUpperCase()}</p>
        <h1>先配置你的模型服务</h1>
        <p className="muted">参考项目需要 LLM 和 Embedding 两类能力。你可以先用本地演示模型学习流程，也可以配置任意 OpenAI 兼容的 Chat Completions 服务。</p>
        <div className="tab-row">
          <button type="button" className={mode === "stub" ? "tab active" : "tab"} onClick={() => setMode("stub")}>本地演示</button>
          <button type="button" className={mode === "openai" ? "tab active" : "tab"} onClick={() => setMode("openai")}>真实 LLM</button>
        </div>
        <div className="provider-grid">
          <div><strong>LLM</strong><span>{mode === "stub" ? "本地 StubProvider" : "OpenAI-compatible"}</span></div>
          <div><strong>Embedding</strong><span>本阶段暂用本地占位配置</span></div>
        </div>
        {error && <p className="error">{error}</p>}
        {mode === "stub" ? <button className="primary wide" onClick={enableStub} disabled={busy}>{busy ? "配置中…" : "启用本地演示模型"}</button> : <form className="provider-form" onSubmit={enableOpenAI}>
          <label>API Base<input value={apiBase} onChange={(e) => setApiBase(e.target.value)} placeholder="https://api.openai.com/v1" required /></label>
          <label>Model<input value={model} onChange={(e) => setModel(e.target.value)} placeholder="例如 gpt-4o-mini" required /></label>
          <label>API Key<input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="只发送到本地 QTrace 后端" autoComplete="off" required /></label>
          <p className="hint">当前版本只把 key 保存在本地 SQLite，不会返回到前端；Embedding 仍使用本地演示占位。</p>
          <button className="primary wide" disabled={busy}>{busy ? "保存中…" : "保存真实 LLM 配置"}</button>
        </form>}
        <button className="ghost wide" onClick={onSignOut}>退出登录</button>
      </section>
    </main>
  );
}

function WorkspaceLayout({ user, onSignOut }: { user: User; onSignOut: () => void }) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">QT</span><span>问迹 <small>QTrace growth lab</small></span></div>
        <nav>
          <NavLink to="/" end>开始训练</NavLink>
          <NavLink to="/topic-drill">专项训练</NavLink>
          <NavLink to="/job-prep">JD 定向</NavLink>
          <NavLink to="/copilot">面试 Copilot</NavLink>
          <NavLink to="/agent">个人 Agent</NavLink>
          <NavLink to="/recording">录音复盘</NavLink>
          <NavLink to="/knowledge">知识库</NavLink>
          <NavLink to="/history">历史记录</NavLink>
          <NavLink to="/profile">我的画像</NavLink>
          <NavLink to="/settings">模型设置</NavLink>
        </nav>
        <div className="sidebar-bottom"><span className="user-chip">{user.name}</span><button className="ghost" onClick={onSignOut}>退出</button></div>
      </aside>
      <main className="workspace"><Outlet /></main>
    </div>
  );
}

function Dashboard({ token }: { token: string }) {
  const navigate = useNavigate();
  const [role, setRole] = useState("AI 应用开发工程师");
  const [resume, setResume] = useState("");
  const [resumeStatus, setResumeStatus] = useState<ResumeStatus | null>(null);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void getResumeStatus(token).then(setResumeStatus).catch(() => setResumeStatus(null));
  }, [token]);

  async function handleUpload(file: File) {
    setUploadBusy(true);
    setUploadError("");
    try {
      setResumeStatus(await uploadResume(file, token));
    } catch (reason) {
      setUploadError(reason instanceof Error ? reason.message : "上传失败");
    } finally {
      setUploadBusy(false);
    }
  }

  async function handleDelete() {
    if (!window.confirm("确认删除本地保存的 PDF 简历吗？")) return;
    setUploadBusy(true);
    setUploadError("");
    try {
      await deleteResume(token);
      setResumeStatus({ has_resume: false, filename: "", size: 0, text_chars: 0 });
    } catch (reason) {
      setUploadError(reason instanceof Error ? reason.message : "删除失败");
    } finally {
      setUploadBusy(false);
    }
  }
  async function start(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const session = await apiFetch<Session>("/interview/start", { method: "POST", body: JSON.stringify({ target_role: role, resume_text: resume }) }, token);
      navigate(`/interview/${session.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "启动失败");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="page-stack">
      <header className="page-header"><div><p className="eyebrow">YOUR NEXT REP</p><h1>开始一场简历模拟面试</h1><p className="muted">先完成一条最小闭环：回答、追问、结束、复盘。之后每个阶段都会在这条主链上扩展。</p></div><span className="status-pill">LOCAL PROVIDER READY</span></header>
      <section className="grid-two">
        <form className="card form-card" onSubmit={start}>
          <div className="section-label">01 / 训练上下文</div>
          <label>目标岗位<input value={role} onChange={(e) => setRole(e.target.value)} required /></label>
          <div className="resume-upload-card">
            <div className="upload-heading">
              <div><strong>PDF 简历（可选）</strong><p className="hint">上传后由后端在本地提取文本；启动面试时会自动注入上下文。</p></div>
              <label className="file-picker">{uploadBusy ? "处理中…" : "选择 PDF"}<input className="file-input" type="file" accept="application/pdf,.pdf" disabled={uploadBusy} onChange={(event) => { const file = event.target.files?.[0]; if (file) void handleUpload(file); event.currentTarget.value = ""; }} /></label>
            </div>
            {resumeStatus?.has_resume ? <div className="resume-meta"><span>{resumeStatus.filename} · {(resumeStatus.size / 1024).toFixed(1)} KB · 已提取 {resumeStatus.text_chars} 字</span><button type="button" className="ghost danger" onClick={() => void handleDelete()} disabled={uploadBusy}>删除</button></div> : <p className="hint">尚未上传 PDF，也可以直接填写下面的项目摘要。</p>}
            {uploadError && <p className="error">{uploadError}</p>}
          </div>
          <label>简历或项目摘要<textarea value={resume} onChange={(e) => setResume(e.target.value)} placeholder="如果不上传 PDF，可以先写一段合成项目经历，例如：我负责了一个 RAG 面试助手…" rows={7} /></label>
          {error && <p className="error">{error}</p>}
          <button className="primary" disabled={busy}>{busy ? "准备中…" : "开始模拟面试 →"}</button>
        </form>
        <section className="card explainer-card">
          <div className="section-label">02 / 你正在学习什么</div>
          <h2>不是先做页面，而是先打通状态。</h2>
          <p className="muted">本阶段自己实现了 FastAPI 路由、JWT、本地 SQLite、provider 抽象和显式面试阶段状态机。</p>
          <div className="phase-list"><span>自我介绍</span><span>技术追问</span><span>项目深挖</span><span>行为问题</span><span>反问</span></div>
          <div className="dashboard-links"><Link className="text-link" to="/profile">查看当前画像 ↗</Link><Link className="text-link" to="/copilot">用 JD 开始 Copilot Prep ↗</Link></div>
        </section>
      </section>
    </div>
  );
}

function TopicDrillPage({ token }: { token: string }) {
  const navigate = useNavigate();
  const [topics, setTopics] = useState<Record<string, Topic>>({});
  const [dueReviews, setDueReviews] = useState<DueReview[]>([]);
  const [selectedTopic, setSelectedTopic] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void Promise.all([getTopics(token), getDueReviews(token)]).then(([nextTopics, nextDueReviews]) => {
      setTopics(nextTopics);
      setDueReviews(nextDueReviews);
      setSelectedTopic((current) => current && nextTopics[current] ? current : Object.keys(nextTopics)[0] || "");
    }).catch((reason) => setError(reason instanceof Error ? reason.message : "读取训练领域失败"));
  }, [token]);

  const selectedDueReviews = dueReviews.filter((item) => item.topic === selectedTopic);

  async function startDrill() {
    if (!selectedTopic) return;
    setBusy(true);
    setError("");
    try {
      const session = await apiFetch<Session>("/interview/start", {
        method: "POST",
        body: JSON.stringify({
          mode: "topic_drill",
          topic: selectedTopic,
          target_role: topics[selectedTopic]?.name || selectedTopic,
        }),
      }, token);
      navigate(`/interview/${session.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "启动专项训练失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-stack">
      <header className="page-header"><div><p className="eyebrow">FOCUSED PRACTICE</p><h1>专项训练</h1><p className="muted">选择一个技术领域，出题和评分会参考该领域的核心知识与高频题库。</p></div><Link className="text-link" to="/knowledge">管理知识库 ↗</Link></header>
      <section className="card drill-intro"><strong>这条链路正在学习什么？</strong><span className="muted">训练领域不是静态题库标签，而是会影响上下文组装、问题方向和复盘依据的数据源。</span>{selectedDueReviews.length > 0 ? <span className="queue-hint">今日优先复习 {selectedDueReviews.length} 个薄弱点：{selectedDueReviews.slice(0, 2).map((item) => item.point).join("、")}</span> : <span className="queue-hint quiet">当前领域没有到期复习项</span>}</section>
      <section className="topic-grid">{Object.entries(topics).map(([key, info]) => <button type="button" className={selectedTopic === key ? "card topic-card selected" : "card topic-card"} key={key} onClick={() => setSelectedTopic(key)}><span className="topic-icon">{info.icon}</span><span><strong>{info.name}</strong><small>{key}</small></span><span className="topic-check">{selectedTopic === key ? "已选" : "选择"}</span></button>)}</section>
      {!Object.keys(topics).length && <section className="card empty-card"><p className="muted">还没有训练领域。</p><Link className="primary inline-button" to="/knowledge">先创建一个领域</Link></section>}
      {error && <p className="error">{error}</p>}
      <div className="drill-action"><span className="muted">当前领域：<strong>{selectedTopic ? topics[selectedTopic]?.name : "未选择"}</strong></span><button className="primary" onClick={() => void startDrill()} disabled={!selectedTopic || busy}>{busy ? "准备中…" : "开始专项训练 →"}</button></div>
    </div>
  );
}

function JobPrepPage({ token }: { token: string }) {
  const navigate = useNavigate();
  const [company, setCompany] = useState("");
  const [position, setPosition] = useState("");
  const [jdText, setJdText] = useState("");
  const [useResume, setUseResume] = useState(true);
  const [preview, setPreview] = useState<JobPreview | null>(null);
  const [previewSignature, setPreviewSignature] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const signature = `${company.trim()}|${position.trim()}|${jdText.trim()}|${useResume}`;
  const previewStale = Boolean(preview && previewSignature !== signature);

  useEffect(() => {
    const raw = sessionStorage.getItem(COPILOT_JOB_CONTEXT_KEY);
    if (!raw) return;
    try {
      const context = JSON.parse(raw) as { company?: string; position?: string; jd_text?: string; use_resume?: boolean };
      setCompany(context.company || "");
      setPosition(context.position || "");
      setJdText(context.jd_text || "");
      setUseResume(context.use_resume ?? true);
      setPreview(null);
      setPreviewSignature("");
    } catch {
      // Ignore a malformed handoff and leave the form empty.
    } finally {
      sessionStorage.removeItem(COPILOT_JOB_CONTEXT_KEY);
    }
  }, []);

  async function analyze(event: FormEvent) {
    event.preventDefault();
    if (jdText.trim().length < 50) {
      setError("JD 至少需要 50 个字符，尽量保留职责、任职要求和技术栈。");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await previewJobPrep({
        company: company.trim() || undefined,
        position: position.trim() || undefined,
        jd_text: jdText.trim(),
        use_resume: useResume,
      }, token);
      setPreview(result.preview);
      setPreviewSignature(signature);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "JD 分析失败");
    } finally {
      setBusy(false);
    }
  }

  async function start() {
    if (!preview || previewStale) return;
    setBusy(true);
    setError("");
    try {
      const session = await startJobPrep({
        company: company.trim() || undefined,
        position: position.trim() || undefined,
        jd_text: jdText.trim(),
        use_resume: useResume,
        preview,
      }, token);
      navigate(`/interview/${session.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "启动 JD 定向训练失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-stack">
      <header className="page-header"><div><p className="eyebrow">ROLE TARGETING</p><h1>JD 定向备面</h1><p className="muted">先拆解岗位，再把 JD 要求、简历匹配和今日复习项接进同一轮训练。</p></div><span className="status-pill">LOCAL ANALYZER</span></header>
      <section className="job-prep-layout">
        <form className="card job-prep-form" onSubmit={analyze}>
          <div className="section-label">01 / 岗位输入</div>
          <label>公司（可选）<input value={company} onChange={(event) => setCompany(event.target.value)} placeholder="例如 QTrace Labs" /></label>
          <label>岗位名称（可选）<input value={position} onChange={(event) => setPosition(event.target.value)} placeholder="例如 大模型应用开发工程师" /></label>
          <label>岗位 JD<textarea value={jdText} onChange={(event) => setJdText(event.target.value)} placeholder="粘贴完整 JD，尽量保留职责、任职要求、技术栈和加分项。" rows={15} /></label>
          <label className="check-row"><input type="checkbox" checked={useResume} onChange={(event) => setUseResume(event.target.checked)} />联动本地已上传的 PDF 简历</label>
          <button className="primary" disabled={busy || jdText.trim().length < 50}>{busy ? "分析中…" : preview ? "重新分析 JD" : "分析 JD →"}</button>
          {error && <p className="error">{error}</p>}
        </form>
        <section className="card job-preview-card">
          <div className="section-label">02 / 岗位拆解</div>
          {!preview ? <div className="empty-card"><p className="muted">提交 JD 后，这里会出现岗位重点、风险缺口和定向问题蓝图。</p></div> : <>
            {previewStale && <p className="warning">岗位输入已变化，请重新分析后再开始训练。</p>}
            <h2>{preview.role_summary}</h2>
            <div className="skill-pills">{preview.detected_skills.length ? preview.detected_skills.map((skill) => <span key={skill}>{skill}</span>) : <span>未命中预置技术词</span>}</div>
            <div className="job-preview-section"><strong>重点方向</strong>{preview.focus_areas.map((item) => <div className="job-focus-row" key={item.area}><div><b>{item.area}</b><small>{item.reason}</small></div><span className={`priority-${item.priority}`}>{item.priority}</span></div>)}</div>
            <div className="job-preview-section"><strong>面试前优先准备</strong><ul>{preview.prep_priorities.map((item) => <li key={item}>{item}</li>)}</ul></div>
            <div className="job-preview-section"><strong>简历匹配</strong><p className="muted">{preview.resume_alignment.fit_assessment}</p>{preview.resume_alignment.risk_gaps.length > 0 && <small className="job-gap">风险缺口：{preview.resume_alignment.risk_gaps.join("；")}</small>}</div>
            <button type="button" className="primary" onClick={() => void start()} disabled={busy || previewStale}>{busy ? "准备中…" : "开始 JD 定向训练 →"}</button>
          </>}
        </section>
      </section>
    </div>
  );
}

function CopilotPage({ token }: { token: string }) {
  const navigate = useNavigate();
  const [company, setCompany] = useState("");
  const [position, setPosition] = useState("");
  const [jdText, setJdText] = useState("");
  const [useResume, setUseResume] = useState(true);
  const [events, setEvents] = useState<CopilotStreamEvent[]>([]);
  const [result, setResult] = useState<CopilotResult | null>(null);
  const [prepId, setPrepId] = useState("");
  const [prepHistory, setPrepHistory] = useState<CopilotPrep[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function loadHistory() {
    try {
      setPrepHistory(await getCopilotPrepHistory(token));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "读取 Copilot 历史失败");
    }
  }

  useEffect(() => {
    void loadHistory();
  }, [token]);

  async function start(event: FormEvent) {
    event.preventDefault();
    if (jdText.trim().length < 50) {
      setError("JD 内容至少需要 50 个字符。");
      return;
    }
    setBusy(true);
    setError("");
    setEvents([]);
    setResult(null);
    setPrepId("");
    try {
      const completed = await streamCopilot({
        company: company.trim() || undefined,
        position: position.trim() || undefined,
        jd_text: jdText.trim(),
        use_resume: useResume,
      }, token, (next) => {
        setEvents((current) => [...current, next]);
        setPrepId(next.data.prep_id);
        if (next.event === "completed" && next.data.result) setResult(next.data.result);
      });
      setResult(completed);
      await loadHistory();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Copilot Prep 失败");
    } finally {
      setBusy(false);
    }
  }

  function restorePrep(prep: CopilotPrep) {
    setCompany(prep.company);
    setPosition(prep.position);
    setJdText(prep.jd_text);
    setResult(prep.result);
    setPrepId(prep.id);
    setEvents(prep.result ? [{ event: "completed", data: { prep_id: prep.id, stage: "completed", message: "已从历史恢复", result: prep.result } }] : []);
    setError("");
  }

  function continueToJobPrep() {
    sessionStorage.setItem(COPILOT_JOB_CONTEXT_KEY, JSON.stringify({
      company,
      position,
      jd_text: jdText,
      use_resume: useResume,
    }));
    navigate("/job-prep");
  }

  return (
    <div className="page-stack">
      <header className="page-header"><div><p className="eyebrow">COPILOT / TEXT PREP PHASE</p><h1>面试 Copilot</h1><p className="muted">先把 JD、简历和画像组合成追问策略，再进入训练。当前阶段用 JSON + SSE 演示事件流，不接实时语音。</p></div><span className="status-pill">JSON + SSE</span></header>
      <section className="copilot-layout">
        <div className="copilot-left-stack">
          <form className="card copilot-form" onSubmit={start}>
            <div className="section-label">01 / PREP INPUT</div>
            <div className="grid-two compact-grid"><label>公司（可选）<input value={company} onChange={(event) => setCompany(event.target.value)} placeholder="例如 QTrace Labs" /></label><label>岗位（可选）<input value={position} onChange={(event) => setPosition(event.target.value)} placeholder="例如 AI 应用开发工程师" /></label></div>
            <label className="check-row"><input type="checkbox" checked={useResume} onChange={(event) => setUseResume(event.target.checked)} />自动带入已保存简历和训练画像</label>
            <label>目标岗位 JD<textarea value={jdText} onChange={(event) => setJdText(event.target.value)} placeholder="粘贴完整岗位职责、任职要求和技术栈……" rows={18} /></label>
            {error && <p className="error">{error}</p>}
            <button className="primary" disabled={busy || jdText.trim().length < 50}>{busy ? "事件流处理中…" : "生成 Copilot Prep →"}</button>
            {prepId && <p className="hint">Prep ID：{prepId}</p>}
          </form>
          <section className="card copilot-history"><div className="section-label">RECENT PREPS</div>{prepHistory.length ? prepHistory.slice(0, 5).map((prep) => <button type="button" className="copilot-history-row" key={prep.id} onClick={() => restorePrep(prep)}><span><strong>{prep.company || "未命名公司"}</strong><small>{prep.position || "未命名岗位"}</small></span><em>{prep.status === "completed" ? "已完成" : prep.status}</em></button>) : <p className="muted">还没有历史 Prep。完成一次分析后会保存在这里。</p>}</section>
        </div>
        <section className="card copilot-stream-card">
          <div className="section-label">02 / EVENT STREAM</div>
          <div className="copilot-events">{events.length === 0 ? <p className="muted">提交 JD 后，这里会按顺序显示 started、JD 分析、风险评估、策略树和 completed 事件。</p> : events.map((item, index) => <div className={`copilot-event ${item.event === "error" ? "failed" : item.event === "completed" ? "done" : ""}`} key={`${item.event}-${index}`}><span>{item.event}</span><p>{item.data.message || (item.event === "completed" ? "结果已保存" : "事件已收到")}</p></div>)}</div>
          {result && <div className="copilot-result"><div className="section-label">03 / STRATEGY OUTPUT</div><h2>{result.role_summary}</h2><div className="skill-pills">{result.detected_skills.map((skill) => <span key={skill}>{skill}</span>)}</div><div className="copilot-section"><strong>追问策略树</strong>{result.strategy_tree.nodes.map((node) => <div className="strategy-node" key={node.id}><div><b>{node.label}</b><small>{node.trigger}</small></div><span>{node.priority}</span><p>{node.follow_up}</p></div>)}</div><div className="copilot-section"><strong>风险地图</strong>{result.risk_map.map((item) => <div className="copilot-risk" key={`${item.risk}-${item.severity}`}><div><b>{item.risk}</b><small>{item.evidence}</small></div><p>{item.mitigation}</p></div>)}</div><div className="copilot-section"><strong>面试前行动</strong><ul>{result.prep_hints.map((hint) => <li key={hint}>{hint}</li>)}</ul></div><div className="copilot-result-actions"><button type="button" className="primary" onClick={continueToJobPrep}>带入 JD 定向训练 →</button><Link className="text-link" to="/profile">查看画像中的复习队列 ↗</Link></div></div>}
        </section>
      </section>
    </div>
  );
}

function AgentPage({ token }: { token: string }) {
  const [conversations, setConversations] = useState<AgentConversation[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [plan, setPlan] = useState<AgentChatResponse["plan"] | null>(null);
  const [toolTrace, setToolTrace] = useState<AgentChatResponse["tool_trace"]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function loadConversations() {
    try {
      setConversations(await getAgentConversations(token));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "读取 Agent 历史失败");
    }
  }

  useEffect(() => {
    void loadConversations();
  }, [token]);

  async function openConversation(id: string) {
    setError("");
    try {
      const conversation = await getAgentConversation(id, token);
      setConversationId(conversation.id);
      setMessages(conversation.messages);
      setPlan(null);
      setToolTrace([]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "读取 Agent 对话失败");
    }
  }

  function startNewConversation() {
    setConversationId(null);
    setMessages([]);
    setPlan(null);
    setToolTrace([]);
    setDraft("");
    setError("");
  }

  async function send(event: FormEvent) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || busy) return;
    setBusy(true);
    setError("");
    setDraft("");
    setMessages((current) => [...current, { role: "user", content: message }]);
    try {
      const result = await chatWithAgent({ message, conversation_id: conversationId }, token);
      setConversationId(result.conversation_id);
      setMessages((current) => [...current, result.message]);
      setPlan(result.plan);
      setToolTrace(result.tool_trace);
      await loadConversations();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Agent 请求失败");
    } finally {
      setBusy(false);
    }
  }

  const quickPrompts = [
    "根据我的长期画像，今天最应该复习什么？",
    "结合我的训练历史，帮我安排下一轮 AI Agent 专项训练。",
    "读取我的简历，指出一个最值得准备的项目追问。",
  ];

  return (
    <div className="page-stack">
      <header className="page-header">
        <div><p className="eyebrow">PERSONAL GROWTH AGENT / V1</p><h1>个人 Agent</h1><p className="muted">Agent 会先规划需要读取的上下文，再调用只读工具读取画像、SM-2 队列、训练历史和简历，最后生成个性化建议。</p></div>
        <span className="status-pill">PLAN + TOOLS</span>
      </header>
      <section className="agent-layout">
        <aside className="card agent-history">
          <div className="agent-history-head"><div className="section-label">AGENT MEMORY</div><button type="button" className="ghost" onClick={startNewConversation}>＋ 新对话</button></div>
          {conversations.length ? conversations.slice(0, 8).map((conversation) => <button type="button" className={conversation.id === conversationId ? "agent-history-row active" : "agent-history-row"} key={conversation.id} onClick={() => void openConversation(conversation.id)}><strong>{conversation.title}</strong><small>{conversation.message_count} 条消息</small></button>) : <p className="muted">还没有 Agent 对话。先提出一个学习问题。</p>}
          <div className="inset-card"><strong>当前工具边界</strong><p className="hint">v1 只读取上下文，不会自动修改画像、创建任务或删除数据。</p></div>
        </aside>
        <main className="agent-main">
          <section className="card agent-chat-card">
            <div className="agent-messages">{messages.length === 0 ? <div className="empty-card"><p className="muted">你可以问我：我当前最薄弱的知识点是什么？下一轮应该练什么？我的简历项目可能被怎样追问？</p></div> : messages.map((message, index) => <div className={`agent-message ${message.role}`} key={`${message.role}-${index}`}><span>{message.role === "user" ? "你" : "Agent"}</span><p>{message.content}</p></div>)}</div>
            <div className="agent-quick-prompts">{quickPrompts.map((prompt) => <button type="button" className="ghost" key={prompt} onClick={() => setDraft(prompt)}>{prompt}</button>)}</div>
            <form className="agent-composer" onSubmit={send}><textarea value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="向你的个人成长 Agent 提问……" rows={5} /><div className="answer-actions"><span className="hint">本地模式会执行确定性工具规划；配置真实 LLM 后由模型生成规划和回答。</span><button className="primary" disabled={busy || !draft.trim()}>{busy ? "Agent 工作中…" : "发送给 Agent →"}</button></div></form>
            {error && <p className="error">{error}</p>}
          </section>
          {(plan || toolTrace.length > 0) && <section className="card agent-trace"><div className="section-label">AGENT TRACE</div>{plan && <div className="agent-plan"><strong>规划意图：{plan.intent}</strong>{plan.tool_calls.map((call) => <span key={call.name}>调用 {call.name} · {call.reason}</span>)}</div>}<div className="agent-tools">{toolTrace.map((item) => <div className={`agent-tool ${item.status === "failed" ? "failed" : ""}`} key={item.name}><span>{item.name}</span><p>{item.summary}</p></div>)}</div></section>}
        </main>
      </section>
    </div>
  );
}

function RecordingPage({ token }: { token: string }) {
  const navigate = useNavigate();
  const [company, setCompany] = useState("");
  const [position, setPosition] = useState("");
  const [mode, setMode] = useState<"dual" | "solo">("dual");
  const [analysisMode, setAnalysisMode] = useState<"rules" | "llm">("rules");
  const [transcript, setTranscript] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function importTranscript(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > 40_000) {
      setError("本地转写文件不能超过 40 KB。");
      event.target.value = "";
      return;
    }
    try {
      setTranscript((await file.text()).trim());
      setError("");
    } catch {
      setError("读取本地转写文件失败，请确认它是 UTF-8 文本。");
    }
  }

  async function analyze(event: FormEvent) {
    event.preventDefault();
    if (transcript.trim().length < 20) {
      setError("转写文本至少需要 20 个字符。");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const session = await analyzeRecording({
        transcript: transcript.trim(),
        recording_mode: mode,
        analysis_mode: analysisMode,
        company: company.trim() || undefined,
        position: position.trim() || undefined,
      }, token);
      navigate(`/review/${session.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "录音复盘失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-stack">
      <header className="page-header"><div><p className="eyebrow">VOICE REVIEW / TEXT FIRST</p><h1>录音复盘</h1><p className="muted">先粘贴转写文本，验证“转写 → 说话人解析 → 复盘 → 画像写回”主链；真实 ASR 作为下一层适配器。</p></div><span className="status-pill">ASR ADAPTER READY</span></header>
      <section className="recording-layout">
        <form className="card recording-form" onSubmit={analyze}>
          <div className="section-label">01 / 转写输入</div>
          <div className="grid-two compact-grid"><label>公司（可选）<input value={company} onChange={(event) => setCompany(event.target.value)} placeholder="例如 QTrace Labs" /></label><label>岗位（可选）<input value={position} onChange={(event) => setPosition(event.target.value)} placeholder="例如 AI 应用开发工程师" /></label></div>
          <label>复盘模式<select value={mode} onChange={(event) => setMode(event.target.value as "dual" | "solo")}><option value="dual">双人面试转写</option><option value="solo">个人口述复盘</option></select></label>
          <label>分析器<select value={analysisMode} onChange={(event) => setAnalysisMode(event.target.value as "rules" | "llm")}><option value="rules">本地规则分析（默认）</option><option value="llm">真实 LLM 结构化分析（需配置）</option></select></label>
          <label>导入本地 TXT 转写<input type="file" accept=".txt,text/plain" onChange={(event) => void importTranscript(event)} /></label>
          <label>转写文本<textarea value={transcript} onChange={(event) => setTranscript(event.target.value)} placeholder={mode === "dual" ? "面试官：请介绍一个项目。\n你：我负责……\n面试官：如何验证？\n你：我会……" : "粘贴你的完整口述转写文本。"} rows={17} /></label>
          <p className="hint">双人模式支持“面试官：/你：”或 “Interviewer:/Candidate:” 标签；没有标签时不会臆造问答边界。TXT 只在浏览器本地读取，不上传文件。</p>
          {error && <p className="error">{error}</p>}
          <button className="primary" disabled={busy || transcript.trim().length < 20}>{busy ? "分析中…" : "开始文本复盘 →"}</button>
        </form>
        <section className="card recording-guide">
          <div className="section-label">02 / 这一阶段学什么</div>
          <h2>先把 ASR 之外的链路讲清楚。</h2>
          <div className="recording-flow"><span>转写文本</span><b>→</b><span>说话人解析</span><b>→</b><span>结构化复盘</span><b>→</b><span>长期画像</span></div>
          <p className="muted">当前使用本地确定性分析器，不调用麦克风、不上传音频。ASR 仅保留为可替换边界，项目交付以转写文本复盘为主。</p>
          <div className="card inset-card"><strong>建议先测试的转写格式</strong><p className="hint">面试官：请解释你的技术方案。<br />你：我先定义指标，再做实验，最终延迟降低 30%。</p></div>
        </section>
      </section>
    </div>
  );
}

function KnowledgePage({ token }: { token: string }) {
  const [topics, setTopics] = useState<Record<string, Topic>>({});
  const [selectedTopic, setSelectedTopic] = useState("");
  const [files, setFiles] = useState<KnowledgeFile[]>([]);
  const [selectedFile, setSelectedFile] = useState("");
  const [fileContent, setFileContent] = useState("");
  const [highFreq, setHighFreq] = useState("");
  const [newTopicName, setNewTopicName] = useState("");
  const [newTopicKey, setNewTopicKey] = useState("");
  const [newFileName, setNewFileName] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function loadTopics(preferred = "") {
    const next = await getTopics(token);
    setTopics(next);
    setSelectedTopic((current) => preferred && next[preferred] ? preferred : current && next[current] ? current : Object.keys(next)[0] || "");
  }

  useEffect(() => {
    void loadTopics().catch((reason) => setError(reason instanceof Error ? reason.message : "读取知识库失败"));
  }, [token]);

  useEffect(() => {
    if (!selectedTopic) {
      setFiles([]); setSelectedFile(""); setFileContent(""); setHighFreq("");
      return;
    }
    let active = true;
    Promise.all([getCoreKnowledge(selectedTopic, token), getHighFreq(selectedTopic, token)]).then(([nextFiles, nextHighFreq]) => {
      if (!active) return;
      const preferred = nextFiles.find((file) => file.filename === selectedFile) || nextFiles[0];
      setFiles(nextFiles);
      setSelectedFile(preferred?.filename || "");
      setFileContent(preferred?.content || "");
      setHighFreq(nextHighFreq.content);
    }).catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : "读取知识文件失败"); });
    return () => { active = false; };
  }, [selectedTopic, token]);

  async function addTopic(event: FormEvent) {
    event.preventDefault();
    if (!newTopicName.trim()) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await createTopic({ name: newTopicName, key: newTopicKey || undefined }, token);
      setNewTopicName(""); setNewTopicKey("");
      await loadTopics(result.key);
      setMessage("训练领域已创建");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "创建领域失败"); }
    finally { setBusy(false); }
  }

  async function addFile() {
    if (!selectedTopic) return;
    const filename = newFileName.trim() || `notes-${Date.now()}.md`;
    setBusy(true); setError(""); setMessage("");
    try {
      await createCoreKnowledge(selectedTopic, { filename, content: `# ${topics[selectedTopic]?.name || selectedTopic}\n\n` }, token);
      setNewFileName("");
      const nextFiles = await getCoreKnowledge(selectedTopic, token);
      const created = nextFiles.find((file) => file.filename === filename) || nextFiles[0];
      setFiles(nextFiles); setSelectedFile(created?.filename || ""); setFileContent(created?.content || "");
      setMessage("知识文件已创建");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "创建知识文件失败"); }
    finally { setBusy(false); }
  }

  async function saveFile() {
    if (!selectedTopic || !selectedFile) return;
    setBusy(true); setError(""); setMessage("");
    try { await updateCoreKnowledge(selectedTopic, selectedFile, fileContent, token); setMessage("核心知识已保存"); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "保存知识文件失败"); }
    finally { setBusy(false); }
  }

  async function removeFile() {
    if (!selectedTopic || !selectedFile || !window.confirm(`确认删除 ${selectedFile} 吗？`)) return;
    setBusy(true); setError("");
    try {
      await deleteCoreKnowledge(selectedTopic, selectedFile, token);
      const nextFiles = await getCoreKnowledge(selectedTopic, token);
      const next = nextFiles[0]; setFiles(nextFiles); setSelectedFile(next?.filename || ""); setFileContent(next?.content || "");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "删除知识文件失败"); }
    finally { setBusy(false); }
  }

  async function saveHighFreq() {
    if (!selectedTopic) return;
    setBusy(true); setError(""); setMessage("");
    try { await updateHighFreq(selectedTopic, highFreq, token); setMessage("高频题库已保存"); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "保存题库失败"); }
    finally { setBusy(false); }
  }

  async function removeTopic() {
    if (!selectedTopic || !window.confirm(`确认删除训练领域「${topics[selectedTopic]?.name || selectedTopic}」及其知识文件吗？`)) return;
    setBusy(true); setError("");
    try { await deleteTopic(selectedTopic, token); await loadTopics(); setMessage("训练领域已删除"); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "删除领域失败"); }
    finally { setBusy(false); }
  }

  return (
    <div className="page-stack">
      <header className="page-header"><div><p className="eyebrow">KNOWLEDGE WORKSPACE</p><h1>知识库</h1><p className="muted">领域、核心知识和高频题库共同决定专项训练的上下文。</p></div><Link className="text-link" to="/topic-drill">去专项训练 ↗</Link></header>
      <section className="knowledge-layout">
        <aside className="card knowledge-sidebar"><div className="section-label">训练领域</div>{Object.entries(topics).map(([key, info]) => <button type="button" key={key} className={selectedTopic === key ? "knowledge-topic active" : "knowledge-topic"} onClick={() => setSelectedTopic(key)}><span>{info.icon}</span><span>{info.name}</span></button>)}<form className="create-topic-form" onSubmit={addTopic}><input value={newTopicName} onChange={(event) => setNewTopicName(event.target.value)} placeholder="新领域名称" /><input value={newTopicKey} onChange={(event) => setNewTopicKey(event.target.value)} placeholder="key（可选）" /><button className="ghost" disabled={busy}>＋ 创建领域</button></form></aside>
        <main className="knowledge-main">{selectedTopic ? <><section className="card knowledge-editor"><div className="knowledge-editor-head"><div><div className="section-label">核心知识 / {topics[selectedTopic]?.name}</div><p className="hint">Markdown 文件会被切分并用本地关键词检索，作为出题上下文。</p></div><button type="button" className="ghost danger" onClick={() => void removeTopic()} disabled={busy}>删除领域</button></div><div className="file-tabs">{files.map((file) => <button type="button" key={file.filename} className={selectedFile === file.filename ? "file-tab active" : "file-tab"} onClick={() => { setSelectedFile(file.filename); setFileContent(file.content); }}>{file.filename}</button>)}</div><div className="file-actions"><input value={newFileName} onChange={(event) => setNewFileName(event.target.value)} placeholder="新文件名，例如 notes.md" /><button type="button" className="ghost" onClick={() => void addFile()} disabled={busy}>＋ 新建文件</button><button type="button" className="ghost danger" onClick={() => void removeFile()} disabled={busy || !selectedFile}>删除文件</button></div><textarea className="knowledge-textarea" value={fileContent} onChange={(event) => setFileContent(event.target.value)} disabled={!selectedFile} rows={16} /><button type="button" className="primary" onClick={() => void saveFile()} disabled={busy || !selectedFile}>保存核心知识</button></section><section className="card knowledge-editor"><div className="section-label">高频题库</div><p className="hint">每行一个问题，支持 `- 问题` 或 `1. 问题` 格式。StubProvider 会按训练阶段读取这些问题。</p><textarea className="knowledge-textarea" value={highFreq} onChange={(event) => setHighFreq(event.target.value)} rows={9} /><button type="button" className="primary" onClick={() => void saveHighFreq()} disabled={busy}>保存高频题库</button></section></> : <section className="card empty-card"><p className="muted">先创建或选择一个训练领域。</p></section>}</main>
      </section>
      {message && <p className="success">{message}</p>}{error && <p className="error">{error}</p>}
    </div>
  );
}

function SettingsPage({ token }: { token: string }) {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [mode, setMode] = useState<"stub" | "openai">("stub");
  const [apiBase, setApiBase] = useState("https://api.openai.com/v1");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    void apiFetch<Settings>("/settings", {}, token).then((current) => {
      setSettings(current);
      setMode(current.provider_mode === "openai" ? "openai" : "stub");
      setApiBase(current.llm_api_base || "https://api.openai.com/v1");
      setModel(current.llm_model);
    });
  }, [token]);

  async function save(payload: Record<string, unknown>) {
    setBusy(true); setError(""); setMessage("");
    try {
      const next = await apiFetch<Settings>("/settings", { method: "PUT", body: JSON.stringify(payload) }, token);
      setSettings(next);
      setMode(next.provider_mode === "openai" ? "openai" : "stub");
      setApiKey("");
      setMessage("配置已保存");
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "保存失败");
    } finally { setBusy(false); }
  }

  if (!settings) return <div className="center-screen">正在读取模型设置…</div>;
  return <div className="page-stack narrow-page"><header className="page-header"><div><p className="eyebrow">PROVIDER SETTINGS</p><h1>模型设置</h1><p className="muted">Provider 是面试状态机之外的可替换边界。你可以在这里切换本地演示模型或真实 LLM。</p></div></header><section className="card onboarding-card"><div className="tab-row"><button type="button" className={mode === "stub" ? "tab active" : "tab"} onClick={() => setMode("stub")}>本地演示</button><button type="button" className={mode === "openai" ? "tab active" : "tab"} onClick={() => setMode("openai")}>真实 LLM</button></div><div className="provider-grid"><div><strong>当前 Provider</strong><span>{settings.provider_mode}</span></div><div><strong>Embedding</strong><span>{settings.embedding_mode}（占位）</span></div></div>{message && <p className="success">{message}</p>}{error && <p className="error">{error}</p>}{mode === "stub" ? <button className="primary wide" onClick={() => void save({ use_stub_provider: true })} disabled={busy}>{busy ? "保存中…" : "使用本地演示模型"}</button> : <form className="provider-form" onSubmit={(event) => { event.preventDefault(); void save({ use_stub_provider: false, llm_api_base: apiBase, llm_model: model, llm_api_key: apiKey }); }}><label>API Base<input value={apiBase} onChange={(e) => setApiBase(e.target.value)} required /></label><label>Model<input value={model} onChange={(e) => setModel(e.target.value)} required /></label><label>API Key<input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder={settings.llm_key_configured ? "已保存；留空则保持不变" : "只发送到本地 QTrace 后端"} autoComplete="off" required={!settings.llm_key_configured} /></label><p className="hint">已配置状态：{settings.llm_key_configured ? "是" : "否"}。API Key 不会从后端返回。</p><button className="primary wide" disabled={busy}>{busy ? "保存中…" : "保存真实 LLM 配置"}</button></form>}</section></div>;
}

function InterviewPage({ token }: { token: string }) {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const [session, setSession] = useState<Session | null>(null);
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    if (sessionId) setSession(await apiFetch<Session>(`/interview/${sessionId}`, {}, token));
  }
  useEffect(() => { void load(); }, [sessionId]);

  async function submitAnswer(event: FormEvent) {
    event.preventDefault();
    if (!sessionId || !answer.trim()) return;
    setBusy(true); setError("");
    try {
      const next = await apiFetch<Session>(`/interview/${sessionId}/answer`, { method: "POST", body: JSON.stringify({ answer }) }, token);
      setSession(next); setAnswer("");
      if (next.is_finished) navigate(`/review/${next.id}`);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "提交失败"); }
    finally { setBusy(false); }
  }

  async function finish() {
    if (!sessionId) return;
    setBusy(true); setError("");
    try { const finished = await apiFetch<Session>(`/interview/${sessionId}/finish`, { method: "POST" }, token); setSession(finished); navigate(`/review/${finished.id}`); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "结束失败"); }
    finally { setBusy(false); }
  }

  if (!session) return <div className="center-screen">正在读取面试…</div>;
  return (
    <div className="page-stack narrow-page">
      <header className="page-header"><div><p className="eyebrow">LIVE SESSION / {session.phase.toUpperCase()}</p><h1>{session.target_role}</h1></div><span className="status-pill">QUESTION {session.phase_question_count}</span></header>
      <section className="card transcript-card">
        <div className="transcript">{session.messages.map((message, index) => <div className={`message ${message.role}`} key={`${message.role}-${index}`}><span className="message-label">{message.role === "assistant" ? "面试官" : "你"}</span><p>{message.content}</p></div>)}</div>
        {!session.is_finished ? <form className="answer-box" onSubmit={submitAnswer}><textarea value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="写下你的回答；建议包含背景、行动和结果。" rows={6} /><div className="answer-actions"><span className="hint">本地 StubProvider 不发送任何网络请求</span><div><button type="button" className="ghost" onClick={finish} disabled={busy}>提前结束</button><button className="primary" disabled={busy || !answer.trim()}>{busy ? "提交中…" : "提交回答"}</button></div></div></form> : <button className="primary" onClick={() => navigate(`/review/${session.id}`)}>查看复盘 →</button>}
        {error && <p className="error">{error}</p>}
      </section>
    </div>
  );
}

function ReviewPage({ token }: { token: string }) {
  const { sessionId } = useParams();
  const [session, setSession] = useState<Session | null>(null);
  useEffect(() => { if (sessionId) void apiFetch<Session>(`/interview/${sessionId}`, {}, token).then(setSession); }, [sessionId, token]);
  if (!session) return <div className="center-screen">正在生成复盘…</div>;
  const review = session.review;
  const transcriptMeta = review?.transcript_meta;
  return (
    <div className="page-stack">
      <header className="page-header"><div><p className="eyebrow">SESSION REVIEW</p><h1>{session.mode === "recording" ? "录音复盘完成" : "这一次，你留下了什么？"}</h1><p className="muted">复盘结果会写入本地画像，成为下一轮训练的输入。</p></div><span className="score-orb">{review?.average_score ?? "—"}<small>/ 10</small></span></header>
      {session.mode === "recording" && transcriptMeta && <section className="card recording-meta"><div className="section-label">TRANSCRIPT SIGNALS</div><div className="metric-grid"><div className="metric"><span>回答数</span><strong>{transcriptMeta.answer_count}</strong><small>answers</small></div><div className="metric"><span>估算时长</span><strong>{transcriptMeta.estimated_minutes}</strong><small>minutes</small></div><div className="metric"><span>说话人标签</span><strong>{transcriptMeta.speaker_labels_detected ? "有" : "无"}</strong><small>{transcriptMeta.recording_mode}</small></div><div className="metric"><span>分析器</span><strong>{transcriptMeta.analysis_mode === "llm" ? "LLM" : "规则"}</strong><small>analyzer</small></div></div></section>}
      <div className="grid-two"><section className="card review-card"><div className="section-label">SUMMARY</div><p>{review?.summary ?? "请先结束面试生成复盘。"}</p><h3>优势</h3><ul>{(review?.strengths ?? []).map((item) => <li key={item}>{item}</li>)}</ul><h3>需要补强</h3><ul>{(review?.weak_points ?? []).map((item) => <li key={item}>{item}</li>)}</ul></section><section className="card review-card"><div className="section-label">NEXT ACTIONS</div><ol>{(review?.action_items ?? []).map((item) => <li key={item}>{item}</li>)}</ol><Link className="primary inline-button" to={session.mode === "recording" ? "/recording" : "/"}>再练一轮 →</Link></section></div>
    </div>
  );
}

function HistoryPage({ token }: { token: string }) {
  const [sessions, setSessions] = useState<Session[]>([]);
  useEffect(() => { void apiFetch<Session[]>("/history", {}, token).then(setSessions); }, [token]);
  return <div className="page-stack"><header className="page-header"><div><p className="eyebrow">MEMORY LOG</p><h1>历史记录</h1><p className="muted">每次结束的训练都变成下一次的上下文。</p></div></header><section className="card table-card">{sessions.length === 0 ? <p className="muted">还没有训练记录，先开始一场模拟面试。</p> : sessions.map((session) => <Link className="history-row" to={`/review/${session.id}`} key={session.id}><div><strong>{session.target_role}</strong><span>{session.mode === "topic_drill" ? `专项 · ${session.topic || "未命名领域"}` : session.mode === "jd_prep" ? `JD · ${session.position || "定向备面"}` : session.mode === "recording" ? `录音复盘 · ${session.recording_mode === "solo" ? "个人" : "双人"}` : session.phase} · {session.messages.filter((message) => message.role === "user").length} 次回答</span></div><span>{session.review?.average_score ?? "—"} / 10 →</span></Link>)}</section></div>;
}

function ProfilePage({ token }: { token: string }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [topics, setTopics] = useState<Record<string, Topic>>({});
  useEffect(() => { void Promise.all([apiFetch<Profile>("/profile", {}, token), getTopics(token)]).then(([nextProfile, nextTopics]) => { setProfile(nextProfile); setTopics(nextTopics); }); }, [token]);
  if (!profile) return <div className="center-screen">正在读取画像…</div>;
  return (
    <div className="page-stack">
      <header className="page-header"><div><p className="eyebrow">LONG-TERM MEMORY</p><h1>我的画像</h1><p className="muted">每次训练都会留下掌握度和薄弱点，成为下一阶训练的输入。</p></div></header>
      <section className="metric-grid">
        <div className="card metric"><span>完成训练</span><strong>{profile.completed_sessions}</strong><small>sessions</small></div>
        <div className="card metric"><span>平均掌握度</span><strong>{profile.mastery_score}</strong><small>/ 10</small></div>
        <div className="card metric"><span>待补强点</span><strong>{profile.weak_points.length}</strong><small>weak points</small></div>
      </section>
      <section className="card review-queue-card">
        <div className="section-label">TODAY&apos;S REVIEW QUEUE</div>
        {profile.due_reviews.length ? <div className="review-queue-list">{profile.due_reviews.map((item) => <div className="review-queue-row" key={`${item.topic || "global"}-${item.point}`}><div><strong>{item.point}</strong><span>{item.topic ? topics[item.topic]?.name || item.topic : "通用表达"}</span></div><small>连续记住 {item.repetitions} 次 · 下次间隔 {item.interval_days} 天</small></div>)}</div> : <p className="muted">今天没有到期复习项。完成训练后，新发现的薄弱点会自动进入这里。</p>}
      </section>
      <section className="card"><div className="section-label">TOPIC MASTERY</div>{profile.topic_mastery.length ? <div className="mastery-list">{profile.topic_mastery.map((item) => <div className="mastery-row" key={item.topic}><div className="mastery-row-head"><strong>{topics[item.topic]?.name || item.topic}</strong><span>{item.mastery_score} / 10 · 训练 {item.attempts} 次 · {item.trend === "improving" ? "上升" : item.trend === "declining" ? "下降" : item.trend === "new" ? "建立基线" : "稳定"}</span></div><div className="progress-track"><span style={{ width: `${Math.min(100, Math.max(0, item.mastery_score * 10))}%` }} /></div>{item.weak_points.length > 0 && <small className="mastery-weak">待补强：{item.weak_points.join("、")}</small>}</div>)}</div> : <p className="muted">完成一次专项训练后，这里会出现按领域累计的掌握度。</p>}</section>
      <div className="grid-two">
        <section className="card"><div className="section-label">STRENGTHS</div>{profile.strong_points.length ? <ul>{profile.strong_points.map((point) => <li key={point}>{point}</li>)}</ul> : <p className="muted">完成训练后，这里会积累你的稳定优势。</p>}</section>
        <section className="card"><div className="section-label">BEHAVIOR SIGNALS</div>{profile.behavior_signals.length ? <ul>{profile.behavior_signals.map((signal) => <li key={signal}>{signal}</li>)}</ul> : <p className="muted">完成训练后，这里会显示表达和答题行为信号。</p>}</section>
      </div>
      <section className="card"><div className="section-label">NEXT ACTIONS</div>{profile.action_items.length ? <ol>{profile.action_items.map((item) => <li key={item}>{item}</li>)}</ol> : <p className="muted">完成第一场训练后，系统会根据复盘生成下一步行动。</p>}</section>
      <section className="card"><div className="section-label">CURRENT WEAK POINTS</div>{profile.weak_points.length ? <ul>{profile.weak_points.map((point) => <li key={point}>{point}</li>)}</ul> : <p className="muted">完成第一场训练后，这里会出现从复盘中抽取的长期薄弱点。</p>}</section>
    </div>
  );
}

export default App;
