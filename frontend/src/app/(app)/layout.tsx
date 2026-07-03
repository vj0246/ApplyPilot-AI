"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Sidebar } from "@/components/layout/Sidebar";
import { useAuthStore } from "@/store/auth";
import { authApi, profileApi } from "@/lib/api";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { user, setUser, clearAuth } = useAuthStore();

  useEffect(() => {
    const token = typeof window !== "undefined" ? sessionStorage.getItem("ap_token") : null;
    if (!token) {
      router.push("/auth/login");
      return;
    }
    if (!user) {
      authApi.me()
        .then(({ data }) => setUser(data))
        .catch(() => {
          clearAuth();
          router.push("/auth/login");
        });
    }
  }, [user, router, setUser, clearAuth]);

  // Send anyone who has not finished the resume, knowledge graph, email
  // wizard back to it, so the AI always has a real profile to work from
  // before someone reaches the dashboard.
  const { data: profile } = useQuery({
    queryKey: ["profile"],
    queryFn: () => profileApi.get().then(r => r.data),
    enabled: !!user,
  });

  useEffect(() => {
    if (profile && !profile.onboarding_done) {
      router.push("/onboarding");
    }
  }, [profile, router]);

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar />
      <main className="flex-1 min-w-0">{children}</main>
    </div>
  );
}
