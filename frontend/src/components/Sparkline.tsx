"use client";

import { useId } from "react";

export function Sparkline({
  data,
  width = 88,
  height = 26,
  positive,
}: {
  data: number[];
  width?: number;
  height?: number;
  positive?: boolean;
}) {
  const gid = useId();
  if (!data || data.length < 2) {
    return (
      <svg width={width} height={height} className="opacity-30">
        <line
          x1={0}
          y1={height / 2}
          x2={width}
          y2={height / 2}
          stroke="currentColor"
          strokeWidth={1}
          className="text-faint"
        />
      </svg>
    );
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const pad = 2;
  const n = data.length;

  const x = (i: number) => (i / (n - 1)) * (width - pad * 2) + pad;
  const y = (v: number) =>
    height - pad - ((v - min) / range) * (height - pad * 2);

  const up = positive ?? data[n - 1] >= data[0];
  const color = up ? "var(--color-up)" : "var(--color-down)";

  const line = data.map((v, i) => `${x(i).toFixed(2)},${y(v).toFixed(2)}`).join(" ");
  const area =
    `${pad},${height - pad} ` +
    data.map((v, i) => `${x(i).toFixed(2)},${y(v).toFixed(2)}`).join(" ") +
    ` ${width - pad},${height - pad}`;

  return (
    <svg width={width} height={height} className="block overflow-visible">
      <defs>
        <linearGradient id={`spark-${gid}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.28} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <polygon points={area} fill={`url(#spark-${gid})`} />
      <polyline
        points={line}
        fill="none"
        stroke={color}
        strokeWidth={1.25}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
