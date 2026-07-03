"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import {
  Zap, FileText, Briefcase, Loader2, MessageSquare,
  Sparkles, Copy, Link2, ExternalLink, AlertTriangle, ShieldCheck, Send, Pencil,
} from "lucide-react";
import { resumeApi, jobApi, appApi, autofillApi, emailApi } from "@/lib/api";
import { Card, Badge, Textarea } from "@/components/ui";
import { cn } from "@/lib/utils";

export default function ApplyPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [tab, setTab] = useState<"generate" | "formfill" | "googleform" | "email">("generate");

  // ── Data ──────────────────────────────────────────────────
  const { data: resumesData } = useQuery({
    queryKey: ["resumes"],
    queryFn: () => resumeApi.list().then(r => r.data),
  });
  const { data: jobsData } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => jobApi.list().then(r => r.data),
  });

  const readyResumes = (resumesData?.items || []).filter((r: any) => r.status === "ready");
  const readyJobs    = (jobsData?.items   || []).filter((j: any) => j.status === "ready");

  const [resumeId, setResumeId] = useState("");
  const [jobId, setJobId]       = useState("");
  const [context, setContext]   = useState("");

  // Auto-select primary resume / latest job
  if (!resumeId && readyResumes.length) {
    const primary = readyResumes.find((r: any) => r.is_primary) || readyResumes[0];
    setResumeId(primary.id);
  }
  if (!jobId && readyJobs.length) {
    setJobId(readyJobs[0].id);
  }

  // ── Generate application ─────────────────────────────────
  const generateMut = useMutation({
    mutationFn: () => appApi.generate({ job_id: jobId, resume_id: resumeId, extra_context: context }),
    onSuccess: ({ data }) => {
      toast.success("Generating your application...");
      qc.invalidateQueries({ queryKey: ["apps"] });
      router.push(`/applications/${data.id}`);
    },
    onError: (err: any) => toast.error(err.response?.data?.detail || "Generation failed"),
  });

  // ── Form filler ────────────────────────────────────────────
  const [questionsRaw, setQuestionsRaw] = useState("");
  const [formContext, setFormContext]  = useState("");
  const [formJobId, setFormJobId]      = useState("");
  const [answers, setAnswers] = useState<{question: string; answer: string}[] | null>(null);

  const answerMut = useMutation({
    mutationFn: () => {
      const questions = questionsRaw.split("\n").map(q => q.trim()).filter(Boolean);
      return appApi.answerQuestions({ questions, job_id: formJobId || undefined, extra_context: formContext });
    },
    onSuccess: ({ data }) => setAnswers(data.answers),
    onError: (err: any) => toast.error(err.response?.data?.detail || "Failed to generate answers"),
  });

  // ── Google Form autofill ─────────────────────────────────────
  const [formUrl, setFormUrl] = useState("");
  const [gfResumeId, setGfResumeId] = useState("");
  const [gfJobId, setGfJobId] = useState("");
  const [gfContext, setGfContext] = useState("");
  const [runId, setRunId] = useState<string | null>(null);

  const startAutofillMut = useMutation({
    mutationFn: () => autofillApi.start({
      form_url: formUrl.trim(),
      resume_id: gfResumeId || resumeId,
      job_id: gfJobId || undefined,
      extra_context: gfContext,
    }),
    onSuccess: ({ data }) => { setRunId(data.id); toast.success("Opening the form..."); },
    onError: (err: any) => toast.error(err.response?.data?.detail || "Couldn't start autofill"),
  });

  const { data: runData } = useQuery({
    queryKey: ["autofill", runId],
    queryFn: () => autofillApi.get(runId!).then(r => r.data),
    enabled: !!runId,
    refetchInterval: (q) => q.state.data?.status === "running" ? 2000 : false,
  });

  const isRunning = runData?.status === "running";
  const isReady = runData?.status === "ready";
  const isFailed = runData?.status === "failed";
  const result = runData?.result;

  // ── Application email ─────────────────────────────────────────────
  const [emailJobId, setEmailJobId] = useState("");
  const [emailResumeId, setEmailResumeId] = useState("");
  const [recipientEmail, setRecipientEmail] = useState("");
  const [emailContext, setEmailContext] = useState("");
  const [emailDraftId, setEmailDraftId] = useState<string | null>(null);

  const draftEmailMut = useMutation({
    mutationFn: () => emailApi.draft({
      job_id: emailJobId,
      resume_id: emailResumeId || resumeId,
      recipient_email: recipientEmail.trim(),
      extra_context: emailContext,
    }),
    onSuccess: ({ data }) => { setEmailDraftId(data.id); toast.success("Draft written, review it before sending"); },
    onError: (err: any) => toast.error(err.response?.data?.detail || "Couldn't draft the email"),
  });

  const { data: emailDraft } = useQuery({
    queryKey: ["email", emailDraftId],
    queryFn: () => emailApi.get(emailDraftId!).then(r => r.data),
    enabled: !!emailDraftId,
  });

  const [editedSubject, setEditedSubject] = useState<string | null>(null);
  const [editedBody, setEditedBody] = useState<string | null>(null);
  const subjectValue = editedSubject ?? emailDraft?.subject ?? "";
  const bodyValue = editedBody ?? emailDraft?.body ?? "";

  const saveEditMut = useMutation({
    mutationFn: () => emailApi.update(emailDraftId!, { subject: subjectValue, body: bodyValue }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["email", emailDraftId] }); toast.success("Draft updated"); },
  });

  const sendEmailMut = useMutation({
    mutationFn: () => emailApi.send(emailDraftId!),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["email", emailDraftId] }); toast.success("Email sent from your address"); },
    onError: (err: any) => toast.error(err.response?.data?.detail || "Could not send the email"),
  });

  const noResume = readyResumes.length === 0;
  const noJob = readyJobs.length === 0;

  return (
    <div className="p-8 max-w-3xl">
      <div className="page-header">
        <h1 className="page-title">Apply / Generate</h1>
        <p className="page-desc">Generate a full application or get answers to any form question</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 flex-wrap">
        <TabBtn active={tab === "generate"} onClick={() => setTab("generate")} icon={Sparkles}>
          Generate Application
        </TabBtn>
        <TabBtn active={tab === "formfill"} onClick={() => setTab("formfill")} icon={MessageSquare}>
          Form Question Filler
        </TabBtn>
        <TabBtn active={tab === "googleform"} onClick={() => setTab("googleform")} icon={Link2}>
          Form Autofill
        </TabBtn>
        <TabBtn active={tab === "email"} onClick={() => setTab("email")} icon={Send}>
          Mail the Job Description
        </TabBtn>
      </div>

      {tab === "generate" ? (
        <>
          {(noResume || noJob) && (
            <Card className="mb-5 bg-yellow-50 border-yellow-100">
              <p className="text-sm text-yellow-800 font-medium mb-1">
                {noResume && noJob ? "Upload a resume and add a job to get started" :
                 noResume ? "Upload a resume first" : "Add a job posting first"}
              </p>
              <div className="flex gap-2 mt-2">
                {noResume && <a href="/resume" className="btn-secondary text-xs py-1.5">Upload resume</a>}
                {noJob && <a href="/jobs" className="btn-secondary text-xs py-1.5">Add job</a>}
              </div>
            </Card>
          )}

          <Card className="space-y-5">
            {/* Resume select */}
            <div>
              <label className="label flex items-center gap-1.5"><FileText className="w-3.5 h-3.5" /> Resume</label>
              {readyResumes.length === 0 ? (
                <p className="text-sm text-gray-400">No processed resumes available</p>
              ) : (
                <div className="space-y-2">
                  {readyResumes.map((r: any) => (
                    <label key={r.id} className={cn(
                      "flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors",
                      resumeId === r.id ? "border-indigo-300 bg-indigo-50" : "border-gray-200 hover:bg-gray-50"
                    )}>
                      <input type="radio" checked={resumeId === r.id} onChange={() => setResumeId(r.id)} className="text-indigo-600" />
                      <FileText className="w-4 h-4 text-gray-400" />
                      <span className="text-sm font-medium text-gray-800 flex-1">{r.label || r.filename}</span>
                      {r.is_primary && <Badge className="bg-indigo-100 text-indigo-700">Primary</Badge>}
                      {r.ats_score != null && <span className="text-xs text-gray-400">ATS {r.ats_score}</span>}
                    </label>
                  ))}
                </div>
              )}
            </div>

            {/* Job select */}
            <div>
              <label className="label flex items-center gap-1.5"><Briefcase className="w-3.5 h-3.5" /> Job posting</label>
              {readyJobs.length === 0 ? (
                <p className="text-sm text-gray-400">No processed jobs available</p>
              ) : (
                <div className="space-y-2">
                  {readyJobs.map((j: any) => (
                    <label key={j.id} className={cn(
                      "flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors",
                      jobId === j.id ? "border-indigo-300 bg-indigo-50" : "border-gray-200 hover:bg-gray-50"
                    )}>
                      <input type="radio" checked={jobId === j.id} onChange={() => setJobId(j.id)} className="text-indigo-600" />
                      <Briefcase className="w-4 h-4 text-gray-400" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-800 truncate">{j.title}</p>
                        <p className="text-xs text-gray-400 truncate">{j.company}</p>
                      </div>
                    </label>
                  ))}
                </div>
              )}
            </div>

            {/* Extra context */}
            <div>
              <label className="label">Extra context <span className="text-gray-400 font-normal">(optional)</span></label>
              <Textarea
                value={context}
                onChange={(e) => setContext(e.target.value)}
                rows={3}
                placeholder="e.g. 'I was referred by a current employee', 'I have a portfolio project relevant to this role'..."
              />
            </div>

            <button
              onClick={() => generateMut.mutate()}
              disabled={!resumeId || !jobId || generateMut.isPending}
              className="btn-primary w-full justify-center py-2.5"
            >
              {generateMut.isPending ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</>
              ) : (
                <><Sparkles className="w-4 h-4" /> Generate Application</>
              )}
            </button>
          </Card>
        </>
      ) : tab === "formfill" ? (
        <Card className="space-y-5">
          <div>
            <label className="label">Paste form questions <span className="text-gray-400 font-normal">(one per line)</span></label>
            <Textarea
              value={questionsRaw}
              onChange={(e) => setQuestionsRaw(e.target.value)}
              rows={6}
              placeholder={"Why do you want to work here?\nWhat's your greatest strength?\nDescribe a challenging project you completed.\nWhat are your salary expectations?"}
            />
          </div>

          {readyJobs.length > 0 && (
            <div>
              <label className="label">Related job <span className="text-gray-400 font-normal">(optional — improves relevance)</span></label>
              <select value={formJobId} onChange={(e) => setFormJobId(e.target.value)} className="input">
                <option value="">No specific job</option>
                {readyJobs.map((j: any) => (
                  <option key={j.id} value={j.id}>{j.title} — {j.company}</option>
                ))}
              </select>
            </div>
          )}

          <div>
            <label className="label">Extra context <span className="text-gray-400 font-normal">(optional)</span></label>
            <Textarea
              value={formContext}
              onChange={(e) => setFormContext(e.target.value)}
              rows={2}
              placeholder="Anything specific you want reflected in the answers..."
            />
          </div>

          <button
            onClick={() => answerMut.mutate()}
            disabled={!questionsRaw.trim() || readyResumes.length === 0 || answerMut.isPending}
            className="btn-primary w-full justify-center py-2.5"
          >
            {answerMut.isPending ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Writing answers...</>
            ) : (
              <><Zap className="w-4 h-4" /> Generate Answers</>
            )}
          </button>

          {readyResumes.length === 0 && (
            <p className="text-xs text-yellow-700 bg-yellow-50 p-2 rounded-lg">
              Upload and process a resume first — answers are based on your real experience.
            </p>
          )}

          {/* Results */}
          {answers && (
            <div className="space-y-3 pt-2 border-t border-gray-100">
              <p className="text-sm font-semibold text-gray-900 pt-3">Generated answers</p>
              {answers.map((a, i) => (
                <div key={i} className="bg-gray-50 rounded-lg p-4 border border-gray-100">
                  <p className="text-xs font-semibold text-indigo-600 mb-1.5">{a.question}</p>
                  <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{a.answer}</p>
                  <button
                    onClick={() => { navigator.clipboard.writeText(a.answer); toast.success("Copied!"); }}
                    className="mt-2 text-xs text-gray-400 hover:text-indigo-600 flex items-center gap-1 transition-colors"
                  >
                    <Copy className="w-3 h-3" /> Copy
                  </button>
                </div>
              ))}
            </div>
          )}
        </Card>
      ) : null}

      {tab === "googleform" && (
        <div className="space-y-5">
          <Card className="bg-blue-50 border-blue-100">
            <div className="flex gap-3">
              <ShieldCheck className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
              <div className="text-sm text-blue-900">
                <p className="font-medium mb-0.5">We fill it, you submit it</p>
                <p className="text-blue-700">
                  This opens your Google Form or Microsoft Form, fills in every field with
                  answers grounded in your resume and your knowledge graph, and stops. Nothing
                  gets submitted automatically, you review the filled form and click submit
                  yourself.
                </p>
              </div>
            </div>
          </Card>

          <Card className="space-y-5">
            <div>
              <label className="label flex items-center gap-1.5"><Link2 className="w-3.5 h-3.5" /> Form link</label>
              <input
                value={formUrl}
                onChange={(e) => setFormUrl(e.target.value)}
                placeholder="https://docs.google.com/forms/d/e/.../viewform or https://forms.office.com/..."
                className="input"
              />
            </div>

            <div>
              <label className="label flex items-center gap-1.5"><FileText className="w-3.5 h-3.5" /> Resume to use</label>
              {readyResumes.length === 0 ? (
                <p className="text-sm text-gray-400">No processed resumes available</p>
              ) : (
                <select value={gfResumeId || resumeId} onChange={(e) => setGfResumeId(e.target.value)} className="input">
                  {readyResumes.map((r: any) => (
                    <option key={r.id} value={r.id}>{r.label || r.filename}{r.is_primary ? " (primary)" : ""}</option>
                  ))}
                </select>
              )}
            </div>

            {readyJobs.length > 0 && (
              <div>
                <label className="label">Related job <span className="text-gray-400 font-normal">(optional — improves relevance)</span></label>
                <select value={gfJobId} onChange={(e) => setGfJobId(e.target.value)} className="input">
                  <option value="">No specific job</option>
                  {readyJobs.map((j: any) => (
                    <option key={j.id} value={j.id}>{j.title} — {j.company}</option>
                  ))}
                </select>
              </div>
            )}

            <div>
              <label className="label">Extra context <span className="text-gray-400 font-normal">(optional)</span></label>
              <Textarea
                value={gfContext}
                onChange={(e) => setGfContext(e.target.value)}
                rows={2}
                placeholder="Anything specific you want reflected in the answers..."
              />
            </div>

            <button
              onClick={() => startAutofillMut.mutate()}
              disabled={!formUrl.trim() || (!gfResumeId && !resumeId) || isRunning || startAutofillMut.isPending}
              className="btn-primary w-full justify-center py-2.5"
            >
              {isRunning || startAutofillMut.isPending ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Filling the form...</>
              ) : (
                <><Zap className="w-4 h-4" /> Fill this form</>
              )}
            </button>

            {readyResumes.length === 0 && (
              <p className="text-xs text-yellow-700 bg-yellow-50 p-2 rounded-lg">
                Upload and process a resume first — answers are based on your real experience.
              </p>
            )}
          </Card>

          {isRunning && (
            <Card className="text-center py-8">
              <Loader2 className="w-7 h-7 text-indigo-500 animate-spin mx-auto mb-3" />
              <p className="font-medium text-gray-900">Opening the form and filling it in…</p>
              <p className="text-gray-500 text-sm mt-1">Reading every question, writing answers, typing them in — about 15-30 seconds</p>
            </Card>
          )}

          {isFailed && (
            <Card className="bg-red-50 border-red-100">
              <div className="flex gap-2">
                <AlertTriangle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                <p className="text-sm text-red-700">{runData?.error || "Autofill failed. Check the link and try again."}</p>
              </div>
            </Card>
          )}

          {isReady && result && (
            <Card className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-semibold text-gray-900">{result.title || "Form filled"}</p>
                  <p className="text-gray-500 text-sm">
                    {result.fields.length} field(s) found
                    {result.unfilled_count > 0 && (
                      <span className="text-yellow-600"> · {result.unfilled_count} need your attention</span>
                    )}
                  </p>
                </div>
                <a href={result.form_url} target="_blank" rel="noopener noreferrer" className="btn-primary text-sm">
                  Open form to review & submit <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>

              {result.screenshot_base64 && (
                <img
                  src={`data:image/png;base64,${result.screenshot_base64}`}
                  alt="Filled form preview"
                  className="w-full rounded-lg border border-gray-200"
                />
              )}

              <div className="space-y-2 pt-2 border-t border-gray-100">
                <p className="text-sm font-semibold text-gray-900 pt-3">What was filled in</p>
                {result.fields.map((f: any, i: number) => (
                  <div key={i} className="bg-gray-50 rounded-lg p-3 border border-gray-100 flex items-start gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-semibold text-indigo-600 mb-1">{f.question}</p>
                      <p className="text-sm text-gray-700">{f.answer || <span className="italic text-gray-400">Not filled — fill manually</span>}</p>
                    </div>
                    <Badge className={cn(
                      f.confidence === "high" ? "bg-emerald-50 text-emerald-700" :
                      f.confidence === "low" ? "bg-yellow-50 text-yellow-700" :
                      "bg-gray-100 text-gray-600"
                    )}>
                      {f.confidence}
                    </Badge>
                  </div>
                ))}
              </div>

              <p className="text-xs text-gray-400 pt-2 border-t border-gray-100">
                Open the form above to double-check everything, then click Submit yourself inside Google Forms.
                ApplyPilot never submits on your behalf.
              </p>
            </Card>
          )}
        </div>
      )}

      {tab === "email" && (
        <div className="space-y-5">
          <Card className="bg-blue-50 border-blue-100">
            <div className="flex gap-3">
              <ShieldCheck className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
              <div className="text-sm text-blue-900">
                <p className="font-medium mb-0.5">We draft it, you send it</p>
                <p className="text-blue-700">
                  This writes an application email about the job description from your resume
                  and your knowledge graph. Nothing goes out until you review the draft below,
                  edit it if you want, and press send. It sends from your own address, connected
                  in settings under Email Account.
                </p>
              </div>
            </div>
          </Card>

          <Card className="space-y-5">
            <div>
              <label className="label flex items-center gap-1.5"><Briefcase className="w-3.5 h-3.5" /> Job posting</label>
              {readyJobs.length === 0 ? (
                <p className="text-sm text-gray-400">No processed jobs available</p>
              ) : (
                <select value={emailJobId} onChange={(e) => setEmailJobId(e.target.value)} className="input">
                  <option value="">Select a job</option>
                  {readyJobs.map((j: any) => (
                    <option key={j.id} value={j.id}>{j.title} — {j.company}</option>
                  ))}
                </select>
              )}
            </div>

            <div>
              <label className="label flex items-center gap-1.5"><FileText className="w-3.5 h-3.5" /> Resume to use</label>
              {readyResumes.length === 0 ? (
                <p className="text-sm text-gray-400">No processed resumes available</p>
              ) : (
                <select value={emailResumeId || resumeId} onChange={(e) => setEmailResumeId(e.target.value)} className="input">
                  {readyResumes.map((r: any) => (
                    <option key={r.id} value={r.id}>{r.label || r.filename}{r.is_primary ? " (primary)" : ""}</option>
                  ))}
                </select>
              )}
            </div>

            <div>
              <label className="label">Recipient email</label>
              <input
                value={recipientEmail}
                onChange={(e) => setRecipientEmail(e.target.value)}
                placeholder="hiring@company.com"
                className="input"
              />
            </div>

            <div>
              <label className="label">Extra context <span className="text-gray-400 font-normal">(optional)</span></label>
              <Textarea
                value={emailContext}
                onChange={(e) => setEmailContext(e.target.value)}
                rows={2}
                placeholder="Anything specific you want reflected in the email..."
              />
            </div>

            <button
              onClick={() => draftEmailMut.mutate()}
              disabled={!emailJobId || !recipientEmail.trim() || (!emailResumeId && !resumeId) || draftEmailMut.isPending}
              className="btn-primary w-full justify-center py-2.5"
            >
              {draftEmailMut.isPending ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Writing the draft...</>
              ) : (
                <><Pencil className="w-4 h-4" /> Draft the email</>
              )}
            </button>
          </Card>

          {emailDraft && (
            <Card className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="font-semibold text-gray-900">Review before sending</h2>
                <Badge className={cn(
                  emailDraft.status === "sent" ? "bg-emerald-50 text-emerald-700" :
                  emailDraft.status === "failed" ? "bg-red-50 text-red-700" :
                  "bg-gray-100 text-gray-600"
                )}>
                  {emailDraft.status}
                </Badge>
              </div>

              <div>
                <label className="label">Subject</label>
                <input
                  value={subjectValue}
                  onChange={(e) => setEditedSubject(e.target.value)}
                  disabled={emailDraft.status === "sent"}
                  className="input"
                />
              </div>

              <div>
                <label className="label">Body</label>
                <Textarea
                  value={bodyValue}
                  onChange={(e) => setEditedBody(e.target.value)}
                  disabled={emailDraft.status === "sent"}
                  rows={8}
                />
              </div>

              {emailDraft.status === "failed" && emailDraft.error && (
                <p className="text-sm text-red-700 bg-red-50 p-2 rounded-lg">{emailDraft.error}</p>
              )}

              {emailDraft.status !== "sent" && (
                <div className="flex gap-2">
                  <button
                    onClick={() => saveEditMut.mutate()}
                    disabled={saveEditMut.isPending || (editedSubject === null && editedBody === null)}
                    className="btn-secondary"
                  >
                    Save edits
                  </button>
                  <button
                    onClick={() => sendEmailMut.mutate()}
                    disabled={sendEmailMut.isPending}
                    className="btn-primary flex-1 justify-center"
                  >
                    {sendEmailMut.isPending ? (
                      <><Loader2 className="w-4 h-4 animate-spin" /> Sending...</>
                    ) : (
                      <><Send className="w-4 h-4" /> Send from my address</>
                    )}
                  </button>
                </div>
              )}

              {emailDraft.status === "sent" && (
                <p className="text-sm text-emerald-700 bg-emerald-50 p-2 rounded-lg">
                  Sent to {emailDraft.recipient_email} on {new Date(emailDraft.sent_at).toLocaleString()}.
                </p>
              )}
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

function TabBtn({ active, onClick, icon: Icon, children }: any) {
  return (
    <button onClick={onClick} className={cn(
      "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors",
      active ? "bg-indigo-600 text-white" : "bg-white text-gray-600 border border-gray-200 hover:bg-gray-50"
    )}>
      <Icon className="w-4 h-4" />
      {children}
    </button>
  );
}
