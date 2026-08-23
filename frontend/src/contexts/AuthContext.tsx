import { useState, useEffect, type ReactNode } from "react";
import AuthContext, { type AuthUser } from "./AuthContextBase";

function onboardingSkipKey(user: AuthUser | null) {
  const identity = user?.id ?? user?.email ?? user?.username;
  return identity ? `qtrace_onboarding_skipped:${String(identity)}` : null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem("token")
  );
  const [loading, setLoading] = useState(() =>
    Boolean(localStorage.getItem("token"))
  );
  // 用户尚未配齐自己的 LLM/Embedding → 进首登引导。由 /api/settings 的 configured 决定。
  const [needsOnboarding, setNeedsOnboarding] = useState(false);

  function login(tokenStr: string, userData: AuthUser) {
    localStorage.setItem("token", tokenStr);
    localStorage.setItem("user", JSON.stringify(userData));
    setLoading(true); // re-validate + load provider status before routing
    setToken(tokenStr);
    setUser(userData);
  }

  function logout() {
    const skipKey = onboardingSkipKey(user);
    if (skipKey) localStorage.removeItem(skipKey);
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setToken(null);
    setUser(null);
    setNeedsOnboarding(false);
  }

  function skipOnboarding() {
    const skipKey = onboardingSkipKey(user);
    if (skipKey) localStorage.setItem(skipKey, "1");
    setNeedsOnboarding(false);
  }

  useEffect(() => {
    if (!token) return; // logout already cleared user/state; nothing to load
    let cancelled = false;
    const headers = { Authorization: `Bearer ${token}` };
    Promise.all([
      fetch("/api/profile", { headers }),
      fetch("/api/settings", { headers }),
    ])
      .then(async ([profileRes, settingsRes]) => {
        if (cancelled) return;
        if (!profileRes.ok) {
          logout();
          return;
        }
        const stored = localStorage.getItem("user");
        const storedUser = stored ? (JSON.parse(stored) as AuthUser) : null;
        if (storedUser) setUser(storedUser);
        if (settingsRes.ok) {
          const data = (await settingsRes.json()) as {
            configured?: { llm?: boolean; embedding?: boolean };
            llm_configured?: boolean;
            embedding_configured?: boolean;
          };
          const llmConfigured = data.configured?.llm ?? data.llm_configured ?? false;
          const embeddingConfigured = data.configured?.embedding ?? data.embedding_configured ?? false;
          const skipKey = onboardingSkipKey(storedUser);
          const skipped = Boolean(skipKey && localStorage.getItem(skipKey) === "1");
          setNeedsOnboarding(!(llmConfigured && embeddingConfigured) && !skipped);
        }
      })
      .catch(() => {
        if (!cancelled) logout();
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        needsOnboarding,
        setNeedsOnboarding,
        skipOnboarding,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
