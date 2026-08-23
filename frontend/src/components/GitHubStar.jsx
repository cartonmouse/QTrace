import { useEffect, useState } from "react";
import { Star } from "lucide-react";
import { cn } from "@/lib/utils";

const REPO = "clearsnowsong/QTrace";
const CACHE_KEY = "gh-stars";

// GitHub 星标胶囊:实时拉 star 数,先用本地缓存的上次值渲染再后台刷新,避免闪动。
export default function GitHubStar({ className }) {
  const [stars, setStars] = useState(() => {
    const c = Number(localStorage.getItem(CACHE_KEY));
    return Number.isFinite(c) && c > 0 ? c : null;
  });

  useEffect(() => {
    let active = true;
    fetch(`https://api.github.com/repos/${REPO}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => {
        if (!active || typeof d.stargazers_count !== "number") return;
        setStars(d.stargazers_count);
        localStorage.setItem(CACHE_KEY, String(d.stargazers_count));
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  return (
    <a
      href={`https://github.com/${REPO}`}
      target="_blank"
      rel="noopener noreferrer"
      aria-label="Star QTrace on GitHub"
      className={cn(
        "group inline-flex items-center gap-2 rounded-full border border-border bg-card/80 px-3 py-1.5 text-sm font-medium text-text backdrop-blur-sm transition-colors hover:border-primary/40 hover:bg-card",
        className,
      )}
    >
      <Star
        size={15}
        className="text-primary fill-primary/25 transition-all duration-500 ease-out group-hover:rotate-[360deg] group-hover:scale-110 group-hover:fill-primary"
      />
      <span className="hidden sm:inline">Star on GitHub</span>
      {stars !== null && (
        <>
          <span className="h-4 w-px bg-border" />
          <span className="tabular-nums text-dim">{stars.toLocaleString()}</span>
        </>
      )}
    </a>
  );
}
