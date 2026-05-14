"use client";

import { AbastoLogo } from "@/components/AbastoLogo";
import { Box, Button, Stack, Typography } from "@mui/material";
import { useLocale, useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/navigation";

export function HomeLinks() {
  const t = useTranslations("home");
  const locale = useLocale();
  const pathname = usePathname();
  const other = locale === "en" ? "es" : "en";
  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        boxSizing: "border-box",
        p: 2,
      }}
    >
      <Box sx={{ width: "100%", maxWidth: 560, textAlign: "center" }}>
        <AbastoLogo component="h1" sx={{ mb: 1 }} />
        <Typography color="text.secondary" paragraph sx={{ mb: 0 }}>
          {t("hint")}
        </Typography>
        <Stack spacing={2} sx={{ mt: 3 }}>
          <Button component={Link} href="/pos" variant="contained" size="large" fullWidth>
            {t("pos")}
          </Button>
          <Button component={Link} href="/admin" variant="outlined" size="large" fullWidth>
            {t("admin")}
          </Button>
        </Stack>
        <Typography variant="body2" sx={{ mt: 3 }} color="text.secondary">
          <Link href={pathname ?? "/"} locale={other}>
            {other === "es" ? "Español" : "English"}
          </Link>
        </Typography>
      </Box>
    </Box>
  );
}
