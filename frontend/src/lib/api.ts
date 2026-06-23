import axios from "axios";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: `${BASE}/api/v1`,
  headers: { "Content-Type": "application/json" },
  timeout: 60_000,
});

// Inject token from sessionStorage on every request
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = sessionStorage.getItem("ap_token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Redirect to login on 401
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401 && typeof window !== "undefined") {
      sessionStorage.removeItem("ap_token");
      if (!window.location.pathname.startsWith("/auth")) {
        window.location.href = "/auth/login";
      }
    }
    return Promise.reject(err);
  }
);

// ── Auth ──────────────────────────────────────────────────────────
export const authApi = {
  register: (d: { email: string; password: string; full_name: string }) =>
    api.post("/auth/register", d),
  login: (d: { email: string; password: string }) =>
    api.post("/auth/login", d),
  me: () => api.get("/auth/me"),
  updateMe: (d: { full_name?: string }) => api.patch("/auth/me", d),
};

// ── Profile ───────────────────────────────────────────────────────
export const profileApi = {
  get: () => api.get("/profile/"),
  update: (d: Record<string, unknown>) => api.patch("/profile/", d),
};

// ── Resumes ───────────────────────────────────────────────────────
export const resumeApi = {
  upload: (file: File, label?: string) => {
    const fd = new FormData();
    fd.append("file", file);
    if (label) fd.append("label", label);
    return api.post("/resumes/upload", fd, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  list: () => api.get("/resumes/"),
  get: (id: string) => api.get(`/resumes/${id}`),
  patch: (id: string, d: Record<string, unknown>) => api.patch(`/resumes/${id}`, d),
  delete: (id: string) => api.delete(`/resumes/${id}`),
};

// ── Jobs ──────────────────────────────────────────────────────────
export const jobApi = {
  create: (d: { url?: string; text?: string; title?: string; company?: string }) =>
    api.post("/jobs/", d),
  list: () => api.get("/jobs/"),
  get: (id: string) => api.get(`/jobs/${id}`),
  delete: (id: string) => api.delete(`/jobs/${id}`),
};

// ── Applications ──────────────────────────────────────────────────
export const appApi = {
  generate: (d: { job_id: string; resume_id: string; extra_context?: string }) =>
    api.post("/applications/generate", d),
  answerQuestions: (d: { questions: string[]; job_id?: string; extra_context?: string }) =>
    api.post("/applications/answer-questions", d),
  list: (status?: string) =>
    api.get("/applications/", { params: status ? { status } : {} }),
  stats: () => api.get("/applications/stats/summary"),
  get: (id: string) => api.get(`/applications/${id}`),
  update: (id: string, d: Record<string, unknown>) => api.patch(`/applications/${id}`, d),
  delete: (id: string) => api.delete(`/applications/${id}`),
};

// ── Google Form Autofill ────────────────────────────────────────────
// Fills the real form, stops before submit — you review and click
// submit yourself inside the actual Google Form tab.
export const autofillApi = {
  start: (d: { form_url: string; resume_id: string; job_id?: string; extra_context?: string }) =>
    api.post("/autofill/google-form", d, { timeout: 90_000 }),
  get: (id: string) => api.get(`/autofill/${id}`),
};
