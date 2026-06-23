"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { useAuthStore } from "@/store/auth";
import { authApi } from "@/lib/api";

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

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar />
      <main className="flex-1 min-w-0">{children}</main>
    </div>
  );
}
