// Phase 0 のダッシュボード placeholder。
// docs/design/04-deployment-stack.md §3 「Caddy 経由で UI に到達できる」
// DoD2 を満たすため、200 を返す最小ページを用意する。
// 実装本体は Phase 3 で React コンポーネント群に置換する。

export default function HomePage(): JSX.Element {
  return (
    <main>
      <h1>kakeibo</h1>
      <p>
        Phase 0 placeholder dashboard. UI components are scheduled for Phase 3.
      </p>
    </main>
  );
}
