import { cn } from "@/lib/utils";

// QTrace 自有品牌资产；工作台和认证入口共用同一份标识。
export default function Logo({ className }) {
  return <img src="/qtrace-icon.png" alt="问迹 QTrace" role="img" className={cn("shrink-0 block object-contain", className)} />;
}
