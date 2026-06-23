"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import toast from "react-hot-toast";
import {
  ChevronLeft, Loader2, Copy, Edit3, Save, X, Mail, FileText,
  Sparkles, MessageSquare, Target, TrendingUp, AlertTriangle,
  ExternalLink, CheckCircle2,
} from "lucide-react";
import { appApi } from "@/lib/api";
import { Card, ScoreCircle, ProgressBar, Textarea, Alert } from "@/components/ui";
import { STATUS_LABEL, STATUS_COLOR, fmtSalary, cn } from "@/lib/utils";

const TABS = [
  { id: "overview",     label: "Overview",     icon: Target },
  { id: "cover_letter", label: "Cover Letter", icon: FileText },
  { id: "email",        label: "Email",        icon: Mail },
  { id: "resume",       label: "Adapted Resume", icon: Sparkles },
];

const NEXT_STATUSES: Record<string, string[]> = {
  ready:        ["approved"],
  approved:     ["submitted"],
  submitted:    ["screening", "interviewing", "rejected"],
  screening:    ["interviewing", "rejected"],
  interviewing: ["offered", "rejected"],
};

export default function ApplicationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const [tab, setTab] = useState("overview");
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  const { data: app, isLoading } = useQuery({
    queryKey: ["app", id],
    queryFn: () => appApi.get(id).then(r => r.data),
    refetchInterval: (q) => q.state.data?.status === "generating" ? 2000 : false,
  });

  const updateMut = useMutation({
    mutationFn: (body: Record<string, unknown>) => appApi.update(id, body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["app", id] }); qc.invalidateQueries({ queryKey: ["apps"] }); },
    onError: (err: any) => toast.error(err.response?.data?.detail || "Update failed"),
  });

  if (isLoading) {
    return <div className="p-8 flex items-center justify-center h-64"><Loader2 className="w-7 h-7 text-gray-300 animate-spin" /></div>;
  }
  if (!app) return <div className="p-8 text-gray-400">Application not found</div>;

  const isGenerating = app.status === "generating";
  const isFailed = app.status === "failed";

  const startEdit = (field: string, value: string) => { setEditing(field); setDraft(value || ""); };
  const saveEdit = (field: string) => {
    updateMut.mutate({ [field]: draft });
    setEditing(null);
    toast.success("Saved");
  };
  const copy = (text: string) => { navigator.clipboard.writeText(text); toast.success("Copied to clipboard!"); };

  return (
    <div className="p-8 max-w-4xl">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => router.back()} className="p-2 text-gray-400 hover:text-gray-700 transition-colors">
          <ChevronLeft className="w-5 h-5" />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-xl font-bold text-gray-900">{app.job?.title || "Application"}</h1>
            <span className={cn("badge", STATUS_COLOR[app.status])}>{STATUS_LABEL[app.status]}</span>
          </div>
          <p className="text-gray-500 text-sm mt-0.5">
            {app.job?.company}
            {app.job?.location && ` · ${app.job.location}`}
            {fmtSalary(app.job?.salary_min, app.job?.salary_max, app.job?.salary_currency) && ` · ${fmtSalary(app.job?.salary_min, app.job?.salary_max, app.job?.salary_currency)}`}
          </p>
        </div>
        {app.fit_score != null && <ScoreCircle score={app.fit_score} size="md" />}
      </div>

      {isGenerating && (
        <Card className="mb-6 text-center py-10">
          <Loader2 className="w-8 h-8 text-indigo-500 animate-spin mx-auto mb-3" />
          <p className="font-semibold text-gray-900">AI is generating your application…</p>
          <p className="text-gray-500 text-sm mt-1">Cover letter, email, fit score — about 15 seconds</p>
        </Card>
      )}

      {isFailed && (
        <Alert type="error">
          <strong>Generation failed:</strong> {app.error_msg || "Unknown error. Check your GROQ_API_KEY in .env."}
        </Alert>
      )}

      {!isGenerating && !isFailed && (
        <>
          {/* Action bar */}
          <div className="flex items-center gap-2 mb-6 flex-wrap">
            {NEXT_STATUSES[app.status]?.map(s => (
              <button key={s} onClick={() => updateMut.mutate({ status: s })} className="btn-secondary text-sm">
                {s === "approved" && <CheckCircle2 className="w-3.5 h-3.5" />}
                Mark as {STATUS_LABEL[s]}
              </button>
            ))}
            {app.job?.url && (
              <a href={app.job.url} target="_blank" rel="noopener noreferrer" className="btn-secondary text-sm">
                <ExternalLink className="w-3.5 h-3.5" /> Open job posting
              </a>
            )}
          </div>

          {/* Tabs */}
          <div className="flex gap-1 border-b border-gray-200 mb-5">
            {TABS.map(({ id: tid, label, icon: Icon }) => (
              <button key={tid} onClick={() => setTab(tid)} className={cn(
                "flex items-center gap-1.5 px-3.5 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors",
                tab === tid ? "border-indigo-600 text-indigo-600" : "border-transparent text-gray-500 hover:text-gray-800"
              )}>
                <Icon className="w-3.5 h-3.5" />{label}
              </button>
            ))}
          </div>

          {/* OVERVIEW */}
          {tab === "overview" && (
            <div className="space-y-5">
              {app.fit_breakdown && (
                <Card>
                  <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-indigo-500" /> Fit Breakdown
                  </h3>
                  <div className="space-y-3">
                    <FitRow label="Skills match" value={app.fit_breakdown.skills_match} />
                    <FitRow label="Experience match" value={app.fit_breakdown.experience_match} />
                  </div>
                  {app.fit_breakdown.matched_skills?.length > 0 && (
                    <div className="mt-4">
                      <p className="text-xs font-medium text-gray-500 mb-1.5">Matched skills</p>
                      <div className="flex flex-wrap gap-1.5">
                        {app.fit_breakdown.matched_skills.map((s: string) => (
                          <span key={s} className="badge bg-emerald-50 text-emerald-700">{s}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </Card>
              )}

              {app.skill_gaps?.length > 0 && (
                <Card>
                  <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-yellow-500" /> Skill Gaps
                  </h3>
                  <div className="space-y-2">
                    {app.skill_gaps.map((g: any) => (
                      <div key={g.skill} className="flex items-center gap-2 text-sm">
                        <span className={cn("badge", g.type === "required" ? "bg-red-50 text-red-600" : "bg-yellow-50 text-yellow-700")}>
                          {g.type === "required" ? "Required" : "Nice to have"}
                        </span>
                        <span className="text-gray-700 font-medium">{g.skill}</span>
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              {app.strategy && (
                <Card>
                  <h3 className="font-semibold text-gray-900 mb-2">Strategy</h3>
                  <p className="text-sm text-gray-600 leading-relaxed">{app.strategy}</p>
                </Card>
              )}

              {app.answers?.length > 0 && (
                <Card>
                  <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                    <MessageSquare className="w-4 h-4 text-purple-500" /> Suggested Answers
                  </h3>
                  <div className="space-y-3">
                    {app.answers.map((a: any, i: number) => (
                      <div key={i} className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                        <p className="text-xs font-semibold text-indigo-600 mb-1">{a.question}</p>
                        <p className="text-sm text-gray-700">{a.answer}</p>
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              <Card>
                <h3 className="font-semibold text-gray-900 mb-2">Your Notes</h3>
                <Textarea
                  defaultValue={app.user_notes || ""}
                  rows={3}
                  placeholder="Add private notes about this application..."
                  onBlur={(e) => updateMut.mutate({ user_notes: e.target.value })}
                />
              </Card>
            </div>
          )}

          {/* COVER LETTER */}
          {tab === "cover_letter" && (
            <EditableCard
              title="Cover Letter"
              content={app.cover_letter || ""}
              editing={editing === "cover_letter"}
              draft={draft}
              onEdit={() => startEdit("cover_letter", app.cover_letter)}
              onChange={setDraft}
              onSave={() => saveEdit("cover_letter")}
              onCancel={() => setEditing(null)}
              onCopy={() => copy(app.cover_letter || "")}
            />
          )}

          {/* EMAIL */}
          {tab === "email" && (
            <div className="space-y-4">
              <Card>
                <label className="label">Subject</label>
                {editing === "email_subject" ? (
                  <div className="flex gap-2">
                    <input value={draft} onChange={e => setDraft(e.target.value)} className="input" />
                    <button onClick={() => saveEdit("email_subject")} className="btn-primary px-3"><Save className="w-4 h-4" /></button>
                    <button onClick={() => setEditing(null)} className="btn-secondary px-3"><X className="w-4 h-4" /></button>
                  </div>
                ) : (
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm text-gray-800 font-medium">{app.email_subject}</p>
                    <div className="flex gap-1 shrink-0">
                      <button onClick={() => startEdit("email_subject", app.email_subject)} className="p-1.5 text-gray-400 hover:text-gray-700"><Edit3 className="w-3.5 h-3.5" /></button>
                      <button onClick={() => copy(app.email_subject || "")} className="p-1.5 text-gray-400 hover:text-indigo-600"><Copy className="w-3.5 h-3.5" /></button>
                    </div>
                  </div>
                )}
              </Card>
              <EditableCard
                title="Body"
                content={app.email_body || ""}
                editing={editing === "email_body"}
                draft={draft}
                onEdit={() => startEdit("email_body", app.email_body)}
                onChange={setDraft}
                onSave={() => saveEdit("email_body")}
                onCancel={() => setEditing(null)}
                onCopy={() => copy(app.email_body || "")}
              />
            </div>
          )}

          {/* RESUME */}
          {tab === "resume" && (
            <EditableCard
              title="Adapted Resume"
              content={app.resume_adapted || ""}
              editing={editing === "resume_adapted"}
              draft={draft}
              onEdit={() => startEdit("resume_adapted", app.resume_adapted)}
              onChange={setDraft}
              onSave={() => saveEdit("resume_adapted")}
              onCancel={() => setEditing(null)}
              onCopy={() => copy(app.resume_adapted || "")}
              mono
            />
          )}
        </>
      )}
    </div>
  );
}

function FitRow({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-gray-600">{label}</span>
        <span className="font-medium text-gray-900">{value?.toFixed(0)}%</span>
      </div>
      <ProgressBar value={value} />
    </div>
  );
}

function EditableCard({
  title, content, editing, draft, onEdit, onChange, onSave, onCancel, onCopy, mono,
}: {
  title: string; content: string; editing: boolean; draft: string;
  onEdit: () => void; onChange: (v: string) => void; onSave: () => void;
  onCancel: () => void; onCopy: () => void; mono?: boolean;
}) {
  return (
    <Card className="p-0 overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
        <h3 className="font-semibold text-gray-900 text-sm">{title}</h3>
        {!editing ? (
          <div className="flex gap-1">
            <button onClick={onEdit} className="btn-ghost text-xs py-1"><Edit3 className="w-3.5 h-3.5" /> Edit</button>
            <button onClick={onCopy} className="btn-ghost text-xs py-1"><Copy className="w-3.5 h-3.5" /> Copy</button>
          </div>
        ) : (
          <div className="flex gap-1">
            <button onClick={onSave} className="btn-ghost text-xs py-1 text-green-600"><Save className="w-3.5 h-3.5" /> Save</button>
            <button onClick={onCancel} className="btn-ghost text-xs py-1"><X className="w-3.5 h-3.5" /> Cancel</button>
          </div>
        )}
      </div>
      <div className="p-5">
        {editing ? (
          <Textarea value={draft} onChange={(e) => onChange(e.target.value)} rows={16} className={mono ? "font-mono text-xs" : ""} />
        ) : content ? (
          <p className={cn("text-sm text-gray-700 whitespace-pre-wrap leading-relaxed", mono && "font-mono text-xs")}>{content}</p>
        ) : (
          <p className="text-sm text-gray-400 italic">Not generated</p>
        )}
      </div>
    </Card>
  );
}
