"use client";

import { ThemeProvider, CssBaseline, createTheme } from "@mui/material";
import { NextIntlClientProvider } from "next-intl";
import { Provider as JotaiProvider } from "jotai";
import { useAtom, useSetAtom } from "jotai";
import { useEffect, useState } from "react";
import { authReadyAtom, authTokenAtom, authUserAtom } from "@/lib/atoms";
import { apiFetch } from "@/lib/api";
import type { UserPublic } from "@/lib/types";

const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: "#1565c0" },
  },
  typography: {
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
  },
});

const TOKEN_KEY = "abasto_token";

function AuthHydrate() {
  const [token, setToken] = useAtom(authTokenAtom);
  const setUser = useSetAtom(authUserAtom);
  const setReady = useSetAtom(authReadyAtom);
  const [restored, setRestored] = useState(false);

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(TOKEN_KEY);
      if (raw) setToken(raw);
    } catch {
      /* ignore */
    }
    queueMicrotask(() => {
      setRestored(true);
      setReady(true);
    });
  }, [setToken, setReady]);

  useEffect(() => {
    if (!restored) return;
    try {
      if (token) sessionStorage.setItem(TOKEN_KEY, token);
      else sessionStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
  }, [token, restored]);

  useEffect(() => {
    if (!restored) return;
    if (!token) {
      setUser(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const me = await apiFetch<UserPublic>("/auth/me", { token });
        if (!cancelled) setUser(me);
      } catch {
        if (!cancelled) {
          setUser(null);
          setToken(null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, restored, setUser, setToken]);

  return null;
}

export function Providers({
  children,
  locale,
  messages,
}: {
  children: React.ReactNode;
  locale: string;
  messages: Record<string, unknown>;
}) {
  return (
    <NextIntlClientProvider locale={locale} messages={messages} timeZone="UTC">
      <JotaiProvider>
        <ThemeProvider theme={theme}>
          <CssBaseline />
          <AuthHydrate />
          {children}
        </ThemeProvider>
      </JotaiProvider>
    </NextIntlClientProvider>
  );
}
