import Link from "next/link";
import {
  Zap, FileText, Mail, Link2, MessageSquare, Brain,
  ArrowRight, Upload, ClipboardPaste, CheckCircle2, ShieldCheck,
} from "lucide-react";

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
      <section className="max-w-6xl mx-auto px-6 pt-20 pb-12 text-center">
        <h1 className="text-5xl font-bold text-gray-900 leading-tight mb-5 max-w-3xl mx-auto">
          Paste a job form link.{" "}
          <span className="text-indigo-600">Get it filled in seconds.</span>
        </h1>
        <p className="text-xl text-gray-500 max-w-2xl mx-auto mb-8 leading-relaxed">
          ApplyPilot reads your resume once, then fills Google and Microsoft application
          forms and drafts tailored application emails — sent from your own address,
          resume attached. You review everything before it goes anywhere.
        </p>
        <div className="flex items-center justify-center gap-3 flex-wrap">
          <Link href="/auth/register" className="btn-primary px-6 py-3 text-base">
            Start for free <ArrowRight className="w-4 h-4" />
          </Link>
          <Link href="/auth/login" className="btn-secondary px-6 py-3 text-base">
            Sign in
          </Link>
        </div>
        <p className="text-gray-400 text-sm mt-4">Free · No credit card · Nothing sent without your OK</p>
      </section>

      {/* Metrics strip */}
      <section className="max-w-5xl mx-auto px-6 pb-16">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { v: "~60 sec", d: "to fill a form that takes 20 minutes by hand" },
            { v: "1 paste", d: "Quick Apply reads the link and recipient from one message" },
            { v: "1 upload", d: "your resume powers every application after that" },
            { v: "100%", d: "human reviewed — nothing is ever auto submitted" },
          ].map((m) => (
            <div key={m.d} className="card p-5 text-center">
              <div className="text-2xl font-bold text-indigo-600 mb-1">{m.v}</div>
              <div className="text-gray-500 text-sm leading-snug">{m.d}</div>
            </div>
          ))}
        </div>
      </section>

      {/* What you give / what you get */}
      <section className="bg-gray-50 py-16">
        <div className="max-w-5xl mx-auto px-6">
          <h2 className="text-2xl font-bold text-gray-900 text-center mb-12">
            What you give, what you get
          </h2>
          <div className="grid md:grid-cols-2 gap-6">
            <div className="card p-6 bg-white">
              <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <Upload className="w-4 h-4 text-indigo-600" /> You give
              </h3>
              <ul className="space-y-3 text-sm text-gray-600">
                <li className="flex gap-2"><CheckCircle2 className="w-4 h-4 text-indigo-500 shrink-0 mt-0.5" />Your resume, once — PDF, DOCX, or plain text</li>
                <li className="flex gap-2"><CheckCircle2 className="w-4 h-4 text-indigo-500 shrink-0 mt-0.5" />A Google or Microsoft form link, or a recipient email</li>
                <li className="flex gap-2"><CheckCircle2 className="w-4 h-4 text-indigo-500 shrink-0 mt-0.5" />Optionally: eight short questions about you, so answers sound like you and not a template</li>
              </ul>
            </div>
            <div className="card p-6 bg-white">
              <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <Zap className="w-4 h-4 text-indigo-600" /> You get
              </h3>
              <ul className="space-y-3 text-sm text-gray-600">
                <li className="flex gap-2"><CheckCircle2 className="w-4 h-4 text-green-500 shrink-0 mt-0.5" />A pre-filled form link with every answer editable before you submit</li>
                <li className="flex gap-2"><CheckCircle2 className="w-4 h-4 text-green-500 shrink-0 mt-0.5" />A tailored application email, grounded in your real projects and experience, with your resume attached</li>
                <li className="flex gap-2"><CheckCircle2 className="w-4 h-4 text-green-500 shrink-0 mt-0.5" />Answers that improve every run — your corrections are remembered and reused</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Capabilities */}
      <section className="max-w-6xl mx-auto px-6 py-16">
        <h2 className="text-2xl font-bold text-gray-900 text-center mb-12">
          What it can do
        </h2>
        <div className="grid md:grid-cols-2 gap-6">
          {[
            {
              icon: Link2, title: "Form autofill",
              desc: "Paste a Google or Microsoft Forms link. Every question is answered from your resume and profile, and you get back a pre-filled link — edit anything, then submit it yourself.",
              color: "text-blue-600", bg: "bg-blue-50",
            },
            {
              icon: Mail, title: "Application email",
              desc: "A structured, specific email written against the exact job description — your projects, your matched skills, honest about gaps. Sent from your own address, resume always attached.",
              color: "text-purple-600", bg: "bg-purple-50",
            },
            {
              icon: MessageSquare, title: "Quick Apply",
              desc: "Paste a whole job message in one go. ApplyPilot finds the form link and the recipient email inside it, fills the form, and drafts the email in one pass.",
              color: "text-green-600", bg: "bg-green-50",
            },
            {
              icon: Brain, title: "Memory that learns",
              desc: "Every answer you correct is remembered and preferred next time. A short interview builds a knowledge graph of who you are, so nothing reads like a generic template.",
              color: "text-orange-600", bg: "bg-orange-50",
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
              { icon: Upload, t: "Upload your resume", d: "Skills, projects, experience, education, and links are extracted automatically." },
              { icon: ClipboardPaste, t: "Paste a form link or a job message", d: "ApplyPilot fills the form and drafts the email against that exact job." },
              { icon: ShieldCheck, t: "Review, edit, send", d: "You see every answer and every line before anything is submitted or sent. Always." },
            ].map((s, i) => (
              <div key={s.t} className="flex items-start gap-5 card p-5 bg-white">
                <div className="w-9 h-9 bg-indigo-600 rounded-full flex items-center justify-center text-white font-bold text-sm shrink-0">
                  {i + 1}
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
        <h2 className="text-3xl font-bold text-gray-900 mb-4">
          Spend your time interviewing, not filling forms.
        </h2>
        <p className="text-gray-500 mb-8">Free, open source, set up in two minutes.</p>
        <Link href="/auth/register" className="btn-primary px-8 py-3 text-base">
          Create free account <ArrowRight className="w-4 h-4" />
        </Link>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-100 py-8 text-center text-gray-400 text-sm">
        <p>© {new Date().getFullYear()} ApplyPilot · Open source · MIT License</p>
        <p className="mt-2 flex items-center justify-center gap-4">
          <Link href="/privacy" className="hover:text-gray-600">Privacy Policy</Link>
          <Link href="/terms" className="hover:text-gray-600">Terms of Service</Link>
        </p>
      </footer>
    </div>
  );
}
