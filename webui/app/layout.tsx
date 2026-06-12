import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "动态群 - 群控控制台",
  description: "陌陌群控：招呼通过 → 拉群",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" className="dark">
      <body className={`${inter.className} bg-black text-white antialiased`}>
        {children}
      </body>
    </html>
  );
}
