import {
  Brain,
  Building2,
  CheckCircle2,
  Eye,
  ShieldAlert,
  Sparkles,
  Target,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function PrepResultCards({ status }) {
  const fitReport = status.fit_report || {};
  const riskMap = status.risk_map || [];
  const jdAnalysis = status.jd_analysis || {};
  const companyReport = (() => {
    try {
      return JSON.parse(status.company_report || "{}");
    } catch {
      return {};
    }
  })();

  const highlights = fitReport.highlights || [];
  const gaps = fitReport.gaps || [];
  const skills = jdAnalysis.required_skills || [];
  const dangerNodes = riskMap.filter((item) => item.risk_level === "danger");

  return (
    <>
      <Card className="copilot-fade-up overflow-hidden border-primary/25 bg-[radial-gradient(ellipse_at_top_left,rgba(59,130,246,0.16),transparent_50%),linear-gradient(160deg,rgba(255,255,255,0.99),rgba(228,238,255,0.92))] dark:bg-[radial-gradient(ellipse_at_top_left,rgba(59,130,246,0.22),transparent_50%),linear-gradient(160deg,rgba(20,20,28,0.99),rgba(24,32,50,0.92))]">
        <CardContent className="p-5 md:p-7 xl:p-8">
          <div className="flex flex-wrap items-center gap-3 mb-5">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/15 text-primary">
              <Brain size={20} />
            </div>
            <span className="text-xl font-bold tracking-tight">
              {companyReport.company_name
                ? `${companyReport.company_name} · ${jdAnalysis.role_title || "技术岗位"}`
                : jdAnalysis.role_title || "面试准备完成"}
            </span>
            <Badge
              variant={fitReport.overall_fit >= 0.7 ? "green" : fitReport.overall_fit >= 0.5 ? "blue" : "destructive"}
              className="text-xs px-3 py-1"
            >
              匹配度 {Math.round((fitReport.overall_fit || 0) * 100)}%
            </Badge>
            {dangerNodes.length > 0 && (
              <Badge variant="destructive" className="text-xs px-3 py-1">
                {dangerNodes.length} 个高危区域
              </Badge>
            )}
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            {fitReport.coach_brief && (
              <div className="copilot-fade-up copilot-stagger-1 rounded-2xl border-2 border-primary/20 bg-gradient-to-br from-primary/8 to-primary/4 px-5 py-4 shadow-sm">
                <div className="flex items-center gap-2 mb-2.5">
                  <Eye size={14} className="text-primary/70" />
                  <span className="text-[11px] font-semibold uppercase tracking-[0.15em] text-primary/70">你需要知道</span>
                </div>
                <div className="text-[15px] leading-8 text-text/95">{fitReport.coach_brief}</div>
              </div>
            )}
            {status.risk_summary && (
              <div className="copilot-fade-up copilot-stagger-2 copilot-danger-glow rounded-2xl border-2 border-red/25 bg-gradient-to-br from-red/10 to-red/5 px-5 py-4">
                <div className="flex items-center gap-2 mb-2.5">
                  <ShieldAlert size={14} className="text-red/80" />
                  <span className="text-[11px] font-semibold uppercase tracking-[0.15em] text-red/80">高危区域</span>
                </div>
                <div className="text-[15px] leading-8 text-text/95">{status.risk_summary}</div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {(companyReport.interviewer_mindset || companyReport.main_business || companyReport.how_to_reference) && (
        <Card className="copilot-fade-up copilot-stagger-2 border-blue-500/15 bg-gradient-to-r from-blue-500/3 to-transparent">
          <CardContent className="p-5 md:p-6">
            <div className="flex items-center gap-2 mb-4">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500/12 text-blue-400">
                <Building2 size={16} />
              </div>
              <div className="font-semibold">公司情报</div>
            </div>
            <div className="grid gap-5 xl:grid-cols-3">
              {companyReport.main_business && (
                <div className="rounded-xl border border-border/60 bg-card/60 px-4 py-3">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-blue-400/70 mb-2">主营业务</div>
                  <div className="text-sm leading-7 text-text/90">{companyReport.main_business}</div>
                </div>
              )}
              {companyReport.interviewer_mindset && (
                <div className="rounded-xl border border-border/60 bg-card/60 px-4 py-3">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-blue-400/70 mb-2">面试官关注点</div>
                  <div className="text-sm leading-7 text-text/90">{companyReport.interviewer_mindset}</div>
                </div>
              )}
              {companyReport.how_to_reference && (
                <div className="rounded-xl border border-border/60 bg-card/60 px-4 py-3">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-blue-400/70 mb-2">答题时怎么引用</div>
                  <div className="text-sm leading-7 text-text/90">{companyReport.how_to_reference}</div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-5 xl:grid-cols-2">
        <Card className="copilot-fade-up copilot-stagger-3 border-green/15 bg-gradient-to-b from-green/3 to-transparent">
          <CardContent className="p-5 md:p-6">
            <div className="flex items-center gap-2 mb-4">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-green/12 text-green">
                <Target size={16} />
              </div>
              <div className="font-semibold">匹配亮点 / 差距</div>
            </div>
            <div className="space-y-2">
              {highlights.map((item, index) => (
                <div
                  key={index}
                  className="copilot-fade-up rounded-2xl border border-green/20 bg-green/8 px-4 py-3 text-sm leading-7"
                  style={{ animationDelay: `${index * 0.06}s` }}
                >
                  <span className="text-green mr-2">✓</span>
                  {typeof item === "string" ? item : item.point}
                </div>
              ))}
              {gaps.map((item, index) => (
                <div
                  key={index}
                  className="copilot-fade-up rounded-2xl border border-amber-500/20 bg-amber-500/8 px-4 py-3 text-sm leading-7"
                  style={{ animationDelay: `${(highlights.length + index) * 0.06}s` }}
                >
                  <div><span className="text-amber-500 mr-2">△</span>{typeof item === "string" ? item : item.point}</div>
                  {item.mitigation && <div className="mt-1 text-[13px] text-dim ml-5">{item.mitigation}</div>}
                </div>
              ))}
              {highlights.length === 0 && gaps.length === 0 && (
                <div className="text-sm text-dim py-2">暂无匹配数据</div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="copilot-fade-up copilot-stagger-4 border-red/15 bg-gradient-to-b from-red/3 to-transparent">
          <CardContent className="p-5 md:p-6">
            <div className="flex items-center gap-2 mb-4">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-red/12 text-red">
                <ShieldAlert size={16} />
              </div>
              <div className="font-semibold">高危路径详情</div>
            </div>
            <div className="space-y-3">
              {riskMap.length > 0 ? riskMap.map((item, index) => (
                <div
                  key={index}
                  className={cn(
                    "copilot-fade-up rounded-2xl border px-4 py-3",
                    item.risk_level === "danger"
                      ? "border-red/25 bg-red/10 copilot-danger-glow"
                      : "border-amber-500/20 bg-amber-500/8"
                  )}
                  style={{ animationDelay: `${index * 0.08}s` }}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant={item.risk_level === "danger" ? "destructive" : "secondary"} className="text-xs">
                      {item.risk_level}
                    </Badge>
                    <span className="text-sm font-semibold">{item.node_id}</span>
                  </div>
                  <div className="text-[13px] leading-6 text-dim">{item.reason}</div>
                  {item.avoidance_strategy && (
                    <div className="mt-2 text-[13px] leading-6 text-amber-300/80 font-medium">
                      {item.avoidance_strategy}
                    </div>
                  )}
                </div>
              )) : (
                <div className="rounded-2xl border border-green/20 bg-green/8 px-4 py-3 text-sm text-green flex items-center gap-2">
                  <CheckCircle2 size={15} /> 未发现高危路径，准备状态良好。
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {skills.length > 0 && (
        <Card className="copilot-fade-up copilot-stagger-4 border-border/80">
          <CardContent className="p-5 md:p-6">
            <div className="flex items-center gap-2 mb-4">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/12 text-primary">
                <Sparkles size={16} />
              </div>
              <div className="font-semibold">JD 技术栈权重</div>
            </div>
            <div className="grid gap-3 lg:grid-cols-2">
              {skills.map((item, index) => (
                <div
                  key={index}
                  className="copilot-fade-up rounded-2xl border border-border/75 bg-card/75 px-4 py-3 hover:border-primary/20 transition-colors"
                  style={{ animationDelay: `${index * 0.04}s` }}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-semibold">{item.skill}</div>
                    <Badge variant={item.weight === "core" ? "blue" : item.weight === "preferred" ? "secondary" : "outline"}>
                      {item.weight}
                    </Badge>
                  </div>
                  {item.jd_evidence && <div className="mt-1 text-[13px] leading-6 text-dim">{item.jd_evidence}</div>}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </>
  );
}
