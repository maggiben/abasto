"use client";

import { Box, type BoxProps } from "@mui/material";
import Image from "next/image";
import { useTranslations } from "next-intl";

export type AbastoLogoProps = Omit<BoxProps, "children">;

const LOGO_SIZE = 1024;

export function AbastoLogo({ sx, component = "div", ...rest }: AbastoLogoProps) {
  const t = useTranslations("meta");
  return (
    <Box
      component={component}
      sx={{
        display: "inline-block",
        lineHeight: 0,
        verticalAlign: "middle",
        "& img": {
          display: "block",
          width: "clamp(120px, 28vw, 200px)",
          height: "auto",
        },
        ...sx,
      }}
      {...rest}
    >
      <Image
        src="/logo.webp"
        alt={t("title")}
        width={LOGO_SIZE}
        height={LOGO_SIZE}
        sizes="(max-width: 600px) 28vw, 200px"
        priority
      />
    </Box>
  );
}
