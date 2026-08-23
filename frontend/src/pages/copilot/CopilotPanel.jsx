import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Eye,
  Loader2,
  Sparkles,
  Target,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

function PanelEmptyState({ active = false }) {
  if (active) {
    return (
      <div className="space-y-2 mt-2">
        <div className="h-2 w-full rounded-full bg-primary/20 copilot-shimmer-bg" />
        <div className="h-2 w-2/3 rounded-full bg-primary/10 copilot-shimmer-bg" style={{ animationDelay: "0.2s" }} />
      </div>
    );
  }

  return (
    <div className="h-4 w-full flex items-center">
      <div className="h-[2px] w-full bg-dim/10 rounded-full" />
    </div>
  );
}

export default function CopilotPanel({
  update,
  riskAlert,
  streamingAnswer,
  answerLoading,
  answerStreaming,
  monitorData,
}) {
  const recommendedPoints = update?.recommended_points || [];
  const children = update?.children || [];
  const prepHint = update?.prep_hint;
  const hasData = !!update;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between pb-2 border-b border-border/40">
        <span className="text-[10px] uppercase tracking-[0.2em] font-bold text-dim/50">Console Uplink</span>
        <div className="flex gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-red/40" />
          <span className="w-1.5 h-1.5 rounded-full bg-amber-500/40" />
          <span className="w-1.5 h-1.5 rounded-full bg-green/40" />
        </div>
      </div>

      <div className="copilot-fade-up group">
        <div className="flex items-center gap-2.5 mb-2">
          <div className={cn("flex items-center justify-center w-6 h-6 rounded-md", monitorData?.last_answer_feedback ? "bg-cyan-500/10 text-cyan-400" : "bg-dim/10 text-dim/40")}>
            <Eye size={12} />
          </div>
          <span className={cn("text-[11px] font-bold uppercase tracking-[0.15em]", monitorData?.last_answer_feedback ? "text-cyan-400/90" : "text-dim/40")}>回答评价</span>
        </div>
        <div className="pl-[34px]">
          {monitorData?.last_answer_feedback ? (
            <>
              <p className="text-[13px] leading-6 text-text/90 font-medium">{monitorData.last_answer_feedback}</p>
              {monitorData.uncovered_topics?.length > 0 && (
                <div className="mt-2 pt-2 border-t border-border/30">
                  <span className="text-[11px] text-dim/60 mr-1.5">未覆盖:</span>
                  <span className="text-[11px] text-dim/80 font-medium">{monitorData.uncovered_topics.join("、")}</span>
                </div>
              )}
            </>
          ) : (
            <PanelEmptyState active={false} />
          )}
        </div>
      </div>

      <div className="w-full h-px bg-border/40 ml-[34px] my-4" />

      <div className="copilot-fade-up copilot-stagger-1 group">
        <div className="flex items-center gap-2.5 mb-2">
          <div className={cn("flex items-center justify-center w-6 h-6 rounded-md", hasData ? "bg-violet-500/10 text-violet-400" : "bg-dim/10 text-dim/40")}>
            <Target size={12} />
          </div>
          <span className={cn("text-[11px] font-bold uppercase tracking-[0.15em]", hasData ? "text-violet-400/90" : "text-dim/40")}>当前考察</span>
        </div>
        <div className="pl-[34px]">
          {hasData ? (
            <div className="flex items-center gap-3 flex-wrap">
              <Badge variant="outline" className="border-violet-500/30 text-violet-400 bg-violet-500/5 h-[22px] px-2 shadow-sm rounded-md uppercase tracking-wider text-[10px]">
                {update.intent || "unknown"}
              </Badge>
              {update.topic && <span className="text-[13px] font-semibold">{update.topic}</span>}
              {update.confidence > 0 && (
                <span className="text-[11px] text-violet-400/60 ml-auto tabular-nums font-bold">{Math.round(update.confidence * 100)}% Match</span>
              )}
            </div>
          ) : (
            <PanelEmptyState active={false} />
          )}
        </div>
      </div>

      <div className="w-full h-px bg-border/40 ml-[34px] my-4" />

      <div className="copilot-fade-up copilot-stagger-2 group">
        <div className="flex items-center gap-2.5 mb-2">
          <div className={cn("flex items-center justify-center w-6 h-6 rounded-md", recommendedPoints.length > 0 ? "bg-primary/10 text-primary" : "bg-dim/10 text-dim/40")}>
            <Sparkles size={12} />
          </div>
          <span className={cn("text-[11px] font-bold uppercase tracking-[0.15em]", recommendedPoints.length > 0 ? "text-primary/90" : "text-dim/40")}>核心要点建议</span>
        </div>
        <div className="pl-[34px]">
          {recommendedPoints.length > 0 ? (
            <>
              <ul className="space-y-2">
                {recommendedPoints.map((point, index) => (
                  <li key={index} className="text-[13px] leading-6 flex items-start gap-2.5 text-text/90">
                    <span className="text-primary/60 mt-1 shrink-0">-</span>
                    <span>{point}</span>
                  </li>
                ))}
              </ul>
              {prepHint?.redirect_suggestion && (
                <div className="mt-3.5 pt-3 border-t border-border/30 text-[12px] leading-5 bg-primary/5 rounded-lg p-2.5">
                  <span className="font-bold text-primary/80 mr-2 uppercase tracking-wide text-[10px]">引导方向</span>
                  <span className="text-text/80">{prepHint.redirect_suggestion}</span>
                </div>
              )}
            </>
          ) : (
            <PanelEmptyState active={false} />
          )}
        </div>
      </div>

      <div className="w-full h-px bg-border/40 ml-[34px] my-4" />

      <div className="copilot-fade-up copilot-stagger-3 group">
        <div className="flex items-center gap-2.5 mb-2">
          <div className={cn(
            "flex items-center justify-center w-6 h-6 rounded-md transition-colors",
            answerLoading || answerStreaming ? "bg-green/15 text-green" : streamingAnswer ? "bg-green/10 text-green" : "bg-dim/10 text-dim/40"
          )}>
            {answerLoading ? <Loader2 size={12} className="animate-spin" /> : <CheckCircle2 size={12} />}
          </div>
          <span className={cn("text-[11px] font-bold uppercase tracking-[0.15em]", (answerLoading || streamingAnswer) ? "text-green/90" : "text-dim/40")}>流式参考打样</span>
          {(answerLoading || answerStreaming) && (
            <span className="ml-auto flex items-center gap-1.5 text-[9px] font-bold tracking-[0.2em] text-green/80 bg-green/10 border border-green/25 rounded-md px-1.5 py-0.5 uppercase">
              <span className="inline-block w-1 h-1 rounded-full bg-green animate-pulse" />
              {answerLoading ? "Waiting" : "Streaming"}
            </span>
          )}
        </div>
        <div className="pl-[34px]">
          {answerLoading && !streamingAnswer ? (
            <div className="space-y-2">
              <div className="h-2.5 w-full rounded-full bg-green/15 copilot-shimmer-bg" />
              <div className="h-2.5 w-[92%] rounded-full bg-green/12 copilot-shimmer-bg" style={{ animationDelay: "0.15s" }} />
              <div className="h-2.5 w-[88%] rounded-full bg-green/10 copilot-shimmer-bg" style={{ animationDelay: "0.3s" }} />
              <div className="h-2.5 w-[62%] rounded-full bg-green/8 copilot-shimmer-bg" style={{ animationDelay: "0.45s" }} />
              <p className="text-[11px] text-green/65 font-medium pt-1 flex items-center gap-1.5">
                <Loader2 size={10} className="animate-spin" />
                Answer Coach 首 token 生成中...
              </p>
            </div>
          ) : streamingAnswer ? (
            <p className="text-[13px] leading-7 text-text/90 whitespace-pre-wrap font-medium">
              {streamingAnswer}
              {answerStreaming && <span className="copilot-blink inline-block w-[2px] h-[1em] bg-green/80 translate-y-[2px] ml-[1px]" />}
            </p>
          ) : (
            <PanelEmptyState active={false} />
          )}
        </div>
      </div>

      <div className="w-full h-px bg-border/40 ml-[34px] my-4" />

      <div className="copilot-fade-up copilot-stagger-4 group">
        <div className="flex items-center gap-2.5 mb-2">
          <div className={cn("flex items-center justify-center w-6 h-6 rounded-md", children.length > 0 ? "bg-amber-500/10 text-amber-500" : "bg-dim/10 text-dim/40")}>
            <ChevronRight size={12} />
          </div>
          <span className={cn("text-[11px] font-bold uppercase tracking-[0.15em]", children.length > 0 ? "text-amber-500/90" : "text-dim/40")}>预测追问方向</span>
        </div>
        <div className="pl-[34px]">
          {children.length > 0 ? (
            <div className="space-y-3">
              {children.map((child, index) => (
                <div key={index} className="rounded-xl border border-border/60 bg-background/40 px-3.5 py-3 shadow-sm">
                  <div className="font-bold text-[12px] text-text border-b border-border/40 pb-1.5 mb-1.5">{child.topic}</div>
                  {child.question && (
                    <div className="text-[12px] text-dim/80 leading-5 italic">"{child.question}"</div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <PanelEmptyState active={false} />
          )}
        </div>
      </div>

      {riskAlert && (
        <>
          <div className="w-full h-px bg-border/40 ml-[34px] my-4" />
          <div className="copilot-fade-up copilot-danger-glow group">
            <div className="flex items-center gap-2.5 mb-2">
              <div className="flex items-center justify-center w-6 h-6 rounded-md bg-amber-500/10 text-amber-400">
                <AlertTriangle size={12} />
              </div>
              <span className="text-[11px] font-bold uppercase tracking-[0.15em] text-amber-400">注意</span>
            </div>
            <div className="pl-[34px]">
              <p className="text-[13px] leading-6 text-amber-500 font-medium">{riskAlert.message}</p>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
