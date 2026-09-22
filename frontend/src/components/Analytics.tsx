import React, { useState, useEffect, useRef } from "react";
import { Loader2, Receipt, TrendingUp, DollarSign, Store } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { FilterDropdown } from "./FilterDropdown";
import { CATEGORIES, CATEGORY_COLORS } from "../utils/categories";

// ─── Currency helpers ─────────────────────────────────────────────────────────
const SYMBOLS: Record<string, string> = {
  USD: "$", INR: "₹", EUR: "€", GBP: "£", CAD: "C$",
  AUD: "A$", JPY: "¥", CHF: "Fr", CNY: "¥", SGD: "S$",
  HKD: "HK$", NZD: "NZ$", SEK: "kr", NOK: "kr", DKK: "kr",
};
function sym(code: string | null): string {
  if (!code) return "";
  return SYMBOLS[code] ?? code + " ";
}
function fmtAmt(val: number, code: string | null): string {
  return `${sym(code)}${val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
function fmtAmtCompact(val: number, code: string | null): string {
  const s = sym(code);
  if (val >= 1_000_000) return `${s}${(val / 1_000_000).toFixed(1)}M`;
  if (val >= 1_000) return `${s}${(val / 1_000).toFixed(0)}K`;
  return `${s}${val.toFixed(0)}`;
}

// ─── Dynamic Y-axis "nice scale" algorithm ────────────────────────────────────
function calcNiceScale(monthlyAmounts: number[]): { yAxisMax: number; tickStep: number; ticks: number[] } {
  const maxValue = Math.max(...monthlyAmounts);
  if (maxValue === 0) return { yAxisMax: 0, tickStep: 0, ticks: [] };

  const targetMax = maxValue * 1.10;
  const rawStep = targetMax / 5;
  const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const normalized = rawStep / magnitude;

  let niceNormalized: number;
  if (normalized <= 1) niceNormalized = 1;
  else if (normalized <= 2) niceNormalized = 2;
  else if (normalized <= 5) niceNormalized = 5;
  else niceNormalized = 10;

  const tickStep = niceNormalized * magnitude;
  const yAxisMax = Math.ceil(targetMax / tickStep) * tickStep;

  const ticks: number[] = [];
  for (let t = 0; t <= yAxisMax; t += tickStep) {
    ticks.push(Math.round(t * 1000) / 1000); // avoid floating-point drift
  }
  return { yAxisMax, tickStep, ticks };
}

// ─── Types ────────────────────────────────────────────────────────────────────
interface CategoryBreakdown {
  category: string;
  amount: number;
}

interface MonthlyTrendItem {
  month: string;
  month_number: number;
  amount: number;
}

interface YearlyTrendItem {
  year: number;
  amount: number;
}

interface AnalyticsData {
  total_spending: number;
  receipt_count: number;
  average_receipt: number;
  largest_expense: number;
  largest_expense_merchant: string | null;
  category_breakdown: CategoryBreakdown[];
  table_breakdown: { category: string; transaction_count: number; total: number; percentage: number }[];
  monthly_trend: MonthlyTrendItem[];
  yearly_trend: YearlyTrendItem[];
}

// ─── Monthly Trend SVG Chart ──────────────────────────────────────────────────
const CHART_SHORT_MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

const MonthlyTrendChart: React.FC<{
  trend: MonthlyTrendItem[];
  currency: string | null;
  loading: boolean;
}> = ({ trend, currency, loading }) => {
  const [tooltip, setTooltip] = useState<{ x: number; y: number; month: string; amount: number } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const W = 460;
  const H = 200;
  const padL = 52;
  const padR = 16;
  const padT = 14;
  const padB = 32;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  if (loading) {
    return (
      <div className="w-full h-[220px] flex items-center justify-center">
        <div className="flex flex-col items-center gap-2">
          <Loader2 className="w-6 h-6 text-[#0D7C66] animate-spin" />
          <p className="text-[#171A3A]/40 text-xs">Loading trend…</p>
        </div>
      </div>
    );
  }

  const amounts = trend.map(t => t.amount);
  const { yAxisMax, ticks } = calcNiceScale(amounts);
  const allZero = yAxisMax === 0;

  if (allZero) {
    return (
      <div className="w-full h-[220px] flex items-center justify-center bg-[#171A3A]/[0.03] rounded-xl border border-dashed border-[#171A3A]/10">
        <p className="text-[#171A3A]/40 text-sm">No spending data for this year.</p>
      </div>
    );
  }

  // Guard: if trend data hasn't loaded yet (< 12 points), show loading
  if (trend.length < 12) {
    return (
      <div className="w-full h-[220px] flex items-center justify-center">
        <div className="flex flex-col items-center gap-2">
          <Loader2 className="w-6 h-6 text-[#0D7C66] animate-spin" />
          <p className="text-[#171A3A]/40 text-xs">Loading trend…</p>
        </div>
      </div>
    );
  }

  // Map data points to SVG coordinates
  const toX = (i: number) => padL + (i / 11) * plotW;
  const toY = (amt: number) => padT + plotH - (amt / yAxisMax) * plotH;

  const points = trend.map((t, i) => ({ x: toX(i), y: toY(t.amount), ...t }));
  const last = points[points.length - 1];
  const first = points[0];

  // Build polyline path
  const polyline = points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(" ");
  // Build filled area path
  const areaPath = `${polyline} L${last.x.toFixed(2)},${(padT + plotH).toFixed(2)} L${first.x.toFixed(2)},${(padT + plotH).toFixed(2)} Z`;

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    const svgX = ((e.clientX - rect.left) / rect.width) * W;
    const relX = svgX - padL;
    const idx = Math.max(0, Math.min(11, Math.round((relX / plotW) * 11)));
    const p = points[idx];
    setTooltip({ x: p.x, y: p.y, month: trend[idx].month, amount: trend[idx].amount });
  };

  return (
    <div className="relative w-full">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setTooltip(null)}
      >
        <defs>
          <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0D7C66" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#0D7C66" stopOpacity="0" />
          </linearGradient>
          <clipPath id="chartClip">
            <rect x={padL} y={padT} width={plotW} height={plotH} />
          </clipPath>
        </defs>

        {/* Y-axis grid lines + labels */}
        {ticks.map(tick => {
          const y = toY(tick);
          return (
            <g key={tick}>
              <line
                x1={padL} y1={y} x2={padL + plotW} y2={y}
                stroke="#171A3A" strokeOpacity="0.06" strokeWidth="1" strokeDasharray="3,3"
              />
              <text x={padL - 6} y={y + 4} textAnchor="end" fontSize="9" fill="#171A3A" fillOpacity="0.45">
                {fmtAmtCompact(tick, currency)}
              </text>
            </g>
          );
        })}

        {/* Area fill */}
        <path d={areaPath} fill="url(#trendGradient)" clipPath="url(#chartClip)" />

        {/* Line */}
        <path
          d={polyline}
          fill="none"
          stroke="#0D7C66"
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
          clipPath="url(#chartClip)"
        />

        {/* Data points */}
        {points.map((p, i) => (
          <circle
            key={i}
            cx={p.x}
            cy={p.y}
            r={tooltip?.month === trend[i].month ? 4.5 : 2.5}
            fill={tooltip?.month === trend[i].month ? "#0D7C66" : "#fff"}
            stroke="#0D7C66"
            strokeWidth={tooltip?.month === trend[i].month ? 2 : 1.5}
            style={{ transition: "r 0.1s" }}
          />
        ))}

        {/* X-axis labels */}
        {points.map((p, i) => (
          <text key={i} x={p.x} y={H - padB + 14} textAnchor="middle" fontSize="9" fill="#171A3A" fillOpacity="0.5">
            {CHART_SHORT_MONTHS[i]}
          </text>
        ))}

        {/* Tooltip vertical line */}
        {tooltip && (
          <line
            x1={tooltip.x} y1={padT} x2={tooltip.x} y2={padT + plotH}
            stroke="#0D7C66" strokeOpacity="0.3" strokeWidth="1" strokeDasharray="3,2"
          />
        )}
      </svg>

      {/* Floating tooltip */}
      {tooltip && (() => {
        const pct = tooltip.x / W;
        const alignRight = pct > 0.65;
        return (
          <div
            className="absolute pointer-events-none bg-[#171A3A] text-white rounded-lg px-2.5 py-1.5 text-xs shadow-lg z-10"
            style={{
              top: `${(tooltip.y / H) * 100}%`,
              left: alignRight ? undefined : `${(tooltip.x / W) * 100}%`,
              right: alignRight ? `${((W - tooltip.x) / W) * 100}%` : undefined,
              transform: "translateY(-110%)",
            }}
          >
            <p className="font-bold">{tooltip.month}</p>
            <p className="text-[#0D7C66] font-extrabold">{fmtAmt(tooltip.amount, currency)}</p>
          </div>
        );
      })()}
    </div>
  );
};

// ─── Yearly Trend SVG Chart ───────────────────────────────────────────────────
const YearlyTrendChart: React.FC<{
  trend: YearlyTrendItem[];
  currency: string | null;
  loading: boolean;
}> = ({ trend, currency, loading }) => {
  const [tooltip, setTooltip] = useState<{ x: number; y: number; year: number; amount: number } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const W = 460;
  const H = 200;
  const padL = 52;
  const padR = 16;
  const padT = 14;
  const padB = 32;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  if (loading) {
    return (
      <div className="w-full h-[220px] flex items-center justify-center">
        <div className="flex flex-col items-center gap-2">
          <Loader2 className="w-6 h-6 text-[#0D7C66] animate-spin" />
          <p className="text-[#171A3A]/40 text-xs">Loading trend…</p>
        </div>
      </div>
    );
  }

  if (trend.length === 0) {
    return (
      <div className="w-full h-[220px] flex items-center justify-center bg-[#171A3A]/[0.03] rounded-xl border border-dashed border-[#171A3A]/10">
        <p className="text-[#171A3A]/40 text-sm">No spending data available.</p>
      </div>
    );
  }

  const amounts = trend.map(t => t.amount);
  const { yAxisMax, ticks } = calcNiceScale(amounts);

  if (yAxisMax === 0) {
    return (
      <div className="w-full h-[220px] flex items-center justify-center bg-[#171A3A]/[0.03] rounded-xl border border-dashed border-[#171A3A]/10">
        <p className="text-[#171A3A]/40 text-sm">No spending data available.</p>
      </div>
    );
  }

  const n = trend.length;
  const toX = (i: number) => n === 1 ? padL + plotW / 2 : padL + (i / (n - 1)) * plotW;
  const toY = (amt: number) => padT + plotH - (amt / yAxisMax) * plotH;

  const points = trend.map((t, i) => ({ x: toX(i), y: toY(t.amount), year: t.year, amount: t.amount }));
  const last = points[points.length - 1];
  const first = points[0];

  const polyline = points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(" ");
  const areaPath = n > 1
    ? `${polyline} L${last.x.toFixed(2)},${(padT + plotH).toFixed(2)} L${first.x.toFixed(2)},${(padT + plotH).toFixed(2)} Z`
    : "";

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    const svgX = ((e.clientX - rect.left) / rect.width) * W;
    const relX = svgX - padL;
    const idx = Math.max(0, Math.min(n - 1, Math.round((relX / plotW) * (n - 1))));
    const p = points[idx];
    setTooltip({ x: p.x, y: p.y, year: trend[idx].year, amount: trend[idx].amount });
  };

  return (
    <div className="relative w-full">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setTooltip(null)}
      >
        <defs>
          <linearGradient id="yearlyGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0D7C66" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#0D7C66" stopOpacity="0" />
          </linearGradient>
          <clipPath id="yearlyClip">
            <rect x={padL} y={padT} width={plotW} height={plotH} />
          </clipPath>
        </defs>

        {/* Y-axis grid lines + labels */}
        {ticks.map(tick => {
          const y = toY(tick);
          return (
            <g key={tick}>
              <line x1={padL} y1={y} x2={padL + plotW} y2={y} stroke="#171A3A" strokeOpacity="0.06" strokeWidth="1" strokeDasharray="3,3" />
              <text x={padL - 6} y={y + 4} textAnchor="end" fontSize="9" fill="#171A3A" fillOpacity="0.45">
                {fmtAmtCompact(tick, currency)}
              </text>
            </g>
          );
        })}

        {/* Area fill */}
        {areaPath && <path d={areaPath} fill="url(#yearlyGradient)" clipPath="url(#yearlyClip)" />}

        {/* Line */}
        <path d={polyline} fill="none" stroke="#0D7C66" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" clipPath="url(#yearlyClip)" />

        {/* Data points */}
        {points.map((p, i) => (
          <circle
            key={i}
            cx={p.x} cy={p.y}
            r={tooltip?.year === trend[i].year ? 4.5 : 2.5}
            fill={tooltip?.year === trend[i].year ? "#0D7C66" : "#fff"}
            stroke="#0D7C66"
            strokeWidth={tooltip?.year === trend[i].year ? 2 : 1.5}
            style={{ transition: "r 0.1s" }}
          />
        ))}

        {/* X-axis labels */}
        {points.map((p, i) => (
          <text key={i} x={p.x} y={H - padB + 14} textAnchor="middle" fontSize="9" fill="#171A3A" fillOpacity="0.5">
            {trend[i].year}
          </text>
        ))}

        {/* Tooltip vertical line */}
        {tooltip && (
          <line x1={tooltip.x} y1={padT} x2={tooltip.x} y2={padT + plotH} stroke="#0D7C66" strokeOpacity="0.3" strokeWidth="1" strokeDasharray="3,2" />
        )}
      </svg>

      {/* Floating tooltip */}
      {tooltip && (() => {
        const pct = tooltip.x / W;
        const alignRight = pct > 0.65;
        return (
          <div
            className="absolute pointer-events-none bg-[#171A3A] text-white rounded-lg px-2.5 py-1.5 text-xs shadow-lg z-10"
            style={{
              top: `${(tooltip.y / H) * 100}%`,
              left: alignRight ? undefined : `${(tooltip.x / W) * 100}%`,
              right: alignRight ? `${((W - tooltip.x) / W) * 100}%` : undefined,
              transform: "translateY(-110%)",
            }}
          >
            <p className="font-bold">{tooltip.year}</p>
            <p className="text-[#0D7C66] font-extrabold">{fmtAmt(tooltip.amount, currency)}</p>
          </div>
        );
      })()}
    </div>
  );
};

// ─── Main Analytics Component ─────────────────────────────────────────────────
export const Analytics: React.FC = () => {
  const { session } = useAuth();

  const [initLoading, setInitLoading] = useState(true);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Global filter state
  const [availableYears, setAvailableYears] = useState<string[]>([]);
  const [availableCurrencies, setAvailableCurrencies] = useState<string[]>([]);
  const [activeYear, setActiveYear] = useState<string | null>(null);
  const [activeMonth, setActiveMonth] = useState<string | null>(null);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [displayCurrency, setDisplayCurrency] = useState<string | null>(null);

  // ── Local trend-chart state (independent from global filters) ──────────────
  const [trendYear, setTrendYear] = useState<string | null>(null);
  const [trendCurrency, setTrendCurrency] = useState<string | null>(null);
  const [trendLoading, setTrendLoading] = useState(false);
  const [trendData, setTrendData] = useState<MonthlyTrendItem[]>([]);

  // ── Local yearly trend state (independent from everything else) ───────────
  const [yearlyTrendCurrency, setYearlyTrendCurrency] = useState<string | null>(null);
  const [yearlyTrendLoading, setYearlyTrendLoading] = useState(false);
  const [yearlyTrendData, setYearlyTrendData] = useState<YearlyTrendItem[]>([]);

  // Shared analytics data (KPIs, chart, table)
  const [data, setData] = useState<AnalyticsData | null>(null);

  const months = ["January","February","March","April","May","June","July","August","September","October","November","December"];

  // ── 1. Initialise: extract available years & currencies from receipts ───────
  useEffect(() => {
    const fetchMetadata = async () => {
      try {
        const headers: Record<string, string> = {};
        if (session?.access_token) headers["Authorization"] = `Bearer ${session.access_token}`;

        const res = await fetch(`${import.meta.env.VITE_API_URL || ""}/api/receipts`, { headers });
        if (!res.ok) throw new Error("Failed to load analytics metadata");
        const receipts: any[] = await res.json();

        const years = new Set<string>();
        const currencies = new Set<string>();

        receipts.forEach(r => {
          if (r.purchase_date) {
            const d = new Date(r.purchase_date);
            if (!isNaN(d.getTime())) years.add(d.getFullYear().toString());
          }
          if (r.currency) currencies.add(r.currency);
        });

        const sortedYears = Array.from(years).sort((a, b) => parseInt(b) - parseInt(a));
        const sortedCurr = Array.from(currencies).sort();

        const currentYearStr = new Date().getFullYear().toString();

        // Pick best default year
        let defaultYear = currentYearStr;
        if (sortedYears.length > 0) {
          if (sortedYears.includes(currentYearStr)) {
            defaultYear = currentYearStr;
          } else {
            let closest = sortedYears[0];
            let minDiff = Math.abs(parseInt(closest) - parseInt(currentYearStr));
            for (const y of sortedYears) {
              const diff = Math.abs(parseInt(y) - parseInt(currentYearStr));
              if (diff < minDiff) { minDiff = diff; closest = y; }
            }
            defaultYear = closest;
          }
        } else {
          sortedYears.push(currentYearStr);
        }

        setAvailableYears(sortedYears);
        setAvailableCurrencies(sortedCurr);
        setActiveYear(defaultYear);

        const defaultCurr = sortedCurr.length > 0 ? sortedCurr[0] : null;
        if (defaultCurr) setDisplayCurrency(defaultCurr);

        // Trend chart also starts with the same default year & currency (independently)
        setTrendYear(defaultYear);
        setTrendCurrency(defaultCurr);
        setYearlyTrendCurrency(defaultCurr);
      } catch (err: any) {
        console.error(err);
      } finally {
        setInitLoading(false);
      }
    };
    fetchMetadata();
  }, [session]);

  // ── 2. Fetch global KPI / chart / table analytics ─────────────────────────
  useEffect(() => {
    if (initLoading) return;
    const fetchAnalytics = async () => {
      setAnalyticsLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        if (activeYear) params.append("year", activeYear);
        if (activeMonth) params.append("month", activeMonth);
        if (activeCategory) params.append("category", activeCategory);
        if (displayCurrency) params.append("currency", displayCurrency);

        const headers: Record<string, string> = {};
        if (session?.access_token) headers["Authorization"] = `Bearer ${session.access_token}`;

        const res = await fetch(`${import.meta.env.VITE_API_URL || ""}/api/analytics?${params.toString()}`, { headers });
        if (!res.ok) throw new Error("Failed to load analytics data");
        const json: AnalyticsData = await res.json();
        setData(json);
      } catch (err: any) {
        setError(err.message || "An unknown error occurred.");
      } finally {
        setAnalyticsLoading(false);
      }
    };
    fetchAnalytics();
  }, [activeYear, activeMonth, activeCategory, displayCurrency, initLoading, session]);

  // ── 3. Fetch trend data independently (only reacts to trendYear/trendCurrency) ─
  useEffect(() => {
    if (initLoading || trendYear === null) return;
    const fetchTrend = async () => {
      setTrendLoading(true);
      try {
        const params = new URLSearchParams();
        params.append("trend_year", trendYear);
        if (trendCurrency) params.append("trend_currency", trendCurrency);

        const headers: Record<string, string> = {};
        if (session?.access_token) headers["Authorization"] = `Bearer ${session.access_token}`;

        const res = await fetch(`${import.meta.env.VITE_API_URL || ""}/api/analytics?${params.toString()}`, { headers });
        if (!res.ok) throw new Error("Failed to load trend data");
        const json: AnalyticsData = await res.json();
        setTrendData(json.monthly_trend);
      } catch (err: any) {
        console.error(err);
      } finally {
        setTrendLoading(false);
      }
    };
    fetchTrend();
  }, [trendYear, trendCurrency, initLoading, session]);

  // ── 4. Fetch yearly trend data independently ───────────────────────────────
  useEffect(() => {
    if (initLoading) return;
    const fetchYearlyTrend = async () => {
      setYearlyTrendLoading(true);
      try {
        const params = new URLSearchParams();
        if (yearlyTrendCurrency) params.append("yearly_trend_currency", yearlyTrendCurrency);

        const headers: Record<string, string> = {};
        if (session?.access_token) headers["Authorization"] = `Bearer ${session.access_token}`;

        const res = await fetch(`${import.meta.env.VITE_API_URL || ""}/api/analytics?${params.toString()}`, { headers });
        if (!res.ok) throw new Error("Failed to load yearly trend data");
        const json: AnalyticsData = await res.json();
        setYearlyTrendData(json.yearly_trend);
      } catch (err: any) {
        console.error(err);
      } finally {
        setYearlyTrendLoading(false);
      }
    };
    fetchYearlyTrend();
  }, [yearlyTrendCurrency, initLoading, session]);

  const clearAllFilters = () => {
    setActiveYear(null);
    setActiveMonth(null);
    setActiveCategory(null);
    if (availableCurrencies.length > 0) setDisplayCurrency(availableCurrencies[0]);
  };

  if (initLoading) {
    return (
      <div className="w-full h-64 flex flex-col items-center justify-center pt-24">
        <Loader2 className="w-8 h-8 text-[#0D7C66] animate-spin mb-4" />
        <p className="text-white/60 font-support">Loading analytics…</p>
      </div>
    );
  }

  const filtersActive = activeYear !== null || activeMonth !== null || activeCategory !== null;

  return (
    <div className="w-full max-w-5xl mx-auto px-4 sm:px-6 pt-12 pb-20 animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* ── Header ── */}
      <div className="mb-8">
        <h1 className="text-3xl font-extrabold text-white tracking-tight">Analytics</h1>
        <p className="text-white/70 font-support text-sm mt-1">Understand your spending at a glance.</p>
      </div>

      {/* ── Global Filter Bar ── */}
      <div className="flex items-center gap-2 w-full flex-wrap mb-10">
        <FilterDropdown
          label="Year"
          options={availableYears.map(y => ({ label: y, value: y }))}
          value={activeYear}
          onChange={setActiveYear}
          onClear={() => setActiveYear(null)}
        />
        <FilterDropdown
          label="Month"
          options={months.map((m, i) => ({ label: m, value: i.toString() }))}
          value={activeMonth}
          onChange={setActiveMonth}
          onClear={() => setActiveMonth(null)}
        />
        <FilterDropdown
          label="Category"
          options={CATEGORIES.map(c => ({ label: c, value: c }))}
          value={activeCategory}
          onChange={setActiveCategory}
          onClear={() => setActiveCategory(null)}
        />
        {availableCurrencies.length > 0 && (
          <FilterDropdown
            label="Currency"
            options={availableCurrencies.map(c => ({ label: c, value: c }))}
            value={displayCurrency}
            onChange={setDisplayCurrency}
            onClear={() => {}}
          />
        )}
        {filtersActive && (
          <button
            onClick={clearAllFilters}
            className="shrink-0 px-4 py-2 rounded-full text-sm font-bold whitespace-nowrap transition-all flex items-center gap-1.5 border bg-white/5 text-white/70 border-white/10 hover:bg-white/10 hover:text-white"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* ── Error State ── */}
      {error && (
        <div className="w-full bg-rose-500/10 border border-rose-500/30 rounded-2xl p-6 text-center mb-8">
          <p className="text-rose-400 font-semibold mb-3">{error}</p>
          <button
            onClick={() => { setInitLoading(true); setTimeout(() => setInitLoading(false), 10); }}
            className="px-4 py-2 bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 rounded-lg text-sm font-semibold transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {/* ── KPI Cards Grid ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">

        {/* Total Spending */}
        <div className="bg-[#F5F3EA] rounded-2xl p-4 border border-[#171A3A]/10 shadow-sm relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-3 opacity-10 group-hover:opacity-20 transition-opacity">
            <DollarSign className="w-12 h-12 text-[#0D7C66]" />
          </div>
          <p className="text-[#171A3A]/60 font-semibold text-xs tracking-wider uppercase mb-1 relative z-10">Total Spending</p>
          <div className="relative z-10">
            {analyticsLoading ? (
              <div className="h-6 w-32 bg-slate-200 animate-pulse rounded mb-1"></div>
            ) : (
              <h3 className="text-2xl font-extrabold text-[#171A3A] mb-0.5">{fmtAmt(data?.total_spending || 0, displayCurrency)}</h3>
            )}
            <p className="text-xs font-support text-[#171A3A]/60">
              {analyticsLoading ? <div className="h-3 w-24 bg-slate-200 animate-pulse rounded inline-block"></div> : `Across ${data?.receipt_count || 0} receipts`}
            </p>
          </div>
        </div>

        {/* Receipt Count */}
        <div className="bg-[#F5F3EA] rounded-2xl p-4 border border-[#171A3A]/10 shadow-sm relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-3 opacity-10 group-hover:opacity-20 transition-opacity">
            <Receipt className="w-12 h-12 text-[#171A3A]" />
          </div>
          <p className="text-[#171A3A]/60 font-semibold text-xs tracking-wider uppercase mb-1 relative z-10">Receipts</p>
          <div className="relative z-10">
            {analyticsLoading ? (
              <div className="h-6 w-16 bg-slate-200 animate-pulse rounded mb-1"></div>
            ) : (
              <h3 className="text-2xl font-extrabold text-[#171A3A] mb-0.5">{data?.receipt_count || 0}</h3>
            )}
            <p className="text-xs font-support text-[#171A3A]/60">
              {analyticsLoading ? <div className="h-3 w-24 bg-slate-200 animate-pulse rounded inline-block"></div> : "Total logged"}
            </p>
          </div>
        </div>

        {/* Average Receipt */}
        <div className="bg-[#F5F3EA] rounded-2xl p-4 border border-[#171A3A]/10 shadow-sm relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-3 opacity-10 group-hover:opacity-20 transition-opacity">
            <TrendingUp className="w-12 h-12 text-[#171A3A]" />
          </div>
          <p className="text-[#171A3A]/60 font-semibold text-xs tracking-wider uppercase mb-1 relative z-10">Average Receipt</p>
          <div className="relative z-10">
            {analyticsLoading ? (
              <div className="h-6 w-24 bg-slate-200 animate-pulse rounded mb-1"></div>
            ) : (
              <h3 className="text-2xl font-extrabold text-[#171A3A] mb-0.5">{fmtAmt(data?.average_receipt || 0, displayCurrency)}</h3>
            )}
            <p className="text-xs font-support text-[#171A3A]/60">
              {analyticsLoading ? <div className="h-3 w-24 bg-slate-200 animate-pulse rounded inline-block"></div> : "Per receipt"}
            </p>
          </div>
        </div>

        {/* Largest Expense */}
        <div className="bg-[#F5F3EA] rounded-2xl p-4 border border-[#171A3A]/10 shadow-sm relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-3 opacity-5 group-hover:opacity-10 transition-opacity">
            <Store className="w-12 h-12 text-[#0D7C66]" />
          </div>
          <p className="text-[#171A3A]/60 font-semibold text-xs tracking-wider uppercase mb-1 relative z-10">Largest Expense</p>
          <div className="relative z-10">
            {analyticsLoading ? (
              <div className="h-6 w-32 bg-slate-200 animate-pulse rounded mb-1"></div>
            ) : (
              <h3 className="text-2xl font-extrabold text-[#0D7C66] mb-0.5">{fmtAmt(data?.largest_expense || 0, displayCurrency)}</h3>
            )}
            <p className="text-xs font-bold text-[#171A3A]/80 truncate">
              {analyticsLoading ? <div className="h-3 w-32 bg-slate-200 animate-pulse rounded inline-block"></div> : (data?.largest_expense_merchant || "N/A")}
            </p>
          </div>
        </div>

      </div>

      {/* ── Empty State (global) ── */}
      {!analyticsLoading && !error && data && data.receipt_count === 0 && (
        <div className="mt-6 bg-white/5 border border-white/10 rounded-2xl p-4 text-center">
          <p className="text-white/50 text-sm font-support">No receipts match the selected filters.</p>
        </div>
      )}

      {/* ── Row 1: Category Chart + Breakdown Table ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">

        {/* Spending by Category (bar chart) */}
        <div className="bg-[#F5F3EA] rounded-2xl p-4 border border-[#171A3A]/10 shadow-sm flex flex-col">
          <div className="mb-4 shrink-0">
            <h2 className="text-lg font-bold text-[#171A3A]">Spending by Category</h2>
            <p className="text-[#171A3A]/60 text-xs font-support mt-0.5">
              {[
                activeYear || "All Years",
                activeMonth !== null ? months[parseInt(activeMonth)] : "All Months",
                displayCurrency || ""
              ].filter(Boolean).join(" • ")}
            </p>
          </div>

          <div className="flex-1 flex flex-col gap-1.5">
            {analyticsLoading ? (
              Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="flex flex-col gap-1.5">
                  <div className="flex justify-between text-sm">
                    <div className="w-24 h-4 bg-slate-200 animate-pulse rounded"></div>
                    <div className="w-16 h-4 bg-slate-200 animate-pulse rounded"></div>
                  </div>
                  <div className="w-full h-2 bg-slate-200 animate-pulse rounded-full"></div>
                </div>
              ))
            ) : data?.category_breakdown ? (
              (() => {
                const maxAmount = Math.max(...data.category_breakdown.map(c => c.amount));
                return data.category_breakdown.map((item) => {
                  const percentage = maxAmount > 0 ? (item.amount / maxAmount) * 100 : 0;
                  const colorClass = CATEGORY_COLORS[item.category] || CATEGORY_COLORS["Other"];
                  const hexColor = colorClass.match(/#([0-9A-Fa-f]{6})/)?.[0] || "#0D7C66";
                  return (
                    <div key={item.category} className="flex flex-col gap-1 group">
                      <div className="flex justify-between text-[11px] items-end">
                        <span className="font-semibold text-[#171A3A]/80">{item.category}</span>
                        <span className="font-bold text-[#171A3A]">{fmtAmt(item.amount, displayCurrency)}</span>
                      </div>
                      <div className="w-full h-1.5 bg-[#171A3A]/5 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-1000 ease-out"
                          style={{ width: `${percentage}%`, backgroundColor: hexColor }}
                        />
                      </div>
                    </div>
                  );
                });
              })()
            ) : null}
          </div>
        </div>

        {/* Category Breakdown Table */}
        <div className="bg-[#F5F3EA] rounded-2xl p-4 border border-[#171A3A]/10 shadow-sm flex flex-col">
          <div className="mb-4 shrink-0">
            <h2 className="text-lg font-bold text-[#171A3A]">Category Breakdown</h2>
            <p className="text-[#171A3A]/60 text-xs font-support mt-0.5">See your spending by category.</p>
          </div>

          <div className="flex-1 overflow-x-auto">
            {analyticsLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-8 bg-slate-200 animate-pulse rounded w-full"></div>)}
              </div>
            ) : data?.table_breakdown && data.table_breakdown.length > 0 ? (
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="border-b border-[#171A3A]/10 text-[#171A3A]/60 font-semibold text-[10px] uppercase tracking-wider">
                    <th className="pb-2 pl-2">Category</th>
                    <th className="pb-2 text-right">Txns</th>
                    <th className="pb-2 text-right">Total</th>
                    <th className="pb-2 text-right pr-2">%</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#171A3A]/5">
                  {data.table_breakdown.map(row => {
                    const colorClass = CATEGORY_COLORS[row.category] || CATEGORY_COLORS["Other"];
                    const hexColor = colorClass.match(/#([0-9A-Fa-f]{6})/)?.[0] || "#171A3A";
                    return (
                      <tr key={row.category} className="group hover:bg-[#171A3A]/[0.02] transition-colors">
                        <td className="py-2 pl-2 font-medium" style={{ color: hexColor }}>{row.category}</td>
                        <td className="py-2 text-right text-[#171A3A]/80">{row.transaction_count}</td>
                        <td className="py-2 text-right font-bold text-[#171A3A]">{fmtAmt(row.total, displayCurrency)}</td>
                        <td className="py-2 text-right font-semibold text-[#171A3A]/60 pr-2">{row.percentage.toFixed(1)}%</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <div className="flex items-center justify-center h-32 bg-[#171A3A]/5 rounded-xl border border-dashed border-[#171A3A]/10">
                <p className="text-[#171A3A]/40 text-sm font-support">No spending data for the selected filters.</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Section Divider: Spending Trends ── */}
      <div className="mt-8 mb-4">
        <h2 className="text-[20px] font-bold text-white tracking-tight">Spending Trends</h2>
        <p className="text-white/50 text-[13px] font-support mt-1">See how your spending changes over time across months and years.</p>
        <div className="mt-3 border-t border-white/10" />
      </div>

      {/* ── Row 2: Monthly Spending Trend (left) + Yearly Trend placeholder (right) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">

        {/* Monthly Spending Trend */}
        <div className="bg-[#F5F3EA] rounded-2xl p-4 border border-[#171A3A]/10 shadow-sm flex flex-col min-h-[300px]">
          {/* Card header: title + local filters */}
          <div className="flex items-start justify-between gap-2 mb-4 shrink-0">
            <div>
              <h2 className="text-lg font-bold text-[#171A3A]">Monthly Spending Trend</h2>
              <p className="text-[#171A3A]/60 text-xs font-support mt-0.5">Track how your spending changes throughout the year.</p>
            </div>
            {/* Local filters — completely independent from global filters */}
            <div className="flex items-center gap-1.5 shrink-0 mt-0.5">
              <select
                value={trendYear || ""}
                onChange={e => setTrendYear(e.target.value)}
                className="text-xs font-semibold text-[#171A3A] bg-[#171A3A]/[0.06] hover:bg-[#171A3A]/[0.1] border border-[#171A3A]/10 rounded-lg px-2 py-1 cursor-pointer outline-none transition-colors"
              >
                {availableYears.map(y => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
              {availableCurrencies.length > 0 && (
                <select
                  value={trendCurrency || ""}
                  onChange={e => setTrendCurrency(e.target.value)}
                  className="text-xs font-semibold text-[#171A3A] bg-[#171A3A]/[0.06] hover:bg-[#171A3A]/[0.1] border border-[#171A3A]/10 rounded-lg px-2 py-1 cursor-pointer outline-none transition-colors"
                >
                  {availableCurrencies.map(c => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              )}
            </div>
          </div>

          {/* Chart area */}
          <div className="flex-1">
            <MonthlyTrendChart
              trend={trendData}
              currency={trendCurrency}
              loading={trendLoading}
            />
          </div>
        </div>

        {/* Yearly Spending Trend */}
        <div className="bg-[#F5F3EA] rounded-2xl p-4 border border-[#171A3A]/10 shadow-sm flex flex-col min-h-[300px]">
          <div className="flex items-start justify-between gap-2 mb-4 shrink-0">
            <div>
              <h2 className="text-lg font-bold text-[#171A3A]">Yearly Spending Trend</h2>
              <p className="text-[#171A3A]/60 text-xs font-support mt-0.5">Track how your spending changes across years.</p>
            </div>
            {availableCurrencies.length > 0 && (
              <div className="flex items-center gap-1.5 shrink-0 mt-0.5">
                <select
                  value={yearlyTrendCurrency || ""}
                  onChange={e => setYearlyTrendCurrency(e.target.value)}
                  className="text-xs font-semibold text-[#171A3A] bg-[#171A3A]/[0.06] hover:bg-[#171A3A]/[0.1] border border-[#171A3A]/10 rounded-lg px-2 py-1 cursor-pointer outline-none transition-colors"
                >
                  {availableCurrencies.map(c => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>
            )}
          </div>

          <div className="flex-1">
            <YearlyTrendChart
              trend={yearlyTrendData}
              currency={yearlyTrendCurrency}
              loading={yearlyTrendLoading}
            />
          </div>
        </div>

      </div>

    </div>
  );
};
