// Next.js App Router のルートレイアウト。
// すべてのページを包含する <html>/<body> 階層を 1 箇所だけここで定義する。
// Phase 0 はスタイル基盤も置かず、ブラウザ既定スタイルで描画する。

import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "kakeibo",
  description: "個人向け資産・家計管理アプリケーション（Phase 0 スタブ）",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: ReactNode;
}): JSX.Element {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
