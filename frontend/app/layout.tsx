import type { Metadata } from "next";
import type { ReactNode } from "react";

import "@fontsource-variable/hanken-grotesk";
import "@fontsource-variable/jetbrains-mono";

import { AppShell } from "../components/app-shell/app-shell";
import { Providers } from "../components/app-shell/providers";
import "./globals.css";
import "reactflow/dist/style.css";

export const metadata: Metadata = {
  title: "SpecPilot",
  description: "4ga Boards 手册驱动测试控制台",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
