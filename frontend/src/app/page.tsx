import Link from "next/link";
import { Zap, FileText, BarChart2, Mail, MessageSquare, ArrowRight } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white">
      {/* Nav */}
      <header className="border-b border-gray-100 bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center">
              <Zap className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-gray-900">ApplyPilot</span>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/auth/login" className="text-sm text-gray-600 hover:text-gray-900 font-medium">
              Sign in
            </Link>
            <Link href="/auth/register" className="btn-primary text-sm py-2">
              Get started free
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 pt-20 pb-16 text-center">
        <div className="inline-flex items-center gap-2 bg-indigo-50 text-indigo-700 text-xs font-medium px-3 py-1.5 rounded-full mb-6">
          <Zap className="w-3 h-3" /> Powered by free AI — no credit card needed
        </div>
        <h1 className="text-5xl font-bold text-gray-900 leading-tight mb-5 max-w-3xl mx-auto">
          Upload your resume once.{" "}
          <span className="text-indigo-600">Apply everywhere intelligently.</span>
        </h1>
        <p className="text-xl text-gray-500 max-w-2xl mx-auto mb-8 leading-relaxed">
          ApplyPilot reads your resume and any job posting, then generates a tailored cover letter,
          application email, and answers to every form question — in under 30 seconds.
        </p>
        <div className="flex items-center justify-center gap-3 flex-wrap">
          <Link href="/auth/register" className="btn-primary px-6 py-3 text-base">
            Start for free <ArrowRight className="w-4 h-4" />
          </Link>
          <Link href="/auth/login" className="btn-secondary px-6 py-3 text-base">
            Sign in
          </Link>
        </div>
        <p className="text-gray-400 text-sm mt-4">
          Free forever · Open source · No subscriptions
        </p>
      </section>

      {/* Feature grid */}
      <section className="max-w-6xl mx-auto px-6 py-16">
        <h2 className="text-2xl font-bold text-gray-900 text-center mb-3">
          Everything you need to apply smarter
        </h2>
        <p className="text-gray-500 text-center mb-12">
          One tool for the entire job application process
        </p>
        <div className="grid md:grid-cols-3 gap-6">
          {[
            {
              icon: FileText, title: "AI Resume Parser",
              desc: "Upload your PDF or DOCX once. We extract your skills, experience, education, and ATS keywords automatically.",
              color: "text-blue-600", bg: "bg-blue-50",
            },
            {
              icon: BarChart2, title: "Fit Score & Gap Analysis",
              desc: "See exactly how well you match a job (0–100) with a breakdown by skills, experience, and culture fit.",
              color: "text-indigo-600", bg: "bg-indigo-50",
            },
            {
              icon: Mail, title: "Cover Letter & Email",
              desc: "Humanized, personalized cover letter and application email — sounds like you wrote it, not AI.",
              color: "text-purple-600", bg: "bg-purple-50",
            },
            {
              icon: MessageSquare, title: "Form Question Answers",
              desc: "Paste any application form questions. Get specific, grounded answers based on your real experience.",
              color: "text-green-600", bg: "bg-green-50",
            },
            {
              icon: FileText, title: "Adapted Resume",
              desc: "Resume bullets rewritten to naturally incorporate job keywords — without adding anything false.",
              color: "text-orange-600", bg: "bg-orange-50",
            },
            {
              icon: BarChart2, title: "Application Tracker",
              desc: "Track every application: status updates, fit scores, cover letters, and notes in one dashboard.",
              color: "text-teal-600", bg: "bg-teal-50",
            },
          ].map((f) => (
            <div key={f.title} className="card p-6 hover:shadow-md transition-shadow">
              <div className={`w-10 h-10 ${f.bg} rounded-lg flex items-center justify-center mb-4`}>
                <f.icon className={`w-5 h-5 ${f.color}`} />
              </div>
              <h3 className="font-semibold text-gray-900 mb-2">{f.title}</h3>
              <p className="text-gray-500 text-sm leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="bg-gray-50 py-16">
        <div className="max-w-4xl mx-auto px-6">
          <h2 className="text-2xl font-bold text-gray-900 text-center mb-12">How it works</h2>
          <div className="space-y-6">
            {[
              { n: "1", t: "Upload your resume", d: "PDF or DOCX. AI extracts everything in ~20 seconds." },
              { n: "2", t: "Add a job posting", d: "Paste the URL or copy-paste the job description text." },
              { n: "3", t: "Click Generate", d: "AI writes your cover letter, email, and adapted resume bullets in ~15 seconds." },
              { n: "4", t: "Review, edit, and send", d: "Copy your materials, track the application, update status as things progress." },
            ].map((s) => (
              <div key={s.n} className="flex items-start gap-5 card p-5">
                <div className="w-9 h-9 bg-indigo-600 rounded-full flex items-center justify-center text-white font-bold text-sm shrink-0">
                  {s.n}
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 mb-1">{s.t}</h3>
                  <p className="text-gray-500 text-sm">{s.d}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-3xl mx-auto px-6 py-20 text-center">
        <h2 className="text-3xl font-bold text-gray-900 mb-4">Ready to apply smarter?</h2>
        <p className="text-gray-500 mb-8">Free, open source, and takes 2 minutes to set up.</p>
        <Link href="/auth/register" className="btn-primary px-8 py-3 text-base">
          Create free account <ArrowRight className="w-4 h-4" />
        </Link>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-100 py-8 text-center text-gray-400 text-sm">
        <p>© {new Date().getFullYear()} ApplyPilot · Open source · MIT License</p>
      </footer>
    </div>
  );
}
