"use client";
import { create } from "zustand";
import type { UserOut } from "./types";
import { setToken, getToken, authApi } from "./api";

interface AuthState {
  user: UserOut | null;
  loading: boolean;
  setUser: (u: UserOut | null) => void;
  logout: () => void;
  bootstrap: () => Promise<void>;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  loading: true,
  setUser: (u) => set({ user: u }),
  logout: () => {
    setToken(null);
    set({ user: null });
  },
  bootstrap: async () => {
    const token = getToken();
    if (!token) {
      set({ user: null, loading: false });
      return;
    }
    try {
      const user = await authApi.me();
      set({ user, loading: false });
    } catch {
      setToken(null);
      set({ user: null, loading: false });
    }
  },
}));
