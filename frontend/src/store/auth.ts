import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "@/types";

interface AuthState {
  user: User | null;
  token: string | null;
  setAuth: (user: User, token: string) => void;
  clearAuth: () => void;
  setUser: (user: User) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      setAuth: (user, token) => {
        if (typeof window !== "undefined") {
          sessionStorage.setItem("ap_token", token);
        }
        set({ user, token });
      },
      clearAuth: () => {
        if (typeof window !== "undefined") {
          sessionStorage.removeItem("ap_token");
        }
        set({ user: null, token: null });
      },
      setUser: (user) => set({ user }),
    }),
    {
      name: "ap-auth",
      partialize: (s) => ({ user: s.user }),
    }
  )
);
