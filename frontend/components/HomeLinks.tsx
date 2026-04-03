"use client";

import { Box, Button, Stack, Typography } from "@mui/material";
import { useLocale, useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/navigation";

export function HomeLinks() {
  const t = useTranslations("home");
  const locale = useLocale();
  const pathname = usePathname();
  const other = locale === "en" ? "es" : "en";
  return (
    <Box sx={{ p: 4, maxWidth: 560 }}>
      <Typography variant="h4" component="h1" gutterBottom>
        {t("title")}
      </Typography>
      <Typography color="text.secondary" paragraph>
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
  );
}
