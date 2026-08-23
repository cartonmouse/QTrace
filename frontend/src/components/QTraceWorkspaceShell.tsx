import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  ArrowUpRight,
  BrainCircuit,
  ChevronLeft,
  ChevronRight,
  FileText,
  GitBranch,
  History,
  LogOut,
  Menu,
  Moon,
  Network,
  Settings2,
  Sun,
  Target,
  UserRound,
  X,
} from "lucide-react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import useAuth from "../hooks/useAuth";
import Logo from "./Logo";
import "./qtrace-workspace.css";

type NavItem = {
  path: string;
  label: string;
  note: string;
  icon: typeof UserRound;
};

type NavGroup = {
  label: string;
  items: NavItem[];
};

const NAV_GROUPS: NavGroup[] = [
  {
    label: "训练路径",
    items: [
      { path: "/mock-interview", label: "面试训练", note: "模拟现场", icon: FileText },
      { path: "/topic-drill", label: "专项训练", note: "补齐薄弱点", icon: Target },
      { path: "/copilot", label: "面试 Copilot", note: "预测追问", icon: BrainCircuit },
    ],
  },
  {
    label: "长期记忆",
    items: [
      { path: "/profile", label: "我的画像", note: "掌握度与复习", icon: UserRound },
      { path: "/personal-agent", label: "成长 Agent", note: "生成下一步", icon: Network },
      { path: "/history", label: "历史记录", note: "回看训练轨迹", icon: History },
    ],
  },
  {
    label: "素材与图谱",
    items: [
      { path: "/resume-manager", label: "简历管理", note: "维护项目证据", icon: FileText },
      { path: "/knowledge", label: "训练领域", note: "主题与问题", icon: GitBranch },
      { path: "/graph", label: "知识图谱", note: "关系与路径", icon: Network },
    ],
  },
];

const ALL_NAV_ITEMS = NAV_GROUPS.flatMap((group) => group.items);

function getCurrentLabel(pathname: string) {
  const current = ALL_NAV_ITEMS.find((item) => pathname.startsWith(item.path));
  if (pathname === "/settings") return "模型设置";
  if (pathname === "/recording") return "录音复盘";
  return current?.label || "工作台";
}

export default function QTraceWorkspaceShell({ children }: { children: ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [compact, setCompact] = useState(
    () => localStorage.getItem("qtrace_shell_compact") === "true"
  );
  const [mobileOpen, setMobileOpen] = useState(false);
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "dark");

  useEffect(() => {
    localStorage.setItem("qtrace_shell_compact", String(compact));
  }, [compact]);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const currentLabel = useMemo(
    () => getCurrentLabel(location.pathname),
    [location.pathname]
  );

  const closeMobile = () => setMobileOpen(false);
  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  const navigation = (
    <nav className="qtrace-nav" aria-label="QTrace 主导航">
      {NAV_GROUPS.map((group) => (
        <section className="qtrace-nav-group" key={group.label}>
          <div className="qtrace-nav-group-label">
            <span>{group.label}</span>
            <span aria-hidden="true">/</span>
          </div>
          <div className="qtrace-nav-items">
            {group.items.map((item, index) => {
              const Icon = item.icon;
              return (
                <NavLink
                  className={({ isActive }) =>
                    `qtrace-nav-link${isActive ? " is-active" : ""}`
                  }
                  end={item.path === "/profile"}
                  key={item.path}
                  onClick={closeMobile}
                  to={item.path}
                >
                  <span className="qtrace-nav-index" aria-hidden="true">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <Icon aria-hidden="true" className="qtrace-nav-icon" size={16} />
                  <span className="qtrace-nav-copy">
                    <span className="qtrace-nav-title">{item.label}</span>
                    <span className="qtrace-nav-note">{item.note}</span>
                  </span>
                  <ArrowUpRight aria-hidden="true" className="qtrace-nav-arrow" size={14} />
                </NavLink>
              );
            })}
          </div>
        </section>
      ))}
    </nav>
  );

  return (
    <div className={`qtrace-shell${compact ? " is-compact" : ""}`}>
      <a className="qtrace-skip-link" href="#qtrace-main">
        跳到主要内容
      </a>

      <aside className={`qtrace-shell-sidebar${mobileOpen ? " is-mobile-open" : ""}`}>
        <div className="qtrace-brand-lockup">
          <button
            aria-label="回到工作台"
            className="qtrace-brand-button"
            onClick={() => navigate("/profile")}
            type="button"
          >
            <Logo className="qtrace-brand-logo" />
          </button>
          <div className="qtrace-brand-copy">
            <span className="qtrace-brand-name">问迹</span>
            <span className="qtrace-brand-meta">QTRACE / GROWTH LAB</span>
          </div>
          <button
            aria-label="关闭导航"
            className="qtrace-mobile-close"
            onClick={closeMobile}
            type="button"
          >
            <X size={18} />
          </button>
        </div>

        <div className="qtrace-sidebar-rule" />
        <div className="qtrace-sidebar-kicker">
          <span>PERSONAL INTERVIEW OS</span>
          <span className="qtrace-status-dot" aria-hidden="true" />
        </div>

        {navigation}

        <div className="qtrace-sidebar-footer">
          <div className="qtrace-sidebar-actions">
            <button
              className="qtrace-sidebar-action"
              onClick={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
              type="button"
            >
              {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
              <span>{theme === "dark" ? "切换浅色" : "切换深色"}</span>
            </button>
            <button
              className="qtrace-sidebar-action"
              onClick={() => navigate("/settings")}
              type="button"
            >
              <Settings2 size={15} />
              <span>模型设置</span>
            </button>
          </div>
          <div className="qtrace-account-row">
            <div className="qtrace-account-mark" aria-hidden="true">
              {(user?.name || user?.email || "Q").slice(0, 1).toUpperCase()}
            </div>
            <span className="qtrace-account-name">{user?.name || user?.email || "本地学习者"}</span>
            <button
              aria-label="退出登录"
              className="qtrace-logout-button"
              onClick={handleLogout}
              type="button"
            >
              <LogOut size={15} />
            </button>
          </div>
          <button
            aria-label={compact ? "展开导航" : "收起导航"}
            className="qtrace-compact-toggle"
            onClick={() => setCompact((current) => !current)}
            type="button"
          >
            {compact ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
            <span>{compact ? "展开导航" : "收起导航"}</span>
          </button>
        </div>
      </aside>

      {mobileOpen && (
        <button
          aria-label="关闭导航遮罩"
          className="qtrace-mobile-scrim"
          onClick={closeMobile}
          type="button"
        />
      )}

      <div className="qtrace-shell-main">
        <header className="qtrace-command-bar">
          <button
            aria-label="打开导航"
            className="qtrace-mobile-menu"
            onClick={() => setMobileOpen(true)}
            type="button"
          >
            <Menu size={18} />
          </button>
          <div className="qtrace-command-path">
            <span className="qtrace-command-code">QTRACE / WORKSPACE</span>
            <span className="qtrace-command-divider" aria-hidden="true">
              /
            </span>
            <strong>{currentLabel}</strong>
          </div>
          <div className="qtrace-command-status">
            <span className="qtrace-live-mark" aria-hidden="true" />
            <span>LOCAL SESSION</span>
            <span className="qtrace-command-sequence">{location.pathname === "/profile" ? "01" : "--"}</span>
          </div>
        </header>
        <main id="qtrace-main" className="qtrace-shell-content">
          {children}
        </main>
      </div>
    </div>
  );
}
