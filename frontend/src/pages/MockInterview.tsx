import { useRef, type KeyboardEvent } from "react";
import { ArrowRight, BriefcaseBusiness, MessageCircle, Sparkles } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { cn } from "@/lib/utils";
import JobPrep from "./JobPrep";
import ResumeInterview from "./ResumeInterview";
import "./qtrace-interview.css";

type InterviewMode = "live" | "targeted";

const MODES = [
  {
    key: "live" as const,
    icon: MessageCircle,
    title: "实时模拟",
    shortTitle: "实时模拟",
    requirement: "简历必选 · JD 选填",
    description: "AI 面试官根据回答动态追问，适合完整演练一轮真实面试。",
  },
  {
    key: "targeted" as const,
    icon: BriefcaseBusiness,
    title: "岗位备面",
    shortTitle: "岗位备面",
    requirement: "JD 必填 · 简历选填",
    description: "先拆解岗位要求和匹配度，再集中训练高概率问题。",
  },
];

export default function MockInterview() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const selectedMode: InterviewMode =
    searchParams.get("mode") === "targeted" ? "targeted" : "live";
  const selected = MODES.find((mode) => mode.key === selectedMode) ?? MODES[0];

  const selectMode = (mode: InterviewMode) => {
    const next = new URLSearchParams(searchParams);
    next.set("mode", mode);
    setSearchParams(next, { replace: true });
  };

  const handleTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    let nextIndex = index;
    if (event.key === 'ArrowRight') nextIndex = (index + 1) % MODES.length;
    if (event.key === 'ArrowLeft') nextIndex = (index - 1 + MODES.length) % MODES.length;
    if (event.key === 'Home') nextIndex = 0;
    if (event.key === 'End') nextIndex = MODES.length - 1;
    const nextMode = MODES[nextIndex];
    selectMode(nextMode.key);
    tabRefs.current[nextIndex]?.focus();
  };

  return (
    <div className="qtrace-interview-page">
      <div className="qtrace-interview-intro">
        <header className="qtrace-interview-heading">
          <div className="qtrace-interview-index">01 / INTERVIEW LOOP</div>
          <div className="qtrace-interview-kicker">
            <span className="qtrace-interview-signal" aria-hidden="true" />
            PERSONAL INTERVIEW OS
          </div>
          <h1>准备下一次回答。</h1>
          <p>
            把一次面试拆成可追踪的训练路径。先选择当前目标，再让系统按你的资料组织问题。
          </p>
        </header>

        <aside className="qtrace-interview-readout" aria-label="当前训练状态">
          <div className="qtrace-interview-readout-label">CURRENT ROUTE</div>
          <div className="qtrace-interview-readout-value">{selected.title}</div>
          <div className="qtrace-interview-readout-rule" />
          <dl>
            <div>
              <dt>MODE</dt>
              <dd>{selectedMode === "live" ? "LIVE / ADAPTIVE" : "TARGET / FOCUS"}</dd>
            </div>
            <div>
              <dt>INPUT</dt>
              <dd>{selected.requirement}</dd>
            </div>
          </dl>
        </aside>
      </div>

      <section className="qtrace-interview-selector" aria-labelledby="interview-mode-title">
        <div className="qtrace-interview-selector-head">
          <div>
            <div className="qtrace-interview-index">02 / SELECT MODE</div>
            <h2 id="interview-mode-title">选择训练路径</h2>
          </div>
          <div className="qtrace-interview-selector-note">一次只推进一个主任务</div>
        </div>

        <div role="tablist" aria-label="面试训练方式" className="qtrace-interview-tabs">
          {MODES.map((mode, index) => {
            const Icon = mode.icon;
            const active = selectedMode === mode.key;
            return (
              <button
                key={mode.key}
                ref={(node) => { tabRefs.current[index] = node; }}
                id={`interview-mode-${mode.key}`}
                type="button"
                role="tab"
                aria-selected={active}
                aria-controls="interview-mode-panel"
                tabIndex={active ? 0 : -1}
                onClick={() => selectMode(mode.key)}
                onKeyDown={(event) => handleTabKeyDown(event, index)}
                className={cn("qtrace-interview-tab", active && "is-active")}
              >
                <span className="qtrace-interview-tab-index">0{index + 1}</span>
                <span className="qtrace-interview-tab-icon" aria-hidden="true"><Icon size={18} /></span>
                <span className="qtrace-interview-tab-copy">
                  <strong>{mode.title}</strong>
                  <small>{mode.requirement}</small>
                </span>
                <ArrowRight className="qtrace-interview-tab-arrow" aria-hidden="true" size={17} />
              </button>
            );
          })}
        </div>

        <div className="qtrace-interview-route-note">
          <div className="qtrace-interview-route-copy">
            <Sparkles size={15} aria-hidden="true" />
            <span><strong>{selected.requirement}</strong>：{selected.description}</span>
          </div>
          <Link to="/topic-drill" className="qtrace-interview-secondary-link">
            按技术领域练习 <ArrowRight size={14} aria-hidden="true" />
          </Link>
        </div>
      </section>

      <div
        id="interview-mode-panel"
        role="tabpanel"
        aria-labelledby={`interview-mode-${selectedMode}`}
        className="qtrace-interview-panel"
      >
        {selectedMode === "live" ? <ResumeInterview embedded /> : <JobPrep embedded />}
      </div>
    </div>
  );
}
