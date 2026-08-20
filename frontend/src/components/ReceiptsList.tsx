import React, { useState, useEffect, useRef } from "react";
import { Search, UploadCloud, ReceiptText, Loader2, X, ChevronDown } from "lucide-react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

// Types
interface Receipt {
  id: string;
  merchant_name: string;
  purchase_date: string | null;
  document_type: string | null;
  total_amount: number;
  currency: string | null;
  cloudinary_public_id: string | null;
}

function FilterDropdown({ 
  label, options, value, onChange, onClear 
}: { 
  label: string;
  options: { label: string; value: string }[];
  value: string | null;
  onChange: (v: string) => void;
  onClear: () => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const activeOption = options.find(o => o.value === value);

  return (
    <div className="relative shrink-0" ref={dropdownRef}>
      <div 
        className={`px-4 py-2 rounded-full text-sm font-bold whitespace-nowrap transition-all flex items-center gap-1.5 border cursor-pointer select-none ${
          value !== null ? "bg-[#164A3A] text-white border-[#164A3A] shadow-sm" : "bg-[#F5F3EA] text-[#171A3A] border-[#171A3A]/10 hover:bg-white"
        }`}
        onClick={() => setIsOpen(!isOpen)}
      >
        <span>{activeOption ? activeOption.label : label}</span>
        {value !== null ? (
          <button 
            onClick={(e) => { e.stopPropagation(); onClear(); }} 
            className="hover:text-[#00BFA6] transition-colors -mr-1 p-0.5"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        ) : (
          <ChevronDown className="w-3.5 h-3.5 opacity-50 -mr-1" />
        )}
      </div>

      {isOpen && (
        <div className="absolute top-full mt-2 left-0 min-w-full bg-white rounded-xl shadow-xl border border-slate-100 py-1.5 z-20 animate-in fade-in zoom-in-95 duration-100 max-h-60 overflow-y-auto custom-scrollbar">
          {options.map(opt => (
            <button
              key={opt.value}
              onClick={() => { onChange(opt.value); setIsOpen(false); }}
              className={`w-full text-left px-4 py-2.5 text-sm font-semibold transition-colors whitespace-nowrap ${
                value === opt.value ? "bg-[#0D7C66]/10 text-[#0D7C66]" : "text-[#171A3A] hover:bg-slate-50"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export const ReceiptsList: React.FC = () => {
  const { session } = useAuth();
  const [searchQuery, setSearchQuery] = useState("");
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Filter state
  const [dateSort, setDateSort] = useState<"latest" | "oldest" | null>(null);
  const [activeMonth, setActiveMonth] = useState<string | null>(null);
  const [activeYear, setActiveYear] = useState<string | null>(null);
  const [priceSort, setPriceSort] = useState<"high" | "low" | null>(null);

  // Currency conversion map for price sorting
  const [convertedSortMap, setConvertedSortMap] = useState<Record<string, number>>({});

  // Lightbox modal state
  const [previewImage, setPreviewImage] = useState<string | null>(null);

  useEffect(() => {
    const fetchReceipts = async () => {
      try {
        setLoading(true);
        const headers: Record<string, string> = {};
        if (session?.access_token) {
          headers["Authorization"] = `Bearer ${session.access_token}`;
        }
        const res = await fetch("http://localhost:8000/api/receipts", { headers });
        if (!res.ok) throw new Error("Failed to fetch receipts.");
        const data = await res.json();
        setReceipts(data);
      } catch (err: any) {
        console.error(err.message || "An error occurred.");
      } finally {
        setLoading(false);
      }
    };
    fetchReceipts();
  }, []);

  // Fetch conversions for price sorting
  useEffect(() => {
    if (receipts.length === 0) return;
    const fetchConversions = async () => {
      try {
        const payload = {
          target_currency: "USD",
          receipts: receipts.map(r => ({
            id: r.id,
            currency: r.currency || "USD",
            total_amount: r.total_amount,
            purchase_date: r.purchase_date,
            items: [],
          })),
        };
        const headers: Record<string, string> = { "Content-Type": "application/json" };
        if (session?.access_token) {
          headers["Authorization"] = `Bearer ${session.access_token}`;
        }
        const res = await fetch("http://localhost:8000/api/convert-receipts", {
          method: "POST",
          headers,
          body: JSON.stringify(payload),
        });
        if (res.ok) {
          const data = await res.json();
          const map: Record<string, number> = {};
          for (const r of data.results) {
             map[r.id] = r.total_amount;
          }
          setConvertedSortMap(map);
        }
      } catch (err) {
        console.error("Failed to fetch conversions for sorting", err);
      }
    };
    fetchConversions();
  }, [receipts]);

  const availableYears = Array.from(new Set(receipts.map(r => r.purchase_date ? new Date(r.purchase_date).getFullYear() : null).filter((y): y is number => y !== null && !isNaN(y)))).sort((a,b) => b - a);
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  // Complex filter & sort logic
  let filteredReceipts = receipts.filter((r) => {
    if (searchQuery && !(r.merchant_name || "Unknown Merchant").toLowerCase().includes(searchQuery.toLowerCase())) return false;
    
    if (activeMonth !== null || activeYear !== null) {
      if (!r.purchase_date) return false;
      const d = new Date(r.purchase_date);
      if (isNaN(d.getTime())) return false;
      if (activeMonth !== null && d.getMonth() !== parseInt(activeMonth)) return false;
      if (activeYear !== null && d.getFullYear() !== parseInt(activeYear)) return false;
    }
    return true;
  });

  filteredReceipts.sort((a, b) => {
    if (priceSort) {
      const amtA = convertedSortMap[a.id] ?? a.total_amount;
      const amtB = convertedSortMap[b.id] ?? b.total_amount;
      return priceSort === "high" ? amtB - amtA : amtA - amtB;
    }
    const tA = a.purchase_date ? new Date(a.purchase_date).getTime() : 0;
    const tB = b.purchase_date ? new Date(b.purchase_date).getTime() : 0;
    return dateSort === "oldest" ? tA - tB : tB - tA; // default is latest
  });

  const clearAllFilters = () => {
    setDateSort(null);
    setActiveMonth(null);
    setActiveYear(null);
    setPriceSort(null);
  };

  const formatAmount = (amt: number, curr: string | null) => {
    const sym = curr === "USD" ? "$" : curr === "INR" ? "₹" : curr === "EUR" ? "€" : curr === "GBP" ? "£" : (curr || "");
    return `${sym}${amt.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };
  
  const formatDate = (dateString: string | null) => {
    if (!dateString) return "Unknown Date";
    try {
      const d = new Date(dateString);
      if (isNaN(d.getTime())) return dateString;
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return dateString;
    }
  };

  if (loading) {
    return (
      <div className="w-full h-64 flex flex-col items-center justify-center pt-24">
        <Loader2 className="w-8 h-8 text-brand-violet animate-spin mb-4" />
        <p className="text-white/60 font-support">Loading your receipts...</p>
      </div>
    );
  }

  return (
    <div className="w-full max-w-4xl mx-auto px-4 sm:px-6 pt-12 pb-20 animate-in fade-in slide-in-from-bottom-4 duration-500">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8">
        <div className="space-y-1">
          <h1 className="text-3xl font-extrabold text-white tracking-tight">My Receipts</h1>
          <p className="text-white/70 font-support text-sm">
            Keep track of your purchases in one place.
          </p>
        </div>
        <div className="text-sm font-semibold text-white/60">
          <span className="text-white">{filteredReceipts.length}</span> receipts found
        </div>
      </div>

      {/* Search Bar - Half Width on Top */}
      <div className="relative w-full max-w-[50%] mb-4">
        <Search className="w-4 h-4 text-white/50 absolute left-4 top-1/2 -translate-y-1/2" />
        <input
          type="text"
          placeholder="Search merchants..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full bg-white/10 border border-white/20 rounded-full pl-10 pr-4 py-2 text-sm font-semibold text-white placeholder-white/40 focus:outline-none focus:border-[#00BFA6] focus:ring-1 focus:ring-[#00BFA6] transition-colors shadow-sm"
        />
      </div>

      {/* Filter Bar */}
      <div className="mb-8">
        
        {/* Pills Container */}
        <div className="flex items-center gap-2 w-full flex-wrap">
          
          {/* All */}
          <button
            onClick={clearAllFilters}
            className={`shrink-0 px-4 py-2 rounded-full text-sm font-bold whitespace-nowrap transition-all flex items-center gap-1.5 border ${
              dateSort === null && activeMonth === null && activeYear === null && priceSort === null
                ? "bg-[#164A3A] text-white border-[#164A3A] shadow-sm"
                : "bg-[#F5F3EA] text-[#171A3A] border-[#171A3A]/10 hover:bg-white"
            }`}
          >
            All {(dateSort !== null || activeMonth !== null || activeYear !== null || priceSort !== null) && <X className="w-3.5 h-3.5 opacity-70 -mr-1" />}
          </button>

          <FilterDropdown 
            label="Date"
            options={[
              { label: "Latest", value: "latest" },
              { label: "Oldest", value: "oldest" }
            ]}
            value={dateSort}
            onChange={(v) => setDateSort(v as "latest" | "oldest")}
            onClear={() => setDateSort(null)}
          />

          <FilterDropdown 
            label="Month"
            options={months.map((m, i) => ({ label: m, value: i.toString() }))}
            value={activeMonth}
            onChange={setActiveMonth}
            onClear={() => setActiveMonth(null)}
          />

          <FilterDropdown 
            label="Year"
            options={availableYears.map(y => ({ label: y.toString(), value: y.toString() }))}
            value={activeYear}
            onChange={setActiveYear}
            onClear={() => setActiveYear(null)}
          />

          <FilterDropdown 
            label="Price"
            options={[
              { label: "Price: High → Low", value: "high" },
              { label: "Price: Low → High", value: "low" }
            ]}
            value={priceSort}
            onChange={(v) => setPriceSort(v as "high" | "low")}
            onClear={() => setPriceSort(null)}
          />

        </div>
      </div>

      {/* Receipts List */}
      {filteredReceipts.length > 0 ? (
        <div className="space-y-4">
          {filteredReceipts.map((receipt) => (
            <div
              key={receipt.id}
              className="bg-[#F5F3EA] rounded-2xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border border-[#171A3A]/10 hover:border-[#0D7C66]/30 hover:shadow-md transition-all group cursor-pointer"
            >
              
              <div className="flex items-center gap-4 w-full sm:w-auto">
                <div 
                  className="w-12 h-12 rounded-xl bg-[#0D7C66]/10 text-[#0D7C66] flex items-center justify-center shrink-0 border border-[#0D7C66]/20 overflow-hidden cursor-zoom-in group/thumb relative"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (receipt.cloudinary_public_id) {
                      setPreviewImage(`https://res.cloudinary.com/iplgysjg/image/upload/${receipt.cloudinary_public_id}`);
                    }
                  }}
                >
                  {receipt.cloudinary_public_id ? (
                    <>
                      <img 
                        src={`https://res.cloudinary.com/iplgysjg/image/upload/w_100,c_fill/${receipt.cloudinary_public_id}`} 
                        alt="Thumbnail" 
                        className="w-full h-full object-cover transition-transform group-hover/thumb:scale-110" 
                      />
                      <div className="absolute inset-0 bg-black/20 opacity-0 group-hover/thumb:opacity-100 transition-opacity flex items-center justify-center">
                        <Search className="w-4 h-4 text-white" />
                      </div>
                    </>
                  ) : (
                    <ReceiptText className="w-5 h-5" />
                  )}
                </div>
                <div>
                  <h3 className="text-base font-bold text-[#171A3A] mb-0.5">{receipt.merchant_name || "Unknown"}</h3>
                  <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-2 text-xs text-[#171A3A]/60 font-support">
                    <span>{formatDate(receipt.purchase_date)}</span>
                    <span className="hidden sm:inline text-[#171A3A]/30">•</span>
                    <span className="font-semibold text-[#171A3A]/50">{receipt.document_type || "Receipt"}</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between sm:justify-end w-full sm:w-auto gap-6 sm:gap-8 pt-4 sm:pt-0 border-t sm:border-t-0 border-[#171A3A]/10">
                <div className="text-lg font-extrabold text-[#171A3A]">
                  {formatAmount(receipt.total_amount, receipt.currency)}
                </div>
                <Link 
                  to="/purchases" 
                  state={{ selectedReceiptId: receipt.id }}
                  className="text-sm font-bold text-[#0D7C66] hover:text-[#0a5e4d] transition-colors flex items-center gap-1"
                >
                  View <span className="text-lg leading-none">&rarr;</span>
                </Link>
              </div>

            </div>
          ))}
        </div>
      ) : (
        /* Empty State */
        <div className="bg-[#F5F3EA] rounded-[32px] p-12 flex flex-col items-center justify-center text-center shadow-sm border border-[#171A3A]/10 mt-8">
          <div className="w-20 h-20 rounded-full bg-[#0D7C66]/10 flex items-center justify-center mb-6">
            <UploadCloud className="w-8 h-8 text-[#0D7C66]" />
          </div>
          <h3 className="text-2xl font-extrabold text-[#171A3A] mb-2">No receipts found</h3>
          <p className="text-[#171A3A]/60 font-support max-w-sm mb-8">
            {searchQuery
              ? `We couldn't find any receipts matching "${searchQuery}".`
              : "Upload your first physical receipt or digital invoice to start tracking your purchases automatically."}
          </p>
          {!searchQuery && (
            <Link
              to="/upload"
              className="px-8 py-3 bg-[#7A9B6D] hover:bg-[#6B8C5E] text-white font-bold text-sm rounded-xl transition-colors shadow-sm"
            >
              Upload Receipt
            </Link>
          )}
        </div>
      )}

      {/* Lightbox Modal */}
      {previewImage && (
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-200"
          onClick={() => setPreviewImage(null)}
        >
          <div 
            className="relative max-w-4xl max-h-[90vh] w-full h-full flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close Button */}
            <div className="flex justify-end mb-4">
              <button 
                onClick={() => setPreviewImage(null)}
                className="p-2 bg-white/10 hover:bg-white/20 rounded-full text-white transition-colors backdrop-blur-md"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
            
            {/* Image Container */}
            <div className="flex-1 w-full bg-black/50 rounded-2xl overflow-hidden border border-white/10 flex items-center justify-center">
              <img 
                src={previewImage} 
                alt="Receipt Preview" 
                className="max-w-full max-h-full object-contain"
              />
            </div>
          </div>
        </div>
      )}

    </div>
  );
};
