"use client";
import { Suspense, useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { User, Briefcase, Sliders, Loader2, BrainCircuit, Mail, CheckCircle2, Plus, Trash2, ExternalLink } from "lucide-react";
import { profileApi, authApi, emailApi } from "@/lib/api";
import { Card, Textarea } from "@/components/ui";
import { cn, gmailExpiry } from "@/lib/utils";
import { useAuth } from "@/hooks/useAuth";

const TABS = [
  { id: "account",     label: "Account",     icon: User },
  { id: "preferences", label: "Job Preferences", icon: Briefcase },
  { id: "ai",          label: "AI Settings", icon: Sliders },
  { id: "knowledge",   label: "My Memory", icon: BrainCircuit },
  { id: "email",       label: "Email Account", icon: Mail },
];

const EXPERIENCE = ["intern", "entry", "mid", "senior", "staff", "lead"];
const TONES = ["professional", "formal", "conversational", "technical", "enthusiastic"];
const WORK_TYPES = ["remote", "hybrid", "onsite"];

export default function SettingsPage() {
  // useSearchParams needs a Suspense boundary to prerender, so the page
  // is a thin shell around the real component.
  return (
    <Suspense fallback={null}>
      <SettingsPageInner />
    </Suspense>
  );
}

function SettingsPageInner() {
  const searchParams = useSearchParams();
  const urlTab = searchParams.get("tab");
  const [tab, setTab] = useState(
    TABS.some(t => t.id === urlTab) ? (urlTab as string) : "account"
  );
  // Sidebar links can change the tab query parameter while this page is
  // already mounted, and the state initializer above only runs once.
  useEffect(() => {
    if (TABS.some(t => t.id === urlTab)) setTab(urlTab as string);
  }, [urlTab]);

  const qc = useQueryClient();

  // The Gmail OAuth callback lands the browser back here with a plain
  // ?gmail= flag on the URL, since that redirect comes straight from
  // Google with no way to run frontend code in between.
  const gmailResult = searchParams.get("gmail");
  useEffect(() => {
    if (!gmailResult) return;
    const messages: Record<string, string> = {
      connected: "Gmail connected, application emails now send from that address",
      denied: "Gmail connection was cancelled",
      noconsent: "Google did not return a fresh connection. Revoke ApplyPilot's access at myaccount.google.com/permissions, then try connecting again",
      error: "Could not connect Gmail, try again",
    };
    if (messages[gmailResult]) {
      if (gmailResult === "connected") toast.success(messages[gmailResult]);
      else toast.error(messages[gmailResult]);
    }
    qc.invalidateQueries({ queryKey: ["profile"] });
    window.history.replaceState(null, "", "/settings?tab=email");
  }, [gmailResult, qc]);

  const { data: gmailOauthStatus } = useQuery({
    queryKey: ["gmail-oauth-status"],
    queryFn: () => emailApi.oauthStatus().then(r => r.data),
  });

  const connectGmailMut = useMutation({
    mutationFn: () => emailApi.oauthStart(),
    onSuccess: ({ data }) => { window.location.href = data.url; },
    onError: (err: any) => toast.error(err.response?.data?.detail || "Could not start the Gmail connection"),
  });

  const disconnectGmailMut = useMutation({
    mutationFn: () => emailApi.oauthDisconnect(),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["profile"] }); toast.success("Gmail disconnected"); },
  });
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

  // ── Knowledge graph ──────────────────────────────────────────────
  const { data: kgQuestions } = useQuery({
    queryKey: ["knowledge-graph-questions"],
    queryFn: () => profileApi.knowledgeGraphQuestions().then(r => r.data.questions as string[]),
  });
  const [kgAnswers, setKgAnswers] = useState<Record<string, string>>({});

  // On top of the fixed interview, anyone can teach their memory
  // anything by writing their own question and answering it — "What
  // languages do I speak", "What do I refuse to compromise on". The
  // backend treats these exactly like the fixed questions and folds the
  // answers into the same graph.
  const [customPairs, setCustomPairs] = useState<{ question: string; answer: string }[]>([]);

  const buildGraphMut = useMutation({
    mutationFn: () =>
      profileApi.buildKnowledgeGraph([
        ...Object.entries(kgAnswers)
          .filter(([, answer]) => answer.trim())
          .map(([question, answer]) => ({ question, answer })),
        ...customPairs.filter(p => p.question.trim() && p.answer.trim()),
      ]),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["profile"] });
      setCustomPairs([]);
      toast.success("Your memory grew from these answers");
    },
    onError: (err: any) => toast.error(err.response?.data?.detail || "Could not update your memory"),
  });

  const hasAnyAnswer =
    Object.values(kgAnswers).some(v => v.trim()) ||
    customPairs.some(p => p.question.trim() && p.answer.trim());

  const knowledgeGraph = profile?.knowledge_graph;
  const hasGraph = knowledgeGraph && (knowledgeGraph.identity || (knowledgeGraph.values || []).length > 0);

  // ── Direct memory editing ────────────────────────────────────────
  // The interview above only ever adds to the graph. This editor is the
  // other half: open the stored memory as plain text, change or delete
  // anything, and save exactly what is written, replacing what was there.
  const [editingMemory, setEditingMemory] = useState(false);
  const [memoryDraft, setMemoryDraft] = useState<Record<string, string>>({});

  const LIST_FIELDS = [
    "values", "strengths", "motivations", "work_style", "goals",
    "knowledge_areas", "interests", "priorities",
  ] as const;

  const openMemoryEditor = () => {
    const g: any = knowledgeGraph || {};
    const draft: Record<string, string> = {
      identity: g.identity || "",
      communication_style: g.communication_style || "",
      achievements: (g.achievements || [])
        .map((a: any) => `${a.title || ""} :: ${a.summary || ""}`)
        .join("\n"),
    };
    for (const f of LIST_FIELDS) draft[f] = (g[f] || []).join("\n");
    setMemoryDraft(draft);
    setEditingMemory(true);
  };

  const saveMemoryMut = useMutation({
    mutationFn: () => {
      const lines = (s: string) => s.split("\n").map(l => l.trim()).filter(Boolean);
      const graph: Record<string, unknown> = {
        identity: (memoryDraft.identity || "").trim(),
        communication_style: (memoryDraft.communication_style || "").trim(),
        achievements: lines(memoryDraft.achievements || "").map(l => {
          const [title, ...rest] = l.split("::");
          return { title: title.trim(), summary: rest.join("::").trim() };
        }),
      };
      for (const f of LIST_FIELDS) graph[f] = lines(memoryDraft[f] || "");
      return profileApi.editKnowledgeGraph(graph);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["profile"] });
      setEditingMemory(false);
      toast.success("Memory updated");
    },
    onError: (err: any) => toast.error(err.response?.data?.detail || "Could not save your memory"),
  });

  // ── Email account ────────────────────────────────────────────────
  const [emailForm, setEmailForm] = useState({
    sender_email: "", smtp_host: "smtp.gmail.com", smtp_port: 587,
    smtp_username: "", smtp_password: "",
  });

  const saveEmailMut = useMutation({
    mutationFn: () => profileApi.setEmailCredentials(emailForm),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["profile"] });
      toast.success("Email account connected");
      setEmailForm((f) => ({ ...f, smtp_password: "" }));
    },
    onError: (err: any) => toast.error(err.response?.data?.detail || "Could not save email account"),
  });

  const clearEmailMut = useMutation({
    mutationFn: () => profileApi.clearEmailCredentials(),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["profile"] }); toast.success("Email account disconnected"); },
  });

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
                    <label className="label">Min salary (Indian Rupees per year)</label>
                    <input {...register("salary_min")} type="number" placeholder="800000" className="input" />
                  </div>
                  <div>
                    <label className="label">Max salary (Indian Rupees per year)</label>
                    <input {...register("salary_max")} type="number" placeholder="2000000" className="input" />
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
                <div className="border-t border-gray-100 pt-4">
                  <label className="label">Custom writing instructions</label>
                  <p className="text-sm text-gray-500 mb-2">
                    Written in your own words, applied to every email, cover letter, and form answer
                    this tool writes for you. For example: always mention that I am open to
                    relocation, keep every email under one hundred words, sign off with Warm regards.
                  </p>
                  <textarea
                    {...register("custom_instructions")}
                    rows={5}
                    placeholder="Type any standing instruction about your tone or format here"
                    className="input resize-none"
                  />
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

          {tab === "knowledge" && (
            <div className="space-y-5">
              <Card className="bg-indigo-50 border-indigo-100">
                <div className="flex gap-3">
                  <BrainCircuit className="w-5 h-5 text-indigo-600 shrink-0 mt-0.5" />
                  <div className="text-sm text-indigo-900">
                    <p className="font-medium mb-0.5">A knowledge graph of you, not just your resume</p>
                    <p className="text-indigo-700">
                      Answer these in your own words. The answers are turned into a structured
                      profile of your values, strengths, and motivations, and every form answer
                      and email this tool writes is grounded in it, not just in your resume text.
                    </p>
                  </div>
                </div>
              </Card>

              {hasGraph && (
                <Card className="space-y-3">
                  <h2 className="font-semibold text-gray-900 flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-500" /> Current knowledge graph
                  </h2>
                  {knowledgeGraph?.identity && (
                    <p className="text-sm text-gray-700"><span className="font-medium">Identity: </span>{knowledgeGraph.identity}</p>
                  )}
                  {(knowledgeGraph?.values || []).length > 0 && (
                    <p className="text-sm text-gray-700"><span className="font-medium">Values: </span>{knowledgeGraph!.values!.join(", ")}</p>
                  )}
                  {(knowledgeGraph?.strengths || []).length > 0 && (
                    <p className="text-sm text-gray-700"><span className="font-medium">Strengths: </span>{knowledgeGraph!.strengths!.join(", ")}</p>
                  )}
                  {(knowledgeGraph?.motivations || []).length > 0 && (
                    <p className="text-sm text-gray-700"><span className="font-medium">Motivations: </span>{knowledgeGraph!.motivations!.join(", ")}</p>
                  )}
                  {(knowledgeGraph?.goals || []).length > 0 && (
                    <p className="text-sm text-gray-700"><span className="font-medium">Goals: </span>{knowledgeGraph!.goals!.join(", ")}</p>
                  )}
                  {((knowledgeGraph as any)?.knowledge_areas || []).length > 0 && (
                    <p className="text-sm text-gray-700"><span className="font-medium">Knows deeply: </span>{(knowledgeGraph as any).knowledge_areas.join(", ")}</p>
                  )}
                  {((knowledgeGraph as any)?.interests || []).length > 0 && (
                    <p className="text-sm text-gray-700"><span className="font-medium">Interests: </span>{(knowledgeGraph as any).interests.join(", ")}</p>
                  )}
                  {((knowledgeGraph as any)?.priorities || []).length > 0 && (
                    <p className="text-sm text-gray-700"><span className="font-medium">Priorities: </span>{(knowledgeGraph as any).priorities.join(", ")}</p>
                  )}
                  {!editingMemory && (
                    <button onClick={openMemoryEditor} className="btn-secondary text-sm">
                      Edit memory directly
                    </button>
                  )}
                </Card>
              )}

              {editingMemory && (
                <Card className="space-y-4">
                  <h2 className="font-semibold text-gray-900">Edit your memory</h2>
                  <p className="text-sm text-gray-500">
                    Whatever you save here replaces the stored memory exactly. Remove a line to
                    forget it, change a line to correct it. List fields take one item per line;
                    achievements take one per line as Title :: what happened.
                  </p>
                  <div>
                    <label className="label">Identity, one sentence</label>
                    <input
                      value={memoryDraft.identity || ""}
                      onChange={(e) => setMemoryDraft((d) => ({ ...d, identity: e.target.value }))}
                      className="input"
                    />
                  </div>
                  {LIST_FIELDS.map((f) => (
                    <div key={f}>
                      <label className="label capitalize">{f.replace("_", " ")}, one per line</label>
                      <Textarea
                        value={memoryDraft[f] || ""}
                        onChange={(e) => setMemoryDraft((d) => ({ ...d, [f]: e.target.value }))}
                        rows={3}
                      />
                    </div>
                  ))}
                  <div>
                    <label className="label">Achievements, one per line as Title :: summary</label>
                    <Textarea
                      value={memoryDraft.achievements || ""}
                      onChange={(e) => setMemoryDraft((d) => ({ ...d, achievements: e.target.value }))}
                      rows={4}
                    />
                  </div>
                  <div>
                    <label className="label">Communication style</label>
                    <input
                      value={memoryDraft.communication_style || ""}
                      onChange={(e) => setMemoryDraft((d) => ({ ...d, communication_style: e.target.value }))}
                      className="input"
                    />
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => saveMemoryMut.mutate()}
                      disabled={saveMemoryMut.isPending}
                      className="btn-primary"
                    >
                      {saveMemoryMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : "Save memory"}
                    </button>
                    <button onClick={() => setEditingMemory(false)} className="btn-secondary">
                      Cancel
                    </button>
                  </div>
                </Card>
              )}

              <Card className="space-y-5">
                <h2 className="font-semibold text-gray-900">{hasGraph ? "Update your answers" : "Answer these to build it"}</h2>
                {(kgQuestions || []).map((q) => (
                  <div key={q}>
                    <label className="label">{q}</label>
                    <Textarea
                      value={kgAnswers[q] || ""}
                      onChange={(e) => setKgAnswers((a) => ({ ...a, [q]: e.target.value }))}
                      rows={3}
                    />
                  </div>
                ))}

                <div className="border-t border-gray-100 pt-4 space-y-4">
                  <div>
                    <h3 className="font-medium text-gray-900 text-sm">Teach it anything else</h3>
                    <p className="text-sm text-gray-500">
                      Write your own question and answer it. Anything you want your memory to hold:
                      languages you speak, tools you swear by, things you will never compromise on.
                    </p>
                  </div>
                  {customPairs.map((pair, i) => (
                    <div key={i} className="space-y-2 rounded-lg border border-gray-200 p-3">
                      <div className="flex gap-2">
                        <input
                          value={pair.question}
                          onChange={(e) => setCustomPairs(ps => ps.map((p, j) => j === i ? { ...p, question: e.target.value } : p))}
                          placeholder="Your own question, for example: What languages do I speak?"
                          className="input flex-1"
                        />
                        <button
                          onClick={() => setCustomPairs(ps => ps.filter((_, j) => j !== i))}
                          className="btn-secondary px-3 text-red-600 border-red-200 hover:bg-red-50"
                          aria-label="Remove this question"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                      <Textarea
                        value={pair.answer}
                        onChange={(e) => setCustomPairs(ps => ps.map((p, j) => j === i ? { ...p, answer: e.target.value } : p))}
                        placeholder="Your answer, in your own words"
                        rows={2}
                      />
                    </div>
                  ))}
                  <button
                    onClick={() => setCustomPairs(ps => [...ps, { question: "", answer: "" }])}
                    className="btn-secondary text-sm"
                  >
                    <Plus className="w-4 h-4" /> Add your own question
                  </button>
                </div>

                <button
                  onClick={() => buildGraphMut.mutate()}
                  disabled={buildGraphMut.isPending || !hasAnyAnswer}
                  className="btn-primary w-full justify-center py-2.5"
                >
                  {buildGraphMut.isPending ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /> Growing your memory...</>
                  ) : (
                    <><BrainCircuit className="w-4 h-4" /> Add this to your memory</>
                  )}
                </button>
              </Card>
            </div>
          )}

          {tab === "email" && (
            <div className="space-y-5">
              <Card className="bg-blue-50 border-blue-100">
                <div className="flex gap-3">
                  <Mail className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
                  <div className="text-sm text-blue-900">
                    <p className="font-medium mb-0.5">Sending already works, nothing to set up</p>
                    <p className="text-blue-700">
                      {gmailOauthStatus?.default_sending_available
                        ? "Every application email you send already goes out with no setup on your part. The recruiter's reply lands in your own inbox either way, since Reply To is always set to your real email."
                        : "Connect an account below so sending works."}
                      {" "}Connecting Gmail below is optional, and only changes one thing: the email
                      leaves from your literal Gmail address instead of ApplyPilot's shared sender.
                      Nothing is ever sent automatically, every email is drafted first and only goes
                      out when you press send.
                    </p>
                  </div>
                </div>
              </Card>

              {gmailOauthStatus?.available && (
                <Card className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="font-semibold text-gray-900">Connect Gmail</h2>
                      <p className="text-sm text-gray-500">
                        The most reliable way to send: one click, no app password to generate or
                        paste, and it is used automatically whenever it is connected.
                      </p>
                    </div>
                    {profile?.gmail_connected && (
                      <span className="text-xs font-medium text-emerald-700 bg-emerald-50 px-2 py-1 rounded-full flex items-center gap-1 shrink-0">
                        <CheckCircle2 className="w-3.5 h-3.5" /> {profile.gmail_address}
                      </span>
                    )}
                  </div>
                  {profile?.gmail_connected && (() => {
                    const { daysLeft, warn } = gmailExpiry(profile.gmail_connected_at);
                    if (daysLeft == null) return null;
                    const hoursLeft = Math.round(daysLeft * 24);
                    return (
                      <p className={cn(
                        "text-xs px-2.5 py-2 rounded-lg",
                        warn ? "bg-amber-50 text-amber-700" : "text-gray-400"
                      )}>
                        {warn
                          ? `This connection expires in about ${hoursLeft} hour${hoursLeft === 1 ? "" : "s"} — reconnect now so sending never breaks mid use.`
                          : `Connection renews itself if you reconnect before it expires in about ${Math.round(daysLeft)} days.`}
                      </p>
                    );
                  })()}
                  {profile?.gmail_connected ? (
                    <div className="flex gap-2">
                      {gmailExpiry(profile.gmail_connected_at).warn && (
                        <button
                          onClick={() => connectGmailMut.mutate()}
                          disabled={connectGmailMut.isPending}
                          className="btn-primary"
                        >
                          {connectGmailMut.isPending
                            ? <Loader2 className="w-4 h-4 animate-spin" />
                            : <>Reconnect now <ExternalLink className="w-3.5 h-3.5" /></>}
                        </button>
                      )}
                      <button
                        onClick={() => disconnectGmailMut.mutate()}
                        disabled={disconnectGmailMut.isPending}
                        className="btn-secondary text-red-600 border-red-200 hover:bg-red-50"
                      >
                        Disconnect Gmail
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => connectGmailMut.mutate()}
                      disabled={connectGmailMut.isPending}
                      className="btn-primary"
                    >
                      {connectGmailMut.isPending
                        ? <Loader2 className="w-4 h-4 animate-spin" />
                        : <>Connect Gmail <ExternalLink className="w-3.5 h-3.5" /></>}
                    </button>
                  )}
                </Card>
              )}

              <Card className="space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="font-semibold text-gray-900">Advanced: send with an app password instead</h2>
                  {profile?.email_account_configured && (
                    <span className="text-xs font-medium text-emerald-700 bg-emerald-50 px-2 py-1 rounded-full flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" /> Connected as {profile.sender_email}
                    </span>
                  )}
                </div>
                <p className="text-xs text-gray-400">
                  Not needed for normal use, sending already works without this. Only used when
                  Gmail above is not connected, in place of the automatic default sender.
                </p>

                <div>
                  <label className="label">Your email address</label>
                  <input
                    value={emailForm.sender_email}
                    onChange={(e) => setEmailForm((f) => ({ ...f, sender_email: e.target.value }))}
                    placeholder="you@gmail.com"
                    className="input"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="label">SMTP server</label>
                    <input
                      value={emailForm.smtp_host}
                      onChange={(e) => setEmailForm((f) => ({ ...f, smtp_host: e.target.value }))}
                      placeholder="smtp.gmail.com"
                      className="input"
                    />
                  </div>
                  <div>
                    <label className="label">Port</label>
                    <input
                      type="number"
                      value={emailForm.smtp_port}
                      onChange={(e) => setEmailForm((f) => ({ ...f, smtp_port: Number(e.target.value) }))}
                      className="input"
                    />
                  </div>
                </div>

                <div>
                  <label className="label">Username</label>
                  <input
                    value={emailForm.smtp_username}
                    onChange={(e) => setEmailForm((f) => ({ ...f, smtp_username: e.target.value }))}
                    placeholder="Usually the same as your email address"
                    className="input"
                  />
                </div>

                <div>
                  <label className="label">App password</label>
                  <input
                    type="password"
                    value={emailForm.smtp_password}
                    onChange={(e) => setEmailForm((f) => ({ ...f, smtp_password: e.target.value }))}
                    placeholder="Stored only in encrypted form"
                    className="input"
                  />
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={() => saveEmailMut.mutate()}
                    disabled={saveEmailMut.isPending || !emailForm.sender_email || !emailForm.smtp_password}
                    className="btn-primary"
                  >
                    {saveEmailMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : "Connect account"}
                  </button>
                  {profile?.email_account_configured && (
                    <button
                      onClick={() => clearEmailMut.mutate()}
                      disabled={clearEmailMut.isPending}
                      className="btn-secondary text-red-600 border-red-200 hover:bg-red-50"
                    >
                      Disconnect
                    </button>
                  )}
                </div>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
