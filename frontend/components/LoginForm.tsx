"use client";

import { Alert, Box, Button, Stack, TextField, Typography } from "@mui/material";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { useSearchParams } from "next/navigation";
import { useSetAtom } from "jotai";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { apiFetch, ApiError } from "@/lib/api";
import { authTokenAtom, authUserAtom } from "@/lib/atoms";
import type { TokenResponse, UserPublic } from "@/lib/types";

type Form = { email: string; password: string };

export function LoginForm() {
  const t = useTranslations("login");
  const router = useRouter();
  const params = useSearchParams();
  const redirect = params.get("redirect") ?? "/";
  const requireStaff = params.get("staff") === "1";
  const setToken = useSetAtom(authTokenAtom);
  const setUser = useSetAtom(authUserAtom);
  const [error, setError] = useState<string | null>(null);

  const { register, handleSubmit, formState } = useForm<Form>({
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = handleSubmit(async (data) => {
    setError(null);
    try {
      const tok = await apiFetch<TokenResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify(data),
      });
      setToken(tok.access_token);
      const me = await apiFetch<UserPublic>("/auth/me", { token: tok.access_token });
      if (requireStaff && !me.is_staff) {
        setToken(null);
        setUser(null);
        setError(t("staffRequired"));
        return;
      }
      setUser(me);
      router.replace(redirect);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("error"));
    }
  });

  return (
    <Box component="form" onSubmit={onSubmit} sx={{ p: 3, maxWidth: 400 }}>
      <Typography variant="h5" gutterBottom>
        {t("title")}
      </Typography>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      <Stack spacing={2}>
        <TextField
          label={t("email")}
          type="email"
          autoComplete="username"
          {...register("email", { required: true })}
        />
        <TextField
          label={t("password")}
          type="password"
          autoComplete="current-password"
          {...register("password", { required: true })}
        />
        <Button type="submit" variant="contained" disabled={formState.isSubmitting} fullWidth>
          {t("submit")}
        </Button>
      </Stack>
    </Box>
  );
}
