import Link from "next/link";
import { Zap } from "lucide-react";

export const metadata = { title: "Privacy Policy · ApplyPilot" };

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-white">
      <header className="border-b border-gray-100">
        <div className="max-w-3xl mx-auto px-6 h-16 flex items-center gap-2">
          <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <Link href="/" className="font-bold text-gray-900">ApplyPilot</Link>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-12 prose prose-sm prose-gray">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Privacy Policy</h1>
        <p className="text-gray-400 text-sm mb-8">Last updated: {new Date().toISOString().slice(0, 10)}</p>

        <div className="space-y-8 text-gray-700 leading-relaxed">
          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">What this is</h2>
            <p>
              ApplyPilot is a job application assistant. You upload your resume, answer a short
              interview about your background, optionally connect an email account, and the tool
              helps you fill job application forms and write application emails. This page explains
              what data it collects, why, and how it is protected.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">What is collected</h2>
            <ul className="list-disc pl-5 space-y-1.5">
              <li>Your account email address and a hashed password, never the plain password.</li>
              <li>The resume file and text you upload, and the structured profile extracted from it (name, contact details, education, skills, experience, projects).</li>
              <li>Answers you give to the background interview, stored as a structured profile of your values, strengths, and goals.</li>
              <li>Job descriptions you paste in, and the applications, cover letters, and emails generated from them.</li>
              <li>If you connect an email account: either an app password (encrypted at rest) or a Gmail OAuth refresh token (also encrypted at rest). Neither is ever stored in plain text.</li>
              <li>Corrections you make to a filled form's answers, so the same correction can be reused on a future form.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">How your Google Account information is used</h2>
            <p>
              If you connect Gmail, ApplyPilot requests exactly one Google permission:{" "}
              <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded">gmail.send</code>. This
              lets the application send an email as you, with your resume attached, only when you
              press Send on a draft you have reviewed. ApplyPilot never reads your inbox, never
              reads or sends anything you have not explicitly drafted and approved, and never
              accesses any other Google data. You can revoke this access at any time from your
              Google Account permissions page or by disconnecting Gmail in ApplyPilot's settings.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Who else sees your data</h2>
            <p>
              Resume text, job descriptions, and your background answers are sent to Groq, the AI
              provider used to generate cover letters, emails, and form answers, solely to generate
              that output. If you fill a Google Form or Microsoft Form, that form's own provider
              sees whatever answers you choose to submit, the same as if you had typed them in
              yourself. ApplyPilot does not sell data, does not use it for advertising, and does not
              share it with any other third party.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Human in the loop, always</h2>
            <p>
              ApplyPilot never submits a form and never sends an email on its own. Every filled
              form stops before submit for you to review; every email is a draft you can edit until
              you explicitly press send.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Data retention and deletion</h2>
            <p>
              Your data is kept for as long as your account exists. To delete your account and
              everything associated with it, contact the address below.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Contact</h2>
            <p>
              Questions about this policy or a request to delete your data: reach out through the{" "}
              <a
                href="https://github.com/vj0246/ApplyPilot-AI/issues"
                target="_blank" rel="noreferrer"
                className="text-indigo-600 underline"
              >
                project's GitHub issues
              </a>.
            </p>
          </section>
        </div>
      </main>

      <footer className="border-t border-gray-100 py-8 text-center text-gray-400 text-sm">
        <Link href="/" className="hover:text-gray-600">Back to ApplyPilot</Link>
      </footer>
    </div>
  );
}
