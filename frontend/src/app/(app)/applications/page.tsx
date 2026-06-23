"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { SendHorizonal, Loader2, ChevronRight, Plus } from "lucide-react";
import { appApi } from "@/lib/api";
import { Card, EmptyState, Skeleton } from "@/components/ui";
import { STATUS_LABEL, STATUS_COLOR, fitColor, ago, cn } from "@/lib/utils";

const FILTERS = ["all", "ready", "approved", "submitted", "interviewing", "offered", "rejected"];

export default function ApplicationsPage() {
  const [filter, setFilter] = useState("all");

  const { data, isLoading } = useQuery({
    queryKey: ["apps", filter],
    queryFn: () => appApi.list(filter === "all" ? undefined : filter).then(r => r.data),
    refetchInterval: (q) => (q.state.data?.items || []).some((a: any) => a.status === "generating") ? 2000 : false,
  });

  const items = data?.items || [];
  const stats = data?.stats || {};

  return (
    <div className="p-8 max-w-4xl">
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="page-title">Applications</h1>
          <p className="page-desc">{data?.total || 0} total</p>
        </div>
        <Link href="/apply" className="btn-primary">
          <Plus className="w-4 h-4" /> New application
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-3 mb-5">
        {[
          { label: "Ready",        key: "ready",        color: "text-indigo-600" },
          { label: "Submitted",    key: "submitted",     color: "text-green-600" },
          { label: "Interviewing", key: "interviewing",  color: "text-cyan-600" },
          { label: "Offered",      key: "offered",       color: "text-emerald-600" },
        ].map(s => (
          <Card key={s.key} className="text-center p-4">
            <div className={cn("text-xl font-bold", s.color)}>{stats[s.key] || 0}</div>
            <div className="text-gray-400 text-xs mt-0.5">{s.label}</div>
          </Card>
        ))}
      </div>

      {/* Filter pills */}
      <div className="flex gap-1.5 flex-wrap mb-5">
        {FILTERS.map(f => (
          <button key={f} onClick={() => setFilter(f)} className={cn(
            "px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-colors",
            filter === f ? "bg-indigo-600 text-white" : "bg-white text-gray-500 border border-gray-200 hover:bg-gray-50"
          )}>
            {f === "all" ? "All" : STATUS_LABEL[f]}
          </button>
        ))}
      </div>

      {/* List */}
      {isLoading ? (
        <div className="space-y-3">{[1,2,3].map(i => <Skeleton key={i} className="h-16" />)}</div>
      ) : items.length === 0 ? (
        <Card className="p-0">
          <EmptyState
            icon={<SendHorizonal className="w-10 h-10" />}
            title={filter === "all" ? "No applications yet" : `No "${STATUS_LABEL[filter]}" applications`}
            action={filter === "all" ? <Link href="/apply" className="btn-primary">Generate one</Link> : undefined}
          />
        </Card>
      ) : (
        <Card className="p-0 overflow-hidden">
          {items.map((a: any, i: number) => (
            <Link key={a.id} href={`/applications/${a.id}`} className={cn(
              "flex items-center gap-4 px-5 py-4 hover:bg-gray-50 transition-colors",
              i > 0 && "border-t border-gray-100"
            )}>
              <div className="w-10 h-10 rounded-lg bg-gray-100 flex items-center justify-center text-gray-600 font-semibold text-sm shrink-0">
                {(a.job?.company || "?")[0].toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-gray-900 text-sm truncate">{a.job?.title || "Untitled"}</p>
                <p className="text-gray-500 text-xs truncate">{a.job?.company} · {ago(a.created_at)}</p>
              </div>
              {a.status === "generating" ? (
                <span className="flex items-center gap-1.5 text-xs text-blue-600">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" /> Generating
                </span>
              ) : (
                <>
                  {a.fit_score != null && (
                    <div className="text-center shrink-0">
                      <div className={cn("text-base font-bold", fitColor(a.fit_score))}>{a.fit_score.toFixed(0)}%</div>
                    </div>
                  )}
                  <span className={cn("badge shrink-0", STATUS_COLOR[a.status])}>{STATUS_LABEL[a.status]}</span>
                </>
              )}
              <ChevronRight className="w-4 h-4 text-gray-300" />
            </Link>
          ))}
        </Card>
      )}
    </div>
  );
}
