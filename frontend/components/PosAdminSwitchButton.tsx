"use client";

import AdminPanelSettingsIcon from "@mui/icons-material/AdminPanelSettings";
import PointOfSaleIcon from "@mui/icons-material/PointOfSale";
import { IconButton, Tooltip } from "@mui/material";
import type { SxProps, Theme } from "@mui/material/styles";
import { Link } from "@/i18n/navigation";

type Target = "admin" | "pos";

export function PosAdminSwitchButton({
  target,
  title,
  sx,
}: {
  target: Target;
  title: string;
  sx?: SxProps<Theme>;
}) {
  const href = target === "admin" ? "/admin" : "/pos";
  const Icon = target === "admin" ? AdminPanelSettingsIcon : PointOfSaleIcon;
  return (
    <Tooltip title={title}>
      <IconButton
        component={Link}
        href={href}
        color="inherit"
        aria-label={title}
        size="medium"
        sx={sx}
      >
        <Icon />
      </IconButton>
    </Tooltip>
  );
}
