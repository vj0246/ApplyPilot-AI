import type { Metadata } from "next";
import { Toaster } from "react-hot-toast";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "ApplyPilot — Apply everywhere intelligently",
  description: "AI-powered job application assistant. Upload your resume once, apply everywhere.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          {children}
          <Toaster
            position="top-right"
            toastOptions={{
              style: { background: "#fff", color: "#111827", border: "1px solid #e5e7eb", fontSize: "14px" },
              success: { iconTheme: { primary: "#4f46e5", secondary: "#fff" } },
            }}
          />
        </Providers>
      </body>
    </html>
  );
}
