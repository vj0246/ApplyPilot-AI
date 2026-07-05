"use client";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import {
  LayoutDashboard, FileText, Briefcase, Zap,
  SendHorizonal, Settings, LogOut, ChevronRight,
  Link2, Send, BrainCircuit,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/useAuth";

// The two things this product is actually for sit at the top: filling a
// real form and mailing an application. Everything below them exists to
// make those two work better (the resume and the memory feed the AI),
// and the tracking pages sit last because they are records, not actions.
const NAV: {
  href: string; label: string; icon: any;
  tab?: string; section?: string;
}[] = [
  { href: "/dashboard", label: "Home", icon: LayoutDashboard },

  { section: "Apply", href: "/apply?tab=googleform", tab: "googleform", label: "Fill a Form", icon: Link2 },
  { href: "/apply?tab=email", tab: "email", label: "Mail an Application", icon: Send },

  { section: "Your Profile", href: "/resume", label: "My Resume", icon: FileText },
  { href: "/settings?tab=knowledge", tab: "knowledge", label: "My Memory", icon: BrainCircuit },
  { href: "/settings", label: "Settings", icon: Settings },

  { section: "More Tools", href: "/apply?tab=generate", tab: "generate", label: "Full Application Kit", icon: Zap },
  { href: "/jobs", label: "Job Postings", icon: Briefcase },
  { href: "/applications", label: "Applications", icon: SendHorizonal },
];

function NavLinks() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const currentTab = searchParams.get("tab");

  return (
    <>
      {NAV.map(({ href, label, icon: Icon, tab, section }) => {
        const basePath = href.split("?")[0];
        // Entries that share a path are told apart by their tab query
        // parameter; an entry without one only lights up when no sibling
        // with a tab owns the current URL.
        const samePathTabs = NAV.filter(n => n.href.split("?")[0] === basePath && n.tab);
        const active = pathname === basePath || pathname.startsWith(basePath + "/")
          ? tab
            ? currentTab === tab
            : !samePathTabs.some(n => n.tab === currentTab)
          : false;
        return (
          <div key={href}>
            {section && (
              <p className="px-3 pt-4 pb-1 text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                {section}
              </p>
            )}
            <Link
              href={href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors group",
                active
                  ? "bg-indigo-50 text-indigo-700"
                  : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
              )}
            >
              <Icon className={cn("w-4 h-4 shrink-0", active ? "text-indigo-600" : "text-gray-400 group-hover:text-gray-600")} />
              <span className="flex-1">{label}</span>
              {active && <ChevronRight className="w-3.5 h-3.5 text-indigo-400" />}
            </Link>
          </div>
        );
      })}
    </>
  );
}

export function Sidebar() {
  const { user, logout } = useAuth();

  return (
    <aside className="w-60 shrink-0 bg-white border-r border-gray-200 flex flex-col h-screen sticky top-0">
      {/* Logo */}
      <div className="h-16 flex items-center px-5 border-b border-gray-100">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-gray-900 text-base">ApplyPilot</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-2 space-y-0.5 overflow-y-auto">
        <Suspense fallback={null}>
          <NavLinks />
        </Suspense>
      </nav>

      {/* User */}
      <div className="border-t border-gray-100 p-3">
        <div className="flex items-center gap-3 px-2 py-2 mb-1">
          <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 font-semibold text-sm shrink-0">
            {user?.full_name?.[0]?.toUpperCase() || "U"}
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">{user?.full_name || "User"}</p>
            <p className="text-xs text-gray-400 truncate">{user?.email}</p>
          </div>
        </div>
        <button
          onClick={logout}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-500 hover:bg-red-50 hover:text-red-600 transition-colors"
        >
          <LogOut className="w-4 h-4" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
