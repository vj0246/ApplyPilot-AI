import Link from "next/link";
import { Zap } from "lucide-react";

export const metadata = { title: "Terms of Service · ApplyPilot" };

export default function TermsPage() {
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
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Terms of Service</h1>
        <p className="text-gray-400 text-sm mb-8">Last updated: {new Date().toISOString().slice(0, 10)}</p>

        <div className="space-y-8 text-gray-700 leading-relaxed">
          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Using ApplyPilot</h2>
            <p>
              ApplyPilot helps you fill job application forms and write application emails using
              your own resume and background. It is provided as is, free of charge, without any
              warranty of accuracy, availability, or fitness for a particular purpose.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Your responsibility</h2>
            <p>
              Every form filled and every email drafted is a starting point, not a final submission.
              You are responsible for reviewing everything ApplyPilot generates before it goes out
              under your name. ApplyPilot never submits a form or sends an email without your
              explicit action.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Your account</h2>
            <p>
              You are responsible for the accuracy of the information you provide and for keeping
              your account credentials and any connected email account secure. Do not use ApplyPilot
              to submit false information on a job application.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Third party services</h2>
            <p>
              ApplyPilot relies on Groq for AI generation, and on Google Forms, Microsoft Forms, and
              Gmail for the features that interact with them. Your use of those features is also
              subject to those providers' own terms.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Changes</h2>
            <p>
              These terms may be updated as the product changes. Continued use after an update means
              you accept the revised terms.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Contact</h2>
            <p>
              Questions about these terms: reach out through the{" "}
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
