// Next.js 14 設定。
//
// 設計判断:
// - `output: "standalone"` は runtime ステージで .next/standalone のみ
//   コピーすればよく、本番イメージを最小化できる（api/Dockerfile の
//   マルチステージ思想と整合）。Next.js 公式が推奨する Docker 配信パターン。
// - `reactStrictMode: true` で開発時の二重実行による副作用バグを早期検出する。
// - Phase 0 ではビジネスロジックを UI に持ち込まないため、experimental
//   フラグや i18n 設定は意図的に入れない（DRY: 必要になってから足す）。

/** @type {import("next").NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
};

export default nextConfig;
