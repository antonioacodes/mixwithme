import { Session } from "./types";
export function RoutingGraph({ session }: { session: Session }) {
  const groups = [
    session.channels.filter(
      (c) => !["bus", "return", "master"].includes(c.kind),
    ),
    session.channels.filter((c) => c.kind === "bus" || c.kind === "return"),
    session.channels.filter((c) => c.kind === "master"),
  ];
  const height = Math.max(200, ...groups.map((g) => g.length * 65 + 30));
  const positions = Object.fromEntries(
    groups.flatMap((g, col) =>
      g.map((c, i) => [c.id, { x: 20 + col * 270, y: 25 + i * 65 }]),
    ),
  );
  return (
    <div style={{ overflow: "auto", marginBottom: 20 }}>
      <svg
        style={{ width: "100%", minWidth: 600 }}
        viewBox={`0 0 760 ${height}`}
        role="img"
        aria-label="Grafo dos canais, buses, retornos e master. Linhas tracejadas representam sends."
      >
        <defs>
          <marker
            id="arrow"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="5"
            markerHeight="5"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#91b86c" />
          </marker>
        </defs>
        {session.routes.map((r, i) => {
          const a = positions[r.source],
            b = positions[r.target];
          if (!a || !b) return null;
          return (
            <path
              key={i}
              d={`M ${a.x + 175} ${a.y + 18} C ${a.x + 225} ${a.y + 18},${b.x - 50} ${b.y + 18},${b.x - 5} ${b.y + 18}`}
              stroke="#91b86c"
              strokeWidth="1.4"
              fill="none"
              strokeDasharray={r.kind === "send" ? "5 4" : undefined}
              markerEnd="url(#arrow)"
            />
          );
        })}
        {session.channels.map((c) => {
          const p = positions[c.id];
          return (
            <g key={c.id}>
              <rect
                x={p.x}
                y={p.y}
                width="175"
                height="36"
                rx="5"
                fill="#263221"
                stroke="#4e6440"
              />
              <text x={p.x + 10} y={p.y + 23} fill="#dbe8ce" fontSize="11">
                {c.name.length > 23 ? c.name.slice(0, 22) + "…" : c.name}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
