"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  AreaSeries,
  ColorType,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { useMarket } from "@/lib/market";

export function PriceChart({ modelId }: { modelId: string }) {
  const { history, open } = useMarket();
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);

  const points = history[modelId] ?? [];
  const openPrice = open[modelId];

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const chart = createChart(el, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#5a626d",
        fontFamily: "var(--font-plex-mono), monospace",
        fontSize: 10,
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: "rgba(30,35,43,0.6)" },
        horzLines: { color: "rgba(30,35,43,0.6)" },
      },
      rightPriceScale: { borderColor: "#1e232b" },
      timeScale: {
        borderColor: "#1e232b",
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        vertLine: { color: "#2a3038", labelBackgroundColor: "#161a20" },
        horzLine: { color: "#2a3038", labelBackgroundColor: "#161a20" },
      },
      handleScale: false,
      handleScroll: false,
    });

    const series = chart.addSeries(AreaSeries, {
      lineColor: "#e8b339",
      topColor: "rgba(232,179,57,0.22)",
      bottomColor: "rgba(232,179,57,0)",
      lineWidth: 2,
      priceLineStyle: LineStyle.Dotted,
      priceLineColor: "#5a626d",
      lastValueVisible: true,
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      chart.resize(width, height);
    });
    ro.observe(el);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [modelId]);

  // Update data + recolor based on session direction.
  useEffect(() => {
    const series = seriesRef.current;
    const chart = chartRef.current;
    if (!series || !chart || points.length === 0) return;

    const last = points[points.length - 1].value;
    const up = openPrice == null ? true : last >= openPrice;
    const accent = up ? "#3dd68c" : "#ff5c66";
    series.applyOptions({
      lineColor: accent,
      topColor: up ? "rgba(61,214,140,0.22)" : "rgba(255,92,102,0.22)",
      bottomColor: "rgba(0,0,0,0)",
    });

    series.setData(
      points.map((p) => ({ time: p.time as UTCTimestamp, value: p.value })),
    );
    chart.timeScale().fitContent();
  }, [points, openPrice]);

  return <div ref={containerRef} className="h-full w-full" />;
}
