"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { User, Briefcase, Sliders, Loader2 } from "lucide-react";
import { profileApi, authApi } from "@/lib/api";
import { Card } from "@/components/ui";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/useAuth";

const TABS = [
  { id: "account",     label: "Account",     icon: User },
  { id: "preferences", label: "Job Preferences", icon: Briefcase },
  { id: "ai",          label: "AI Settings", icon: Sliders },
];

const EXPERIENCE = ["intern", "entry", "mid", "senior", "staff", "lead"];
const TONES = ["professional", "formal", "conversational", "technical", "enthusiastic"];
const WORK_TYPES = ["remote", "hybrid", "onsite"];

export default function SettingsPage() {
  const [tab, setTab] = useState("account");
  const qc = useQueryClient();
  const { user, logout } = useAuth();

  const { data: profile, isLoading } = useQuery({
    queryKey: ["profile"],
    queryFn: () => profileApi.get().then(r => r.data),
  });

  const { register, handleSubmit, watch, setValue } = useForm({ values: profile || {} });

  const saveProfileMut = useMutation({
    mutationFn: (d: any) => profileApi.update(d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["profile"] }); toast.success("Saved"); },
    onError: () => toast.error("Failed to save"),
  });

  const saveAccountMut = useMutation({
    mutationFn: (d: any) => authApi.updateMe(d),
    onSuccess: () => toast.success("Saved"),
    onError: () => toast.error("Failed to save"),
  });

  const [accountForm, setAccountForm] = useState({ full_name: user?.full_name || "" });

  if (isLoading) {
    return <div className="p-8"><Loader2 className="w-6 h-6 text-gray-300 animate-spin" /></div>;
  }

  const workTypes: string[] = watch("work_types") || [];
  const toggleWorkType = (wt: string) => {
    const next = workTypes.includes(wt) ? workTypes.filter(w => w !== wt) : [...workTypes, wt];
    setValue("work_types", next);
  };

  return (
    <div className="p-8 max-w-3xl">
      <div className="page-header">
        <h1 className="page-title">Settings</h1>
        <p className="page-desc">Manage your account and preferences</p>
      </div>

      <div className="flex gap-6">
        <nav className="w-44 shrink-0 space-y-1">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => setTab(id)} className={cn(
              "w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium text-left transition-colors",
              tab === id ? "bg-indigo-50 text-indigo-700" : "text-gray-600 hover:bg-gray-100"
            )}>
              <Icon className="w-4 h-4" />{label}
            </button>
          ))}
        </nav>

        <div className="flex-1 space-y-5">
          {tab === "account" && (
            <Card>
              <h2 className="font-semibold text-gray-900 mb-4">Account</h2>
              <div className="space-y-4">
                <div>
                  <label className="label">Full name</label>
                  <input
                    value={accountForm.full_name}
                    onChange={(e) => setAccountForm({ full_name: e.target.value })}
                    className="input"
                  />
                </div>
                <div>
                  <label className="label">Email</label>
                  <input value={user?.email || ""} disabled className="input bg-gray-50 text-gray-400" />
                </div>
                <button onClick={() => saveAccountMut.mutate(accountForm)} className="btn-primary">Save changes</button>
              </div>

              <div className="border-t border-gray-100 mt-6 pt-5">
                <p className="text-sm text-gray-500 mb-3">Sign out of your account</p>
                <button onClick={logout} className="btn-secondary text-red-600 border-red-200 hover:bg-red-50">
                  Sign out
                </button>
              </div>
            </Card>
          )}

          {tab === "preferences" && (
            <form onSubmit={handleSubmit((d) => saveProfileMut.mutate(d))}>
              <Card className="space-y-4">
                <h2 className="font-semibold text-gray-900 mb-1">Job Preferences</h2>

                <div>
                  <label className="label">Location</label>
                  <input {...register("location")} placeholder="San Francisco, CA" className="input" />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="label">LinkedIn URL</label>
                    <input {...register("linkedin_url")} placeholder="https://linkedin.com/in/..." className="input" />
                  </div>
                  <div>
                    <label className="label">GitHub URL</label>
                    <input {...register("github_url")} placeholder="https://github.com/..." className="input" />
                  </div>
                </div>

                <div>
                  <label className="label">Experience level</label>
                  <select {...register("experience_level")} className="input capitalize">
                    <option value="">Select...</option>
                    {EXPERIENCE.map(e => <option key={e} value={e}>{e}</option>)}
                  </select>
                </div>

                <div>
                  <label className="label">Work type preference</label>
                  <div className="flex gap-2">
                    {WORK_TYPES.map(wt => (
                      <button key={wt} type="button" onClick={() => toggleWorkType(wt)} className={cn(
                        "px-3 py-1.5 rounded-lg text-sm font-medium capitalize transition-colors",
                        workTypes.includes(wt) ? "bg-indigo-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                      )}>
                        {wt}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="label">Min salary (USD)</label>
                    <input {...register("salary_min")} type="number" placeholder="100000" className="input" />
                  </div>
                  <div>
                    <label className="label">Max salary (USD)</label>
                    <input {...register("salary_max")} type="number" placeholder="160000" className="input" />
                  </div>
                </div>

                <button type="submit" disabled={saveProfileMut.isPending} className="btn-primary">
                  {saveProfileMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : "Save preferences"}
                </button>
              </Card>
            </form>
          )}

          {tab === "ai" && (
            <form onSubmit={handleSubmit((d) => saveProfileMut.mutate(d))}>
              <Card className="space-y-4">
                <h2 className="font-semibold text-gray-900 mb-1">AI Writing Style</h2>
                <p className="text-sm text-gray-500 mb-3">Choose the tone for generated cover letters and emails</p>
                <div className="grid grid-cols-1 gap-2">
                  {TONES.map(t => (
                    <label key={t} className={cn(
                      "flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors capitalize",
                      watch("tone_preference") === t ? "border-indigo-300 bg-indigo-50" : "border-gray-200 hover:bg-gray-50"
                    )}>
                      <input type="radio" value={t} {...register("tone_preference")} className="text-indigo-600" />
                      <span className="text-sm font-medium text-gray-800">{t}</span>
                    </label>
                  ))}
                </div>
                <button type="submit" disabled={saveProfileMut.isPending} className="btn-primary">
                  {saveProfileMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : "Save"}
                </button>
              </Card>

              <Card className="mt-5 bg-gray-50">
                <h3 className="font-semibold text-gray-900 mb-2 text-sm">About the AI</h3>
                <p className="text-sm text-gray-500 leading-relaxed">
                  ApplyPilot uses <strong>Groq's free API</strong> (Llama 3.3 70B) to generate cover letters,
                  emails, and form answers. Your data is sent to Groq for processing only —
                  no other third parties. Get your free key at{" "}
                  <a href="https://console.groq.com" target="_blank" rel="noreferrer" className="text-indigo-600 underline">
                    console.groq.com
                  </a>.
                </p>
              </Card>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
