import type { Metadata } from "next";
import { getMessages, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { Providers } from "@/components/Providers";
import { routing } from "@/i18n/routing";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const messages = (await import(`@/messages/${locale}.json`)).default as {
    meta: { title: string };
  };
  return { title: messages.meta.title };
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!routing.locales.includes(locale as "en" | "es")) {
    notFound();
  }
  setRequestLocale(locale);
  const messages = await getMessages();

  return (
    <Providers locale={locale} messages={messages as Record<string, unknown>}>
      {children}
    </Providers>
  );
}
