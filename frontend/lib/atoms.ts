import { atom } from "jotai";

export type AuthUser = {
  id: number;
  email: string;
  is_active: boolean;
  is_staff: boolean;
};

export const authTokenAtom = atom<string | null>(null);

/** True after session token is read from sessionStorage (client). */
export const authReadyAtom = atom(false);

export const authUserAtom = atom<AuthUser | null>(null);

export const clearAuthAtom = atom(null, (_get, set) => {
  set(authTokenAtom, null);
  set(authUserAtom, null);
  if (typeof window !== "undefined") {
    try {
      sessionStorage.removeItem("abasto_token");
    } catch {
      /* ignore */
    }
  }
});
