"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  AreaSeries,
  CandlestickSeries,
  ColorType,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { api } from "@/lib/api";
import { ensureMonotonicTimes, useMarket } from "@/lib/market";
import { cn } from "@/lib/cn";
import type { OhlcBar } from "@/lib/types";

export type ChartMode = "line" | "candle";

function monotonicBarTimes(bars: OhlcBar[]): OhlcBar[] {
  if (bars.length <= 1) return bars;
  const adjusted = ensureMonotonicTimes(
    bars.map((b) => ({ time: b.t, value: b.c })),
  );
  return bars.map((b, i) => ({ ...b, t: adjusted[i]!.time }));
}

function ChartModeToggle({
  mode,
  onChange,
  className,
}: {
  mode: ChartMode;
  onChange: (m: ChartMode) => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "inline-flex rounded border border-line/60 bg-base/40 p-0.5 font-mono text-[9px] uppercase tracking-wider",
        className,
      )}
    >
      {(["line", "candle"] as const).map((m) => (
        <button
          key={m}
          type="button"
          onClick={() => onChange(m)}
          className={cn(
            "rounded px-2 py-0.5 transition-colors",
            mode === m
              ? "bg-gold/20 text-gold"
              : "text-dim hover:text-muted",
          )}
        >
          {m === "line" ? "Line" : "Candles"}
        </button>
      ))}
    </div>
  );
}

export function PriceChart({
  modelId,
  mode: modeProp,
  onModeChange,
  showToggle = true,
  toggleClassName,
  barInterval = 60,
  barLimit = 60,
}: {
  modelId: string;
  mode?: ChartMode;
  onModeChange?: (m: ChartMode) => void;
  showToggle?: boolean;
  toggleClassName?: string;
  barInterval?: number;
  barLimit?: number;
}) {
  const { history, open, modelMap } = useMarket();
  const [modeInternal, setModeInternal] = useState<ChartMode>("line");
  const mode = modeProp ?? modeInternal;
  const setMode = onModeChange ?? setModeInternal;
  const [bars, setBars] = useState<OhlcBar[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const areaRef = useRef<ISeriesApi<"Area"> | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const fairLineRef = useRef<ReturnType<ISeriesApi<"Area">["createPriceLine"]> | null>(
    null,
  );

  const points = history[modelId] ?? [];
  const model = modelMap[modelId];
  const openPrice = open[modelId] ?? model?.session_open;
  const fundamental = model?.fundamental;

  useEffect(() => {
    if (mode !== "candle") return;
    let cancelled = false;
    api
      .getModelBars(modelId, barInterval, barLimit)
      .then((rows) => {
        if (!cancelled) setBars(rows);
      })
      .catch(() => {
        if (!cancelled) setBars([]);
      });
    return () => {
      cancelled = true;
    };
  }, [modelId, mode, barInterval, barLimit]);

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

    const area = chart.addSeries(AreaSeries, {
      lineColor: "#e8b339",
      topColor: "rgba(232,179,57,0.22)",
      bottomColor: "rgba(232,179,57,0)",
      lineWidth: 2,
      priceLineStyle: LineStyle.Dotted,
      priceLineColor: "#5a626d",
      lastValueVisible: true,
      visible: mode === "line",
    });

    const candles = chart.addSeries(CandlestickSeries, {
      upColor: "#3dd68c",
      downColor: "#ff5c66",
      borderVisible: false,
      wickUpColor: "#3dd68c",
      wickDownColor: "#ff5c66",
      visible: mode === "candle",
    });

    chartRef.current = chart;
    areaRef.current = area;
    candleRef.current = candles;

    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      chart.resize(width, height);
    });
    ro.observe(el);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      areaRef.current = null;
      candleRef.current = null;
    };
  }, [modelId]);

  useEffect(() => {
    areaRef.current?.applyOptions({ visible: mode === "line" });
    candleRef.current?.applyOptions({ visible: mode === "candle" });
  }, [mode]);

  useEffect(() => {
    const series = areaRef.current;
    const chart = chartRef.current;
    if (!series || !chart || mode !== "line" || points.length === 0) return;

    const last = points[points.length - 1].value;
    const up = openPrice == null ? true : last >= openPrice;
    const accent = up ? "#3dd68c" : "#ff5c66";
    series.applyOptions({
      lineColor: accent,
      topColor: up ? "rgba(61,214,140,0.22)" : "rgba(255,92,102,0.22)",
      bottomColor: "rgba(0,0,0,0)",
    });

    const chartPoints = ensureMonotonicTimes(points);
    series.setData(
      chartPoints.map((p) => ({ time: p.time as UTCTimestamp, value: p.value })),
    );
    if (fairLineRef.current) {
      series.removePriceLine(fairLineRef.current);
      fairLineRef.current = null;
    }
    if (fundamental != null && points.length > 0) {
      fairLineRef.current = series.createPriceLine({
        price: fundamental,
        color: "#5a626d",
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: "Fair",
      });
    }
    chart.timeScale().fitContent();
  }, [points, openPrice, fundamental, mode]);

  useEffect(() => {
    const series = candleRef.current;
    const chart = chartRef.current;
    if (!series || !chart || mode !== "candle" || bars.length === 0) return;

    const ordered = monotonicBarTimes(bars);
    series.setData(
      ordered.map((b) => ({
        time: b.t as UTCTimestamp,
        open: b.o,
        high: b.h,
        low: b.l,
        close: b.c,
      })),
    );
    chart.timeScale().fitContent();
  }, [bars, mode]);

  return (
    <div className="relative flex h-full w-full flex-col">
      {showToggle && (
        <div className="absolute right-1 top-1 z-10">
          <ChartModeToggle
            mode={mode}
            onChange={setMode}
            className={toggleClassName}
          />
        </div>
      )}
      <div ref={containerRef} className="h-full w-full flex-1" />
    </div>
  );
}

export { ChartModeToggle };
