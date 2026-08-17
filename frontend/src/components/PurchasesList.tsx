import React, { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, FileText, ExternalLink, RefreshCw, X, ChevronDown } from "lucide-react";
import { useLocation } from "react-router-dom";

// ── Types ──────────────────────────────────────────────────────────────────
interface ReceiptItem {
  item_name: string;
  quantity: number | null;
  unit_price: number | null;
  total_price: number;
}

interface Receipt {
  id: string;
  merchant_name: string;
  purchase_date: string | null;
  document_type: string | null;
  currency: string | null;
  total_amount: number;
  tax: number | null;
  payment_method: string | null;
  due_date: string | null;
  warranty_period_days: number | null;
  cloudinary_public_id: string | null;
  cloudinary_resource_type: string | null;
  original_filename: string | null;
  items: ReceiptItem[];
}

interface ItemConverted {
  item_name: string;
  quantity: number | null;
  unit_price: number | null;
  total_price: number;
}

interface ReceiptConverted {
  id: string;
  total_amount: number;
  tax: number | null;
  items: ItemConverted[];
  rate_date: string | null;
  conversion_unavailable: boolean;
}

// ── Currency helpers ───────────────────────────────────────────────────────
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

// ── Component ──────────────────────────────────────────────────────────────
export const PurchasesList: React.FC = () => {
  const [receipts, setReceipts]               = useState<Receipt[]>([]);
  const [loading, setLoading]                 = useState(true);
  const [error, setError]                     = useState<string | null>(null);
  const [selectedReceipt, setSelectedReceipt] = useState<Receipt | null>(null);
  const [highlightedReceiptId, setHighlightedReceiptId] = useState<string | null>(null);
  const location                              = useLocation();

  // Conversion state
  const [displayCurrency, setDisplayCurrency] = useState<string | null>(null);
  const [convertedMap, setConvertedMap]       = useState<Record<string, ReceiptConverted>>({});
  const [convLoading, setConvLoading]         = useState(false);
  const [convError, setConvError]             = useState<string | null>(null);
  const lastConvertedFor                      = useRef<string | null>(null);

  // ── Fetch receipts ──────────────────────────────────────────────────────
  const fetchReceipts = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch("http://localhost:8000/api/receipts");
      if (!res.ok) throw new Error("Failed to fetch purchases data.");
      const data: Receipt[] = await res.json();
      setReceipts(data);
    } catch (err: any) {
      setError(err.message || "An unknown error occurred.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchReceipts(); }, []);

  // Auto-scroll to receipt from location state
  useEffect(() => {
    if (receipts.length > 0 && location.state?.selectedReceiptId) {
      const targetId = location.state.selectedReceiptId;
      setHighlightedReceiptId(targetId);
      
      // Scroll to the element instantly to jump directly to it
      setTimeout(() => {
        const el = document.getElementById(`receipt-${targetId}`);
        if (el) {
          el.scrollIntoView({ behavior: "auto", block: "start" });
        }
      }, 50);

      // Remove highlight after a few seconds
      const timer = setTimeout(() => {
        setHighlightedReceiptId(null);
      }, 3000);

      // Clear the state so it doesn't trigger again on re-renders
      window.history.replaceState({}, document.title);
      
      return () => clearTimeout(timer);
    }
  }, [receipts, location.state]);

  // ── Available currencies (only those present in saved receipts) ─────────
  const availableCurrencies = useMemo<string[]>(() => {
    const s = new Set<string>();
    receipts.forEach(r => { if (r.currency) s.add(r.currency); });
    return Array.from(s).sort();
  }, [receipts]);

  // Set initial display currency
  useEffect(() => {
    if (availableCurrencies.length > 0 && !displayCurrency) {
      setDisplayCurrency(availableCurrencies[0]);
    }
  }, [availableCurrencies]);

  // ── Server-side conversion ──────────────────────────────────────────────
  useEffect(() => {
    if (!displayCurrency || receipts.length === 0) return;
    const cacheKey = displayCurrency;
    if (lastConvertedFor.current === cacheKey) return; // already converted for this target

    const run = async () => {
      setConvLoading(true);
      setConvError(null);
      try {
        const payload = {
          target_currency: displayCurrency,
          receipts: receipts.map(r => ({
            id: r.id,
            currency: r.currency,
            total_amount: r.total_amount,
            tax: r.tax,
            purchase_date: r.purchase_date,
            items: r.items.map(it => ({
              item_name: it.item_name,
              quantity: it.quantity,
              unit_price: it.unit_price,
              total_price: it.total_price,
            })),
          })),
        };

        const res = await fetch("http://localhost:8000/api/convert-receipts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!res.ok) {
          const body = await res.json();
          throw new Error(body.detail ?? "Conversion failed.");
        }

        const data = await res.json();
        const map: Record<string, ReceiptConverted> = {};
        for (const r of data.results) map[r.id] = r;
        setConvertedMap(map);
        lastConvertedFor.current = cacheKey;
      } catch (err: any) {
        setConvError(err.message || "Could not convert currencies.");
      } finally {
        setConvLoading(false);
      }
    };

    run();
  }, [displayCurrency, receipts]);

  // When currency changes, reset cache key so conversion re-runs
  const handleCurrencyChange = (c: string) => {
    if (c !== displayCurrency) {
      lastConvertedFor.current = null;
      setDisplayCurrency(c);
    }
  };

  // ── Render helpers ──────────────────────────────────────────────────────
  const getConverted = (r: Receipt): ReceiptConverted | null => convertedMap[r.id] ?? null;

  if (loading) {
    return (
      <div className="w-full h-64 flex flex-col items-center justify-center">
        <Loader2 className="w-8 h-8 text-[#0D7C66] animate-spin mb-4" />
        <p className="text-white/60 font-support">Loading your purchases...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full max-w-3xl mx-auto mt-12 bg-white/5 rounded-2xl p-8 text-center border border-white/10">
        <p className="text-rose-400 font-semibold mb-4">{error}</p>
        <button
          onClick={fetchReceipts}
          className="flex items-center gap-2 mx-auto px-5 py-2.5 bg-white/10 border border-white/10 rounded-lg text-white hover:bg-white/20 transition-colors"
        >
          <RefreshCw className="w-4 h-4" /> Try Again
        </button>
      </div>
    );
  }

  return (
    <div className="w-full max-w-4xl mx-auto pt-10 pb-20 px-4 sm:px-6 animate-in fade-in slide-in-from-bottom-4 duration-500">

      {/* ── Page Header ── */}
      <div className="mb-6">
        <h1 className="text-3xl font-extrabold text-white tracking-tight">Purchases</h1>
        <p className="text-white/50 font-support text-sm mt-1">
          Detailed log of your verified receipts and expenses.
        </p>
      </div>

      {/* ── Currency Toolbar ── */}
      {availableCurrencies.length > 0 && (
        <div className="flex items-center gap-3 mb-8 flex-wrap">
          <span className="text-xs font-semibold text-white/40 uppercase tracking-widest">Display in</span>

          <div className="relative inline-flex items-center">
            <select
              id="display-currency-select"
              value={displayCurrency ?? ""}
              onChange={e => handleCurrencyChange(e.target.value)}
              className="appearance-none pl-3 pr-8 py-1.5 rounded-lg bg-white/10 border border-white/20 text-white text-sm font-semibold focus:outline-none focus:border-[#7A9B6D] transition-colors cursor-pointer"
            >
              {availableCurrencies.map(c => (
                <option key={c} value={c} className="bg-[#11152F]">{c}</option>
              ))}
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-white/40 absolute right-2 pointer-events-none" />
          </div>

          {convLoading && (
            <span className="flex items-center gap-1.5 text-xs text-white/40 font-support">
              <Loader2 className="w-3 h-3 animate-spin" /> Fetching rates…
            </span>
          )}
          {convError && (
            <span className="text-xs text-rose-400 font-support">⚠ {convError}</span>
          )}

          {displayCurrency && !convLoading && !convError && (
            <span className="ml-auto text-xs font-semibold text-[#7A9B6D] bg-[#7A9B6D]/10 border border-[#7A9B6D]/20 rounded-full px-3 py-1">
              Displayed in {displayCurrency}
            </span>
          )}
        </div>
      )}

      {/* ── Empty state ── */}
      {receipts.length === 0 ? (
        <div className="rounded-xl shadow-md overflow-hidden border border-white/10 flex flex-col p-12 text-center" style={{ backgroundColor: "#E9ECE4" }}>
          <FileText className="w-12 h-12 text-slate-300 mx-auto mb-4" />
          <h3 className="text-xl font-bold text-[#171A3A]">No purchases found</h3>
          <p className="text-slate-500 mt-2">You haven't saved any verified receipts yet.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {receipts.map((r) => {
            const conv = getConverted(r);
            const isConverted = conv && !conv.conversion_unavailable && r.currency !== displayCurrency;
            const unavailable = conv?.conversion_unavailable ?? false;
            const origCurr = r.currency;

            // Decide which values to display
            const dispTotal = isConverted ? conv!.total_amount : r.total_amount;
            const dispTax   = isConverted ? conv!.tax : r.tax;
            const dispItems = isConverted ? conv!.items : r.items;
            const dispCurr  = isConverted ? displayCurrency : origCurr;

            return (
              <div
                key={r.id}
                id={`receipt-${r.id}`}
                className={`rounded-xl shadow-md overflow-hidden border flex flex-col transition-all duration-1000 ${
                  highlightedReceiptId === r.id 
                    ? "border-[#0D7C66] ring-4 ring-[#0D7C66]/20 bg-[#f0f4eb]" 
                    : "border-slate-200"
                }`}
                style={{ backgroundColor: highlightedReceiptId === r.id ? "#f0f4eb" : "#E9ECE4" }}
              >
                {/* Card Header */}
                <div className="px-4 py-3 flex items-center justify-between border-b border-slate-300">
                  <div>
                    <h2 className="text-sm font-bold text-slate-800">{r.merchant_name}</h2>
                    <p className="text-xs text-slate-500 mt-0.5 font-support">
                      {r.purchase_date || "Date unknown"} • {r.document_type || "Receipt"}
                      {origCurr && (
                        <span className="ml-2 text-[10px] font-semibold text-slate-400 uppercase tracking-widest">
                          orig. {origCurr}
                        </span>
                      )}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {unavailable && (
                      <span className="text-[10px] text-amber-700 bg-amber-100 border border-amber-200 rounded-full px-2 py-0.5 font-semibold">
                        Conversion unavailable
                      </span>
                    )}
                    {isConverted && conv?.rate_date && (
                      <span className="text-[10px] text-[#0D7C66] bg-[#B8C5A3] border border-[#7A9B6D]/30 rounded-full px-2 py-0.5 font-semibold">
                        Rate: {conv.rate_date}
                      </span>
                    )}
                    {r.cloudinary_public_id && (
                      <button
                        onClick={() => setSelectedReceipt(r)}
                        className="flex items-center gap-1.5 text-xs font-bold text-[#0D7C66] hover:text-[#0a5c4c] transition-colors shrink-0 bg-white/50 px-3 py-1.5 rounded border border-[#B8C5A3]"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                        <span>View Receipt</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Items Table */}
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse min-w-[500px]">
                    <thead>
                      <tr className="border-b border-slate-300">
                        <th className="py-1.5 px-4 text-[11px] font-bold text-[#164A3A] uppercase tracking-widest w-1/2">Item</th>
                        <th className="py-1.5 px-4 text-[11px] font-bold text-[#164A3A] uppercase tracking-widest text-right">Qty</th>
                        <th className="py-1.5 px-4 text-[11px] font-bold text-[#164A3A] uppercase tracking-widest text-right">Unit Price</th>
                        <th className="py-1.5 px-4 text-[11px] font-bold text-[#164A3A] uppercase tracking-widest text-right">Total</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                      {dispItems.length > 0 ? (
                        dispItems.map((item, idx) => (
                          <tr key={idx} className="hover:bg-black/5 transition-colors">
                            <td className="py-1.5 px-4 text-xs font-semibold text-slate-800">{item.item_name}</td>
                            <td className="py-1.5 px-4 text-xs text-slate-600 text-right">
                              {item.quantity != null ? item.quantity : <span className="text-slate-400">—</span>}
                            </td>
                            <td className="py-1.5 px-4 text-xs text-slate-600 text-right">
                              {item.unit_price != null
                                ? fmtAmt(item.unit_price, dispCurr)
                                : <span className="text-slate-400">—</span>}
                            </td>
                            <td className="py-1.5 px-4 text-xs font-bold text-slate-800 text-right">
                              {fmtAmt(item.total_price, dispCurr)}
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={4} className="py-3 text-center text-xs text-slate-500 font-support">
                            No items extracted for this receipt.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                {/* Summary Footer */}
                <div className="border-t border-slate-300 px-4 py-3 flex flex-col items-end gap-1.5">
                  <div className="flex items-center justify-between w-full sm:w-48 text-[11px]">
                    <span className="text-slate-600 font-semibold">Tax</span>
                    <span className="text-slate-800 font-semibold">
                      {dispTax != null ? fmtAmt(dispTax, dispCurr) : <span className="text-slate-400">—</span>}
                    </span>
                  </div>

                  <div className="flex items-center justify-between w-full sm:w-48 text-[11px]">
                    <span className="text-slate-600 font-semibold">Payment Method</span>
                    <span className="text-slate-800 font-semibold">
                      {r.payment_method || <span className="text-slate-400">—</span>}
                    </span>
                  </div>

                  <div className="flex items-center justify-between w-full sm:w-48 text-[11px]">
                    <span className="text-slate-600 font-semibold">Due Date</span>
                    <span className="text-slate-800 font-semibold">
                      {r.due_date || <span className="text-slate-400">—</span>}
                    </span>
                  </div>

                  <div className="flex items-center justify-between w-full sm:w-48 text-[11px] border-b border-slate-300 pb-1.5">
                    <span className="text-slate-600 font-semibold">Warranty</span>
                    <span className="text-slate-800 font-semibold">
                      {r.warranty_period_days != null
                        ? `${r.warranty_period_days} days`
                        : <span className="text-slate-400">—</span>}
                    </span>
                  </div>

                  <div className="flex items-center justify-between w-full sm:w-48 text-sm mt-1">
                    <span className="font-extrabold text-slate-800">Total</span>
                    <div className="flex flex-col items-end gap-0.5">
                      <span className="font-extrabold text-[#0D7C66] tracking-tight">
                        {fmtAmt(dispTotal, dispCurr)}
                      </span>
                      {isConverted && (
                        <span className="text-[10px] text-slate-400 font-support">
                          orig. {fmtAmt(r.total_amount, origCurr)}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

              </div>
            );
          })}
        </div>
      )}

      {/* ── View Receipt Modal ── */}
      {selectedReceipt && selectedReceipt.cloudinary_public_id && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="relative w-full max-w-4xl bg-black rounded-lg shadow-2xl overflow-hidden flex flex-col">
            <div className="absolute top-4 right-4 z-10">
              <button
                onClick={() => setSelectedReceipt(null)}
                className="p-2 bg-white/10 hover:bg-white/20 rounded-full text-white transition-colors backdrop-blur-md"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="w-full h-auto max-h-[85vh] overflow-auto flex items-center justify-center">
              {selectedReceipt.original_filename?.toLowerCase().endsWith(".pdf") ? (
                <iframe
                  src={`https://res.cloudinary.com/iplgysjg/${selectedReceipt.cloudinary_resource_type || "image"}/upload/${selectedReceipt.cloudinary_public_id}.pdf`}
                  title="Receipt PDF"
                  className="w-full h-[85vh] border-0"
                />
              ) : (
                <img
                  src={`https://res.cloudinary.com/iplgysjg/${selectedReceipt.cloudinary_resource_type || "image"}/upload/${selectedReceipt.cloudinary_public_id}`}
                  alt="Receipt Document"
                  className="max-w-full h-auto object-contain"
                />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
