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
import { PosAdminSwitchButton } from "@/components/PosAdminSwitchButton";
import { useTranslations } from "next-intl";
import { useAtom, useSetAtom } from "jotai";
import { useEffect } from "react";
import {
  authReadyAtom,
  authTokenAtom,
  authUserAtom,
  clearAuthAtom,
} from "@/lib/atoms";
import { Link, usePathname, useRouter } from "@/i18n/navigation";

function adminNavItemActive(pathname: string | null, href: string): boolean {
  if (!pathname) return false;
  const path = pathname.replace(/\/$/, "") || "/";
  const target = href.replace(/\/$/, "") || "/";
  if (target === "/admin") {
    return path === "/admin";
  }
  return path === target || path.startsWith(`${target}/`);
}

function AdminNavButton({
  href,
  active,
  children,
}: {
  href: string;
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <Button
      component={Link}
      href={href}
      color={active ? "primary" : "inherit"}
      variant={active ? "contained" : "text"}
      disableElevation={active}
      size="small"
      aria-current={active ? "page" : undefined}
    >
      {children}
    </Button>
  );
}

export function AdminShell({ children }: { children: React.ReactNode }) {
  const t = useTranslations("admin");
  const [ready] = useAtom(authReadyAtom);
  const [token] = useAtom(authTokenAtom);
  const [user] = useAtom(authUserAtom);
  const clearAuth = useSetAtom(clearAuthAtom);
  const router = useRouter();
  const pathname = usePathname();

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
        <Toolbar variant="dense" sx={{ gap: 0.5, flexWrap: "wrap" }}>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            {t("title")}
          </Typography>
          <AdminNavButton href="/admin" active={adminNavItemActive(pathname, "/admin")}>
            {t("navHome")}
          </AdminNavButton>
          <AdminNavButton
            href="/admin/products"
            active={adminNavItemActive(pathname, "/admin/products")}
          >
            {t("navProducts")}
          </AdminNavButton>
          <AdminNavButton
            href="/admin/inventory"
            active={adminNavItemActive(pathname, "/admin/inventory")}
          >
            {t("navInventory")}
          </AdminNavButton>
          <AdminNavButton
            href="/admin/cuentas-corrientes"
            active={adminNavItemActive(pathname, "/admin/cuentas-corrientes")}
          >
            {t("navCreditAccounts")}
          </AdminNavButton>
          <AdminNavButton
            href="/admin/printer"
            active={adminNavItemActive(pathname, "/admin/printer")}
          >
            {t("navPrinter")}
          </AdminNavButton>
          <PosAdminSwitchButton target="pos" title={t("openPos")} sx={{ ml: 0.5 }} />
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
