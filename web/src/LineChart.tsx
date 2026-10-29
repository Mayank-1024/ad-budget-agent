// A single-series line chart in plain SVG with a crosshair tooltip.
// One measure per chart (no dual axis): the dashboard shows spend and ROAS as two charts.
import { useState } from "react";

export interface Point {
  label: string; // x label (ISO day)
  value: number | null;
}

interface Props {
  title: string;
  points: Point[];
  format: (v: number) => string;
  height?: number;
}

const W = 520;
const PAD = { top: 12, right: 16, bottom: 26, left: 52 };

export function LineChart({ title, points, format, height = 180 }: Props) {
  const [hover, setHover] = useState<number | null>(null);
  const values = points.map((p) => p.value).filter((v): v is number => v !== null);
  const max = values.length ? Math.max(...values) * 1.1 : 1;
  const innerW = W - PAD.left - PAD.right;
  const innerH = height - PAD.top - PAD.bottom;
  const x = (i: number) => PAD.left + (points.length > 1 ? (i / (points.length - 1)) * innerW : 0);
  const y = (v: number) => PAD.top + innerH - (v / max) * innerH;
  const ticks = [0, max / 2, max];
  const path = points
    .map((p, i) => (p.value === null ? null : `${x(i)},${y(p.value)}`))
    .filter(Boolean)
    .join(" L");
  const h = hover !== null ? points[hover] : null;

  return (
    <figure className="chart">
      <figcaption>{title}</figcaption>
      <svg
        viewBox={`0 0 ${W} ${height}`}
        role="img"
        aria-label={title}
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const box = e.currentTarget.getBoundingClientRect();
          const px = ((e.clientX - box.left) / box.width) * W;
          const i = Math.round(((px - PAD.left) / innerW) * (points.length - 1));
          setHover(Math.min(points.length - 1, Math.max(0, i)));
        }}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line className="grid" x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} />
            <text className="tick" x={PAD.left - 6} y={y(t) + 4} textAnchor="end">
              {format(t)}
            </text>
          </g>
        ))}
        {points.length > 0 && (
          <>
            <text className="tick" x={x(0)} y={height - 6} textAnchor="start">
              {points[0].label.slice(5)}
            </text>
            <text className="tick" x={x(points.length - 1)} y={height - 6} textAnchor="end">
              {points[points.length - 1].label.slice(5)}
            </text>
          </>
        )}
        {path && <path className="series" d={`M${path}`} />}
        {hover !== null && h && (
          <g>
            <line className="crosshair" x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={PAD.top + innerH} />
            {h.value !== null && <circle className="marker" cx={x(hover)} cy={y(h.value)} r={4} />}
          </g>
        )}
      </svg>
      <div className="tooltip" aria-live="polite">
        {h ? `${h.label}: ${h.value === null ? "no data" : format(h.value)}` : "Hover the chart for daily values"}
      </div>
    </figure>
  );
}
