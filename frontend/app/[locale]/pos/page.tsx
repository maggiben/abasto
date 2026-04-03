"use client";

import { Box, CircularProgress } from "@mui/material";
import { useAtom } from "jotai";
import { useEffect } from "react";
import { PosTerminal } from "@/components/PosTerminal";
import { authReadyAtom, authTokenAtom } from "@/lib/atoms";
import { useRouter } from "@/i18n/navigation";

export default function PosPage() {
  const [ready] = useAtom(authReadyAtom);
  const [token] = useAtom(authTokenAtom);
  const router = useRouter();

  useEffect(() => {
    if (!ready) return;
    if (!token) router.replace("/login?redirect=/pos");
  }, [ready, token, router]);

  if (!ready || !token) {
    return (
      <Box sx={{ p: 4, display: "flex", justifyContent: "center" }}>
        <CircularProgress />
      </Box>
    );
  }
  return <PosTerminal />;
}
