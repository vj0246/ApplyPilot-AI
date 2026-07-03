"use client";
import { useCallback } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { useAuthStore } from "@/store/auth";
import { api } from "@/lib/api";

export function useAuth() {
  const router = useRouter();
  const { user, token, setAuth, clearAuth } = useAuthStore();

  const login = useCallback(async (email: string, password: string) => {
    const { data } = await api.post("/auth/login", { email, password });
    setAuth(data.user, data.access_token);
    router.push("/dashboard");
  }, [router, setAuth]);

  const register = useCallback(async (email: string, password: string, full_name: string) => {
    const { data } = await api.post("/auth/register", { email, password, full_name });
    setAuth(data.user, data.access_token);
    router.push("/onboarding");
  }, [router, setAuth]);

  const logout = useCallback(() => {
    clearAuth();
    router.push("/auth/login");
    toast.success("Signed out");
  }, [router, clearAuth]);

  return { user, token, isAuthenticated: !!user, login, register, logout };
}
