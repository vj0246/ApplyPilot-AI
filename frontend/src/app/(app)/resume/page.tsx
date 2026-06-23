"use client";
import { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useDropzone } from "react-dropzone";
import toast from "react-hot-toast";
import {
  Upload, FileText, Star, Trash2, Loader2, CheckCircle2,
  AlertCircle, Clock, ChevronDown, ChevronUp,
} from "lucide-react";
import { resumeApi } from "@/lib/api";
import { Card, EmptyState, Skeleton, ScoreCircle, Badge } from "@/components/ui";
import { cn, fmt } from "@/lib/utils";

export default function ResumePage() {
  const qc = useQueryClient();
  const [uploading, setUploading] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["resumes"],
    queryFn: () => resumeApi.list().then(r => r.data),
    refetchInterval: (q) => (q.state.data?.items || []).some((r: any) => r.status === "processing") ? 2500 : false,
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => resumeApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["resumes"] }); toast.success("Resume removed"); },
  });

  const primaryMut = useMutation({
    mutationFn: (id: string) => resumeApi.patch(id, { is_primary: true }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["resumes"] }); toast.success("Primary resume updated"); },
  });

  const onDrop = useCallback(async (files: File[]) => {
    if (!files[0]) return;
    setUploading(true);
    try {
      await resumeApi.upload(files[0]);
      toast.success("Uploaded — AI is analyzing your resume...");
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

  const items = data?.items || [];

  return (
    <div className="p-8 max-w-3xl">
      <div className="page-header">
        <h1 className="page-title">My Resume</h1>
        <p className="page-desc">Upload your resume — AI extracts your skills, experience, and education</p>
      </div>

      {/* Upload zone */}
      <div
        {...getRootProps()}
        className={cn(
          "border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all mb-6",
          isDragActive ? "border-indigo-400 bg-indigo-50" : "border-gray-200 hover:border-gray-300 hover:bg-gray-50",
          uploading && "opacity-60 pointer-events-none"
        )}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center gap-3">
          {uploading ? (
            <Loader2 className="w-9 h-9 text-indigo-500 animate-spin" />
          ) : (
            <div className="w-12 h-12 bg-indigo-50 rounded-xl flex items-center justify-center">
              <Upload className={cn("w-5 h-5", isDragActive ? "text-indigo-600" : "text-indigo-400")} />
            </div>
          )}
          <div>
            <p className="font-medium text-gray-900">
              {uploading ? "Uploading…" : isDragActive ? "Drop to upload" : "Drag & drop your resume"}
            </p>
            <p className="text-gray-500 text-sm mt-0.5">PDF, DOCX, or TXT — max 10MB</p>
          </div>
          {!uploading && <span className="btn-secondary text-sm">Browse files</span>}
        </div>
      </div>

      {/* Resume list */}
      {isLoading ? (
        <div className="space-y-3">{[1,2].map(i => <Skeleton key={i} className="h-20" />)}</div>
      ) : items.length === 0 ? (
        <EmptyState icon={<FileText className="w-10 h-10" />} title="No resumes uploaded yet" />
      ) : (
        <div className="space-y-3">
          {items.map((r: any) => (
            <Card key={r.id} className="p-0 overflow-hidden">
              <div className="flex items-center gap-4 p-4">
                <div className="w-11 h-11 bg-gray-100 rounded-lg flex items-center justify-center shrink-0">
                  <FileText className="w-5 h-5 text-gray-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-medium text-gray-900 text-sm truncate">{r.label || r.filename}</p>
                    {r.is_primary && <Badge className="bg-indigo-50 text-indigo-700">Primary</Badge>}
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                    <StatusIcon status={r.status} />
                    <span className="capitalize">{r.status}</span>
                    <span>·</span>
                    <span>{fmt(r.created_at)}</span>
                  </div>
                  {r.error_msg && <p className="text-red-500 text-xs mt-1">{r.error_msg}</p>}
                </div>
                {r.ats_score != null && <ScoreCircle score={r.ats_score} size="sm" />}
                <div className="flex items-center gap-1 shrink-0">
                  {!r.is_primary && r.status === "ready" && (
                    <button onClick={() => primaryMut.mutate(r.id)} title="Set as primary" className="p-2 text-gray-400 hover:text-yellow-500 transition-colors">
                      <Star className="w-4 h-4" />
                    </button>
                  )}
                  {r.parsed_data && (
                    <button onClick={() => setExpanded(expanded === r.id ? null : r.id)} className="p-2 text-gray-400 hover:text-gray-700 transition-colors">
                      {expanded === r.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>
                  )}
                  <button onClick={() => { if (confirm("Delete this resume?")) deleteMut.mutate(r.id); }} className="p-2 text-gray-400 hover:text-red-500 transition-colors">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {expanded === r.id && r.parsed_data && (
                <div className="border-t border-gray-100 p-4 bg-gray-50 text-sm space-y-3">
                  <Row label="Name" value={r.parsed_data.name} />
                  <Row label="Email" value={r.parsed_data.email} />
                  <Row label="Location" value={r.parsed_data.location} />
                  {r.parsed_data.summary && <Row label="Summary" value={r.parsed_data.summary} />}
                  {r.parsed_data.skills?.length > 0 && (
                    <div>
                      <p className="text-gray-500 text-xs font-medium mb-1.5">Skills</p>
                      <div className="flex flex-wrap gap-1.5">
                        {r.parsed_data.skills.map((s: string) => (
                          <span key={s} className="badge bg-white border border-gray-200 text-gray-700">{s}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {r.parsed_data.experience?.length > 0 && (
                    <div>
                      <p className="text-gray-500 text-xs font-medium mb-1.5">Experience</p>
                      <div className="space-y-2">
                        {r.parsed_data.experience.map((e: any, i: number) => (
                          <div key={i} className="text-gray-700">
                            <p className="font-medium">{e.title} — {e.company}</p>
                            <p className="text-gray-400 text-xs">{e.start} – {e.end}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value?: string }) {
  if (!value) return null;
  return (
    <div>
      <p className="text-gray-500 text-xs font-medium">{label}</p>
      <p className="text-gray-800">{value}</p>
    </div>
  );
}

function StatusIcon({ status }: { status: string }) {
  if (status === "ready") return <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />;
  if (status === "processing") return <Loader2 className="w-3.5 h-3.5 text-blue-500 animate-spin" />;
  if (status === "failed") return <AlertCircle className="w-3.5 h-3.5 text-red-500" />;
  return <Clock className="w-3.5 h-3.5 text-gray-400" />;
}
