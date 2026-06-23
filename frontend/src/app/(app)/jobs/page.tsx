"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import {
  Link2, Trash2, Loader2, CheckCircle2,
  AlertCircle, Clock, Briefcase, MapPin, DollarSign,
} from "lucide-react";
import { jobApi } from "@/lib/api";
import { Card, EmptyState, Skeleton, Badge } from "@/components/ui";
import { cn, ago, fmtSalary } from "@/lib/utils";

export default function JobsPage() {
  const qc = useQueryClient();
  const [mode, setMode] = useState<"url" | "text">("url");
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => jobApi.list().then(r => r.data),
    refetchInterval: (q) => (q.state.data?.items || []).some((j: any) => j.status === "processing") ? 2500 : false,
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => jobApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["jobs"] }); toast.success("Job removed"); },
  });

  const submit = async () => {
    if (mode === "url" && !url.trim()) return toast.error("Paste a job URL");
    if (mode === "text" && text.trim().length < 50) return toast.error("Paste the full job description");
    setSubmitting(true);
    try {
      await jobApi.create(mode === "url" ? { url: url.trim() } : { text: text.trim() });
      toast.success("Job added — AI is parsing it now");
      setUrl(""); setText("");
      qc.invalidateQueries({ queryKey: ["jobs"] });
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to add job");
    } finally {
      setSubmitting(false);
    }
  };

  const items = data?.items || [];

  return (
    <div className="p-8 max-w-3xl">
      <div className="page-header">
        <h1 className="page-title">Job Postings</h1>
        <p className="page-desc">Add a job by URL or paste the description — AI extracts everything</p>
      </div>

      {/* Add job card */}
      <Card className="mb-6">
        <div className="flex gap-2 mb-4">
          <TabBtn active={mode === "url"} onClick={() => setMode("url")}>Job URL</TabBtn>
          <TabBtn active={mode === "text"} onClick={() => setMode("text")}>Paste description</TabBtn>
        </div>

        {mode === "url" ? (
          <div className="flex gap-2">
            <div className="flex-1 flex items-center gap-2 input">
              <Link2 className="w-4 h-4 text-gray-400 shrink-0" />
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && submit()}
                placeholder="https://jobs.lever.co/company/role"
                className="flex-1 bg-transparent border-0 p-0 focus:outline-none focus:ring-0 text-sm"
              />
            </div>
            <button onClick={submit} disabled={submitting} className="btn-primary px-5">
              {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : "Add"}
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={6}
              placeholder="Paste the full job description here…"
              className="input resize-none"
            />
            <button onClick={submit} disabled={submitting} className="btn-primary">
              {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : "Analyze job"}
            </button>
          </div>
        )}
      </Card>

      {/* Job list */}
      {isLoading ? (
        <div className="space-y-3">{[1,2].map(i => <Skeleton key={i} className="h-24" />)}</div>
      ) : items.length === 0 ? (
        <EmptyState icon={<Briefcase className="w-10 h-10" />} title="No jobs added yet" description="Paste a URL or job description above" />
      ) : (
        <div className="space-y-3">
          {items.map((j: any) => (
            <Card key={j.id} className="p-4">
              <div className="flex items-start gap-4">
                <div className="w-11 h-11 bg-gray-100 rounded-lg flex items-center justify-center text-gray-600 font-semibold text-sm shrink-0">
                  {(j.company || "?")[0].toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <p className="font-semibold text-gray-900 text-sm">
                      {j.status === "processing" ? "Parsing…" : (j.title || "Unknown role")}
                    </p>
                    <StatusBadge status={j.status} />
                  </div>
                  <p className="text-gray-500 text-sm">{j.company}</p>
                  <div className="flex items-center gap-3 mt-2 text-xs text-gray-400 flex-wrap">
                    {j.location && <span className="flex items-center gap-1"><MapPin className="w-3 h-3" />{j.location}</span>}
                    {j.work_type && <Badge className="bg-gray-100 text-gray-600 capitalize">{j.work_type}</Badge>}
                    {fmtSalary(j.salary_min, j.salary_max, j.salary_currency) && (
                      <span className="flex items-center gap-1"><DollarSign className="w-3 h-3" />{fmtSalary(j.salary_min, j.salary_max, j.salary_currency)}</span>
                    )}
                    <span>{ago(j.created_at)}</span>
                  </div>
                  {j.required_skills?.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {j.required_skills.slice(0, 6).map((s: string) => (
                        <span key={s} className="badge bg-indigo-50 text-indigo-700">{s}</span>
                      ))}
                      {j.required_skills.length > 6 && (
                        <span className="text-xs text-gray-400 self-center">+{j.required_skills.length - 6} more</span>
                      )}
                    </div>
                  )}
                  {j.error_msg && <p className="text-red-500 text-xs mt-2">{j.error_msg}</p>}
                </div>
                <button onClick={() => { if (confirm("Delete this job?")) deleteMut.mutate(j.id); }} className="p-2 text-gray-400 hover:text-red-500 transition-colors shrink-0">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function TabBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick} className={cn(
      "px-3.5 py-1.5 rounded-lg text-sm font-medium transition-colors",
      active ? "bg-indigo-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
    )}>
      {children}
    </button>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { icon: any; cls: string; label: string }> = {
    ready:      { icon: CheckCircle2, cls: "bg-green-50 text-green-700", label: "Ready" },
    processing: { icon: Loader2,      cls: "bg-blue-50 text-blue-700",   label: "Processing" },
    failed:     { icon: AlertCircle,  cls: "bg-red-50 text-red-700",     label: "Failed" },
    pending:    { icon: Clock,        cls: "bg-gray-100 text-gray-500",  label: "Pending" },
  };
  const m = map[status] || map.pending;
  return (
    <span className={cn("badge gap-1", m.cls)}>
      <m.icon className={cn("w-3 h-3", status === "processing" && "animate-spin")} />
      {m.label}
    </span>
  );
}
