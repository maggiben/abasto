"use client";

import {
  AppBar,
  Box,
  Button,
  CircularProgress,
  Container,
  Toolbar,
  Typography,
} from "@mui/material";
import { useTranslations } from "next-intl";
import { useAtom, useSetAtom } from "jotai";
import { useEffect } from "react";
import {
  authReadyAtom,
  authTokenAtom,
  authUserAtom,
  clearAuthAtom,
} from "@/lib/atoms";
import { Link, useRouter } from "@/i18n/navigation";

export function AdminShell({ children }: { children: React.ReactNode }) {
  const t = useTranslations("admin");
  const [ready] = useAtom(authReadyAtom);
  const [token] = useAtom(authTokenAtom);
  const [user] = useAtom(authUserAtom);
  const clearAuth = useSetAtom(clearAuthAtom);
  const router = useRouter();

  useEffect(() => {
    if (!ready) return;
    if (!token) {
      router.replace("/login?redirect=/admin&staff=1");
      return;
    }
    if (user && !user.is_staff) {
      router.replace("/");
    }
  }, [ready, token, user, router]);

  if (!ready || !token || !user) {
    return (
      <Box sx={{ p: 4, display: "flex", justifyContent: "center" }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!user.is_staff) {
    return null;
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
      <AppBar position="static" color="default" elevation={1}>
        <Toolbar variant="dense">
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            {t("title")}
          </Typography>
          <Button
            color="inherit"
            component={Link}
            href="/admin"
            variant="text"
          >
            {t("navHome")}
          </Button>
          <Button
            color="inherit"
            component={Link}
            href="/admin/products"
            variant="text"
          >
            {t("navProducts")}
          </Button>
          <Button
            color="inherit"
            component={Link}
            href="/admin/inventory"
            variant="text"
          >
            {t("navInventory")}
          </Button>
          <Button color="inherit" onClick={() => clearAuth()}>
            {t("logout")}
          </Button>
        </Toolbar>
      </AppBar>
      <Container maxWidth="lg" sx={{ py: 3, flex: 1 }}>
        {children}
      </Container>
    </Box>
  );
}
