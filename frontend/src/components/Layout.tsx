import type { PropsWithChildren } from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Box,
  Activity,
  FolderOpen,
  MessageSquare,
  CheckSquare,
  Database,
} from "lucide-react";

import { ApiKeySessionCard } from "./ApiKeySessionCard";

const navItems = [
  { to: "/", label: "总览", icon: LayoutDashboard },
  { to: "/models", label: "模型库", icon: Box },
  { to: "/diagnosis", label: "诊断", icon: Activity },
  { to: "/cases", label: "案例", icon: FolderOpen },
  { to: "/chat", label: "问答", icon: MessageSquare },
  { to: "/reviews", label: "审核", icon: CheckSquare },
  { to: "/knowledge", label: "知识库", icon: Database },
];

export function Layout({ children }: PropsWithChildren) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-zone">
          <div className="brand-mark">
            <Activity size={26} strokeWidth={2.5} color="#ffffff" />
          </div>
          <div>
            <p className="eyebrow">风电智能诊断中枢</p>
            <h1 className="brand-title">WindPower Agent</h1>
          </div>
        </div>
        <nav className="nav-stack">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
              >
                <Icon size={18} strokeWidth={2} />
                {item.label}
              </NavLink>
            );
          })}
        </nav>
        <ApiKeySessionCard />
      </aside>
      <main className="page-shell">{children}</main>
    </div>
  );
}
