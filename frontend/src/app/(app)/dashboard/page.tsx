"use client";
import { useQuery, useMutation } from "@tanstack/react-query";
import Link from "next/link";
import toast from "react-hot-toast";
import {
  SendHorizonal, ArrowRight, FileText, Link2, Send,
  BrainCircuit, Mail, Sparkles, AlertTriangle, Loader2, ExternalLink,
} from "lucide-react";
import { appApi, resumeApi, profileApi, emailApi } from "@/lib/api";
import { Card, Skeleton } from "@/components/ui";
import { STATUS_LABEL, STATUS_COLOR, fitColor, ago, cn, gmailExpiry } from "@/lib/utils";
import { useAuth } from "@/hooks/useAuth";

export default function DashboardPage() {
  const { user } = useAuth();

  const { data: apps, isLoading: appsLoading } = useQuery({
    queryKey: ["apps", "recent"],
    queryFn: () => appApi.list().then(r => r.data),
  });
  const { data: resumes } = useQuery({
    queryKey: ["resumes"],
    queryFn: () => resumeApi.list().then(r => r.data),
  });
  const { data: profile } = useQuery({
    queryKey: ["profile"],
    queryFn: () => profileApi.get().then(r => r.data),
  });
  const { data: gmailOauthStatus } = useQuery({
    queryKey: ["gmail-oauth-status"],
    queryFn: () => emailApi.oauthStatus().then(r => r.data),
  });

  const items = apps?.items || [];
  const hasResume = (resumes?.items || []).some((r: any) => r.status === "ready");
  // Sending works out of the box once SendGrid is configured on the
  // server — nobody has to connect anything for mail to work, so this
  // only shows up as a setup step when there is truly no way to send.
  const hasEmailAccount = !!profile?.email_account_configured
    || !!profile?.gmail_connected
    || !!gmailOauthStatus?.default_sending_available;
  const kg = profile?.knowledge_graph;
  const hasMemory = !!(kg && (kg.identity || (kg.values || []).length > 0));
  const setupDone = hasResume && hasEmailAccount && hasMemory;

  const { warn: gmailWarn, daysLeft: gmailDaysLeft } = gmailExpiry(profile?.gmail_connected_at);
  const reconnectGmailMut = useMutation({
    mutationFn: () => emailApi.oauthStart(),
    onSuccess: ({ data }) => { window.location.href = data.url; },
    onError: (err: any) => toast.error(err.response?.data?.detail || "Could not start the Gmail connection"),
  });

  return (
    <div className="p-8 max-w-5xl">
      <div className="page-header">
        <h1 className="page-title">
          {greeting()}, {user?.full_name?.split(" ")[0] || "there"}
        </h1>
        <p className="page-desc">Two things happen here: forms get filled, applications get mailed</p>
      </div>

      {/* Gmail in this app runs on a Google OAuth app still in Testing
          mode, which expires every connection after 7 days no matter
          what — this is the heads up that beats a send just failing */}
      {profile?.gmail_connected && gmailWarn && (
        <Card className="mb-6 bg-amber-50 border-amber-100">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0" />
            <div className="flex-1">
              <p className="font-medium text-gray-900 text-sm">
                Your Gmail connection expires in about {Math.max(1, Math.round((gmailDaysLeft || 0) * 24))} hours
              </p>
              <p className="text-amber-700 text-sm">Reconnect now so sending an application never breaks mid use.</p>
            </div>
            <button
              onClick={() => reconnectGmailMut.mutate()}
              disabled={reconnectGmailMut.isPending}
              className="btn-primary text-sm shrink-0"
            >
              {reconnectGmailMut.isPending
                ? <Loader2 className="w-4 h-4 animate-spin" />
                : <>Reconnect <ExternalLink className="w-3.5 h-3.5" /></>}
            </button>
          </div>
        </Card>
      )}

      {/* Setup checklist — the AI writes from the resume and the memory,
          and the mailer sends from the connected account, so these three
          are what make everything else on this page actually work well */}
      {!setupDone && (
        <Card className="mb-6 bg-indigo-50 border-indigo-100">
          <h3 className="font-semibold text-gray-900 mb-1">Set yourself up first</h3>
          <p className="text-sm text-indigo-700 mb-3">
            Everything written for you is grounded in these three, the better they are, the better
            every answer and email gets
          </p>
          <div className="space-y-2">
            <ChecklistItem done={hasResume} href="/resume" text="Upload your resume" />
            <ChecklistItem done={hasMemory} href="/settings?tab=knowledge" text="Build your memory, answer a few questions about yourself" />
            <ChecklistItem done={hasEmailAccount} href="/settings?tab=email" text="Connect your email account for sending" />
          </div>
        </Card>
      )}

      {/* The two main actions */}
      <div className="grid md:grid-cols-2 gap-4 mb-6">
        <Link href="/apply?tab=googleform" className="card p-6 hover:border-indigo-300 hover:shadow-md transition-all group">
          <div className="w-12 h-12 bg-indigo-600 rounded-xl flex items-center justify-center mb-4">
            <Link2 className="w-6 h-6 text-white" />
          </div>
          <p className="font-semibold text-gray-900 text-lg mb-1">Fill a Form</p>
          <p className="text-gray-500 text-sm leading-relaxed mb-3">
            Paste a Google Forms or Microsoft Forms link. Every question gets answered from your
            resume and your memory, and you get a link that opens the form with the answers
            already typed in, ready for you to review and submit.
          </p>
          <span className="text-indigo-600 text-sm font-medium flex items-center gap-1 group-hover:gap-2 transition-all">
            Start filling <ArrowRight className="w-4 h-4" />
          </span>
        </Link>

        <Link href="/apply?tab=email" className="card p-6 hover:border-indigo-300 hover:shadow-md transition-all group">
          <div className="w-12 h-12 bg-emerald-600 rounded-xl flex items-center justify-center mb-4">
            <Send className="w-6 h-6 text-white" />
          </div>
          <p className="font-semibold text-gray-900 text-lg mb-1">Mail an Application</p>
          <p className="text-gray-500 text-sm leading-relaxed mb-3">
            Paste a job description and a recipient address. A tailored application email is
            written for you to review and edit, then it goes out from your own address with your
            resume attached as a document.
          </p>
          <span className="text-emerald-600 text-sm font-medium flex items-center gap-1 group-hover:gap-2 transition-all">
            Write the email <ArrowRight className="w-4 h-4" />
          </span>
        </Link>
      </div>

      {/* Supporting pieces */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <SmallAction href="/resume" icon={FileText} label="My Resume"
          hint={hasResume ? "Uploaded" : "Not uploaded yet"} ok={hasResume} />
        <SmallAction href="/settings?tab=knowledge" icon={BrainCircuit} label="My Memory"
          hint={hasMemory ? "Built, keep growing it" : "Not built yet"} ok={hasMemory} />
        <SmallAction href="/settings?tab=email" icon={Mail} label="Email Account"
          hint={
            profile?.gmail_connected ? `Sends as ${profile.gmail_address}` :
            profile?.email_account_configured ? `Sends as ${profile.sender_email}` :
            gmailOauthStatus?.default_sending_available ? "Sending works, Gmail optional" :
            "Not connected"
          } ok={hasEmailAccount} />
        <SmallAction href="/apply?tab=generate" icon={Sparkles} label="Full Kit"
          hint="Cover letter, email, resume" ok />
      </div>

      {/* Recent applications — records, not the main event */}
      {items.length > 0 && (
        <Card className="p-0 overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <h2 className="section-title">Recent Applications</h2>
            <Link href="/applications" className="text-indigo-600 text-sm font-medium flex items-center gap-1 hover:text-indigo-700">
              View all <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
          {appsLoading ? (
            <div className="p-5 space-y-3">
              {[1, 2, 3].map(i => <Skeleton key={i} className="h-14" />)}
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {items.slice(0, 5).map((a: any) => (
                <Link key={a.id} href={`/applications/${a.id}`} className="flex items-center gap-4 px-5 py-3.5 hover:bg-gray-50 transition-colors">
                  <div className="w-9 h-9 rounded-lg bg-gray-100 flex items-center justify-center text-gray-600 font-semibold text-sm shrink-0">
                    {(a.job?.company || "?")[0].toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900 text-sm truncate">{a.job?.title || "Untitled role"}</p>
                    <p className="text-gray-500 text-xs truncate">{a.job?.company} · {ago(a.created_at)}</p>
                  </div>
                  {a.fit_score != null && (
                    <span className={cn("text-sm font-semibold", fitColor(a.fit_score))}>{a.fit_score.toFixed(0)}%</span>
                  )}
                  <span className={cn("badge", STATUS_COLOR[a.status])}>{STATUS_LABEL[a.status]}</span>
                </Link>
              ))}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

function SmallAction({ href, icon: Icon, label, hint, ok }: {
  href: string; icon: any; label: string; hint: string; ok?: boolean;
}) {
  return (
    <Link href={href} className="card p-4 hover:border-gray-300 hover:shadow-sm transition-all">
      <Icon className={cn("w-5 h-5 mb-2", ok ? "text-indigo-600" : "text-amber-500")} />
      <p className="font-medium text-gray-900 text-sm">{label}</p>
      <p className={cn("text-xs mt-0.5 truncate", ok ? "text-gray-400" : "text-amber-600 font-medium")}>{hint}</p>
    </Link>
  );
}

function ChecklistItem({ done, href, text }: { done: boolean; href: string; text: string }) {
  return (
    <Link href={href} className="flex items-center gap-3 text-sm group">
      <div className={cn(
        "w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold shrink-0",
        done ? "bg-emerald-500 text-white" : "bg-white border-2 border-gray-300 text-transparent"
      )}>
        ✓
      </div>
      <span className={cn(done ? "text-gray-400 line-through" : "text-gray-700 group-hover:text-indigo-600 font-medium")}>
        {text}
      </span>
    </Link>
  );
}

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}
