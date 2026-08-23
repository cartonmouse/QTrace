import { cn } from "@/lib/utils";

// TechSpar 的页面结构与交互作为基线；品牌资产保持 QTrace 自有图标。
export default function Logo({ className }) {
  return <img src="/qtrace-icon.png" alt="问迹 QTrace" role="img" className={cn("shrink-0 block object-contain", className)} />;
}
