"use client";
import { Suspense, useEffect, useState, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useDropzone } from "react-dropzone";
import toast from "react-hot-toast";
import {
  Upload, FileText, Loader2, CheckCircle2, BrainCircuit, Mail, Zap, ArrowRight, ExternalLink,
} from "lucide-react";
import { resumeApi, profileApi, emailApi } from "@/lib/api";
import { Card, Textarea } from "@/components/ui";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/auth";

const STEPS = ["Resume", "Knowledge graph", "Email account"] as const;

export default function OnboardingPage() {
  // useSearchParams needs a Suspense boundary to prerender, so the page
  // is a thin shell around the real component.
  return (
    <Suspense fallback={null}>
      <OnboardingPageInner />
    </Suspense>
  );
}

function OnboardingPageInner() {
  const router = useRouter();
  const qc = useQueryClient();
  const { user } = useAuthStore();
  const searchParams = useSearchParams();
  // Coming back from the Gmail consent screen mid wizard lands here with
  // ?gmailstep=1&gmail=connected — jump straight to the email step
  // instead of restarting the wizard from the resume upload.
  const [step, setStep] = useState(searchParams.get("gmailstep") === "1" ? 2 : 0);

  useEffect(() => {
    const token = typeof window !== "undefined" ? sessionStorage.getItem("ap_token") : null;
    if (!token) router.push("/auth/login");
  }, [router]);

  const gmailResult = searchParams.get("gmail");
  useEffect(() => {
    if (!gmailResult) return;
    if (gmailResult === "connected") toast.success("Gmail connected");
    else if (gmailResult === "denied") toast.error("Gmail connection was cancelled");
    else if (gmailResult === "noconsent") toast.error("Revoke ApplyPilot's access at myaccount.google.com/permissions, then try connecting again");
    else if (gmailResult === "error") toast.error("Could not connect Gmail, try again");
    qc.invalidateQueries({ queryKey: ["profile"] });
    window.history.replaceState(null, "", "/onboarding");
  }, [gmailResult, qc]);

  const { data: profile } = useQuery({
    queryKey: ["profile"],
    queryFn: () => profileApi.get().then(r => r.data),
  });
  const { data: gmailOauthStatus } = useQuery({
    queryKey: ["gmail-oauth-status"],
    queryFn: () => emailApi.oauthStatus().then(r => r.data),
  });
  const connectGmailMut = useMutation({
    mutationFn: () => emailApi.oauthStart("onboarding"),
    onSuccess: ({ data }) => { window.location.href = data.url; },
    onError: (err: any) => toast.error(err.response?.data?.detail || "Could not start the Gmail connection"),
  });

  // ── Step 1: resume ──────────────────────────────────────────────
  const [uploading, setUploading] = useState(false);
  const { data: resumesData } = useQuery({
    queryKey: ["resumes"],
    queryFn: () => resumeApi.list().then(r => r.data),
    refetchInterval: (q) => (q.state.data?.items || []).some((r: any) => r.status === "processing") ? 2000 : false,
  });
  const resumes = resumesData?.items || [];
  const hasReadyResume = resumes.some((r: any) => r.status === "ready");

  const onDrop = useCallback(async (files: File[]) => {
    if (!files[0]) return;
    setUploading(true);
    try {
      await resumeApi.upload(files[0]);
      toast.success("Uploaded, reading your resume now");
      qc.invalidateQueries({ queryKey: ["resumes"] });
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
    }
  }, [qc]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
      "text/plain": [".txt"],
    },
    maxSize: 10 * 1024 * 1024,
    multiple: false,
  });

  // ── Step 2: knowledge graph ──────────────────────────────────────
  const { data: kgQuestions } = useQuery({
    queryKey: ["knowledge-graph-questions"],
    queryFn: () => profileApi.knowledgeGraphQuestions().then(r => r.data.questions as string[]),
  });
  const [kgAnswers, setKgAnswers] = useState<Record<string, string>>({});
  const [kgBuilt, setKgBuilt] = useState(false);

  const buildGraphMut = useMutation({
    mutationFn: () =>
      profileApi.buildKnowledgeGraph(
        Object.entries(kgAnswers)
          .filter(([, answer]) => answer.trim())
          .map(([question, answer]) => ({ question, answer }))
      ),
    onSuccess: () => { setKgBuilt(true); toast.success("Knowledge graph built"); },
    onError: (err: any) => toast.error(err.response?.data?.detail || "Could not build the knowledge graph"),
  });

  // ── Step 3: email account ────────────────────────────────────────
  const [emailForm, setEmailForm] = useState({
    sender_email: "", smtp_host: "smtp.gmail.com", smtp_port: 587,
    smtp_username: "", smtp_password: "",
  });
  const [smtpConnectedLocal, setSmtpConnectedLocal] = useState(false);

  const saveEmailMut = useMutation({
    mutationFn: () => profileApi.setEmailCredentials(emailForm),
    onSuccess: () => { setSmtpConnectedLocal(true); qc.invalidateQueries({ queryKey: ["profile"] }); toast.success("Email account connected"); },
    onError: (err: any) => toast.error(err.response?.data?.detail || "Could not save email account"),
  });

  const gmailConnected = !!profile?.gmail_connected;
  const emailConnected = gmailConnected || smtpConnectedLocal || !!profile?.email_account_configured;

  // ── Finish ────────────────────────────────────────────────────────
  const finishMut = useMutation({
    mutationFn: () => profileApi.update({ onboarding_done: true }),
    onSuccess: ({ data }) => {
      // Write the fresh profile into the cache synchronously BEFORE
      // navigating. The (app) layout guard redirects back to onboarding
      // whenever the cached profile still reads onboarding_done: false, so
      // a plain invalidate (which refetches asynchronously) let the guard
      // fire on the stale value and bounce the user straight back here —
      // the "had to finish onboarding twice" loop. Seeding the cache with
      // onboarding_done: true closes that race.
      qc.setQueryData(["profile"], (old: any) => ({ ...(old || {}), ...(data || {}), onboarding_done: true }));
      router.push("/dashboard");
    },
  });

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-xl">
        <div className="text-center mb-6">
          <div className="w-9 h-9 bg-indigo-600 rounded-lg flex items-center justify-center mx-auto mb-3">
            <Zap className="w-4.5 h-4.5 text-white" />
          </div>
          <h1 className="text-xl font-bold text-gray-900">
            Welcome{user?.full_name ? `, ${user.full_name}` : ""}
          </h1>
          <p className="text-gray-500 text-sm mt-1">
            A few things first, then everything else in this tool gets grounded in your real background.
          </p>
        </div>

        <div className="flex items-center justify-center gap-2 mb-6">
          {STEPS.map((label, i) => (
            <div key={label} className={cn(
              "flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full",
              i === step ? "bg-indigo-600 text-white" : i < step ? "bg-emerald-50 text-emerald-700" : "bg-gray-100 text-gray-400"
            )}>
              {i < step && <CheckCircle2 className="w-3 h-3" />}
              {label}
            </div>
          ))}
        </div>

        {step === 0 && (
          <Card className="space-y-5">
            <div>
              <h2 className="font-semibold text-gray-900 flex items-center gap-2"><FileText className="w-4 h-4" /> Upload your resume</h2>
              <p className="text-sm text-gray-500 mt-1">This is read once and turned into your profile, experience, skills, and education.</p>
            </div>

            <div
              {...getRootProps()}
              className={cn(
                "border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all",
                isDragActive ? "border-indigo-400 bg-indigo-50" : "border-gray-200 hover:border-gray-300 hover:bg-gray-50",
                uploading && "opacity-60 pointer-events-none"
              )}
            >
              <input {...getInputProps()} />
              <div className="flex flex-col items-center gap-2">
                {uploading ? <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" /> : <Upload className="w-8 h-8 text-indigo-400" />}
                <p className="font-medium text-gray-900 text-sm">
                  {uploading ? "Uploading" : hasReadyResume ? "Resume ready, drop another to replace" : "Drag and drop your resume"}
                </p>
                <p className="text-gray-500 text-xs">PDF, DOCX, or TXT, up to 10 megabytes</p>
              </div>
            </div>

            {resumes.some((r: any) => r.status === "processing") && (
              <p className="text-sm text-gray-500 flex items-center gap-2"><Loader2 className="w-3.5 h-3.5 animate-spin" /> Reading your resume</p>
            )}

            <button
              onClick={() => setStep(1)}
              disabled={!hasReadyResume}
              className="btn-primary w-full justify-center py-2.5"
            >
              Continue <ArrowRight className="w-4 h-4" />
            </button>
          </Card>
        )}

        {step === 1 && (
          <Card className="space-y-5">
            <div>
              <h2 className="font-semibold text-gray-900 flex items-center gap-2"><BrainCircuit className="w-4 h-4" /> Tell us about yourself</h2>
              <p className="text-sm text-gray-500 mt-1">Answer in your own words. This becomes a knowledge graph of your values, strengths, and motivations that every form answer and email is grounded in, not just your resume.</p>
            </div>

            <div className="space-y-4 max-h-80 overflow-y-auto pr-1">
              {(kgQuestions || []).map((q) => (
                <div key={q}>
                  <label className="label">{q}</label>
                  <Textarea
                    value={kgAnswers[q] || ""}
                    onChange={(e) => setKgAnswers((a) => ({ ...a, [q]: e.target.value }))}
                    rows={2}
                  />
                </div>
              ))}
            </div>

            {!kgBuilt ? (
              <button
                onClick={() => buildGraphMut.mutate()}
                disabled={buildGraphMut.isPending || Object.values(kgAnswers).every((v) => !v.trim())}
                className="btn-primary w-full justify-center py-2.5"
              >
                {buildGraphMut.isPending ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> Building your knowledge graph</>
                ) : (
                  <><BrainCircuit className="w-4 h-4" /> Build knowledge graph</>
                )}
              </button>
            ) : (
              <button onClick={() => setStep(2)} className="btn-primary w-full justify-center py-2.5">
                Continue <ArrowRight className="w-4 h-4" />
              </button>
            )}

            <button onClick={() => setStep(2)} className="text-xs text-gray-400 hover:text-gray-600 w-full text-center">
              Skip for now, answer this later in settings
            </button>
          </Card>
        )}

        {step === 2 && (
          <Card className="space-y-5">
            <div>
              <h2 className="font-semibold text-gray-900 flex items-center gap-2"><Mail className="w-4 h-4" /> Sending is ready</h2>
              <p className="text-sm text-gray-500 mt-1">
                Nothing to set up. When you send an application, open it in your own mail app to
                send from your real address in one click, or send it instantly and it still
                reaches the recipient with replies routed back to you.
              </p>
            </div>

            {emailConnected && (
              <p className="text-sm text-emerald-700 bg-emerald-50 p-3 rounded-lg flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4" />
                {gmailConnected ? `Connected as ${profile?.gmail_address}` : `Connected as ${emailForm.sender_email}`}
              </p>
            )}

            {/* Advanced connection options are hidden by default — Gmail
                Connect only works for accounts on this app's Google test
                user list (Google blocks everyone else with an unverified
                app warning), and the app password path never works on our
                hosted backend since Render blocks outbound SMTP. Neither
                is something a random visitor should be steered toward. */}
            {!emailConnected && (
              <details className="text-sm">
                <summary className="cursor-pointer text-gray-500 hover:text-gray-700">
                  Advanced: connect your own address instead
                </summary>
                <div className="space-y-4 pt-4">
                  {gmailOauthStatus?.available && (
                    <>
                      <button
                        onClick={() => connectGmailMut.mutate()}
                        disabled={connectGmailMut.isPending}
                        className="btn-secondary w-full justify-center py-2.5"
                      >
                        {connectGmailMut.isPending
                          ? <Loader2 className="w-4 h-4 animate-spin" />
                          : <>Connect Gmail <ExternalLink className="w-3.5 h-3.5" /></>}
                      </button>
                      <p className="text-xs text-gray-400">
                        Only works if this account has been added as a tester — Google shows
                        everyone else an unverified app warning. Most people should skip this.
                      </p>
                      <div className="flex items-center gap-3 text-xs text-gray-400">
                        <div className="flex-1 h-px bg-gray-200" /> or <div className="flex-1 h-px bg-gray-200" />
                      </div>
                    </>
                  )}

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
                  <button
                    onClick={() => saveEmailMut.mutate()}
                    disabled={saveEmailMut.isPending || !emailForm.sender_email || !emailForm.smtp_password}
                    className="btn-secondary w-full justify-center py-2.5"
                  >
                    {saveEmailMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : "Connect with app password"}
                  </button>
                  <p className="text-xs text-gray-400">
                    Only works when this backend is self-hosted locally or on a host that allows
                    outbound SMTP — never works on the hosted version at applypilot.
                  </p>
                </div>
              </details>
            )}

            <button
              onClick={() => finishMut.mutate()}
              disabled={finishMut.isPending}
              className="btn-primary w-full justify-center py-2.5"
            >
              {finishMut.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                "Finish, take me to the dashboard"
              )}
            </button>
          </Card>
        )}
      </div>
    </div>
  );
}
