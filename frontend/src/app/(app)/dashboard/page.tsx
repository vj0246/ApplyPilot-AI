"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
  SendHorizonal, Target, Award, TrendingUp, Plus, ArrowRight,
  FileText,
} from "lucide-react";
import { appApi, resumeApi, jobApi } from "@/lib/api";
import { Card, EmptyState, Skeleton } from "@/components/ui";
import { STATUS_LABEL, STATUS_COLOR, fitColor, ago, cn } from "@/lib/utils";
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
  const { data: jobs } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => jobApi.list().then(r => r.data),
  });

  const items = apps?.items || [];
  const stats = apps?.stats || {};
  const hasResume = (resumes?.items || []).some((r: any) => r.status === "ready");
  const hasJob = (jobs?.items || []).some((j: any) => j.status === "ready");

  const submitted = stats.submitted || 0;
  const interviewing = stats.interviewing || 0;
  const offered = stats.offered || 0;
  const avgFit = items.length
    ? items.filter((a: any) => a.fit_score).reduce((s: number, a: any) => s + a.fit_score, 0) / Math.max(1, items.filter((a: any) => a.fit_score).length)
    : 0;

  return (
    <div className="p-8 max-w-5xl">
      <div className="page-header">
        <h1 className="page-title">
          {greeting()}, {user?.full_name?.split(" ")[0] || "there"}
        </h1>
        <p className="page-desc">Here's your application overview</p>
      </div>

      {/* Onboarding checklist */}
      {(!hasResume || !hasJob) && (
        <Card className="mb-6 bg-indigo-50 border-indigo-100">
          <h3 className="font-semibold text-gray-900 mb-3">Get started</h3>
          <div className="space-y-2">
            <ChecklistItem
              done={hasResume}
              href="/resume"
              text="Upload your resume"
            />
            <ChecklistItem
              done={hasJob}
              href="/jobs"
              text="Add a job posting"
            />
            <ChecklistItem
              done={items.length > 0}
              href="/apply"
              text="Generate your first application"
            />
          </div>
        </Card>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard icon={SendHorizonal} label="Submitted" value={submitted} color="text-indigo-600" bg="bg-indigo-50" />
        <StatCard icon={Target} label="Interviewing" value={interviewing} color="text-cyan-600" bg="bg-cyan-50" />
        <StatCard icon={Award} label="Offers" value={offered} color="text-emerald-600" bg="bg-emerald-50" />
        <StatCard icon={TrendingUp} label="Avg Fit Score" value={avgFit ? avgFit.toFixed(0) : "—"} color="text-yellow-600" bg="bg-yellow-50" />
      </div>

      {/* Quick actions */}
      <div className="grid md:grid-cols-2 gap-4 mb-6">
        <Link href="/apply" className="card p-5 flex items-center gap-4 hover:border-indigo-300 hover:shadow-md transition-all group">
          <div className="w-11 h-11 bg-indigo-600 rounded-xl flex items-center justify-center shrink-0">
            <Plus className="w-5 h-5 text-white" />
          </div>
          <div>
            <p className="font-semibold text-gray-900">Generate application</p>
            <p className="text-gray-500 text-sm">AI-powered cover letter & email</p>
          </div>
          <ArrowRight className="w-4 h-4 text-gray-300 ml-auto group-hover:text-indigo-500 transition-colors" />
        </Link>
        <Link href="/resume" className="card p-5 flex items-center gap-4 hover:border-gray-300 hover:shadow-md transition-all group">
          <div className="w-11 h-11 bg-gray-100 rounded-xl flex items-center justify-center shrink-0">
            <FileText className="w-5 h-5 text-gray-600" />
          </div>
          <div>
            <p className="font-semibold text-gray-900">Manage resume</p>
            <p className="text-gray-500 text-sm">{(resumes?.items || []).length} version(s) uploaded</p>
          </div>
          <ArrowRight className="w-4 h-4 text-gray-300 ml-auto group-hover:text-gray-500 transition-colors" />
        </Link>
      </div>

      {/* Recent applications */}
      <Card className="p-0 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h2 className="section-title">Recent Applications</h2>
          <Link href="/applications" className="text-indigo-600 text-sm font-medium flex items-center gap-1 hover:text-indigo-700">
            View all <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
        {appsLoading ? (
          <div className="p-5 space-y-3">
            {[1,2,3].map(i => <Skeleton key={i} className="h-14" />)}
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            icon={<SendHorizonal className="w-10 h-10" />}
            title="No applications yet"
            description="Upload a resume and add a job to get started"
            action={<Link href="/apply" className="btn-primary">Generate application</Link>}
          />
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
    </div>
  );
}

function StatCard({ icon: Icon, label, value, color, bg }: any) {
  return (
    <Card>
      <div className={cn("w-9 h-9 rounded-lg flex items-center justify-center mb-3", bg)}>
        <Icon className={cn("w-4.5 h-4.5", color)} />
      </div>
      <div className="text-2xl font-bold text-gray-900">{value}</div>
      <div className="text-gray-500 text-xs mt-0.5">{label}</div>
    </Card>
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
