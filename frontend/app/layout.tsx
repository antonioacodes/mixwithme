import type { Metadata } from "next";
import "./style.css";
export const metadata: Metadata = {
  title: "MixWithMe — Seu laboratório de mix",
  description: "Análise local e transparente de mixagens TRAP.",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
