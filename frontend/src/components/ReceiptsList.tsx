import React, { useState } from "react";
import { Search, FileText, UploadCloud, ReceiptText } from "lucide-react";
import { Link } from "react-router-dom";

// Mock data for UI demonstration
const mockReceipts = [
  {
    id: "1",
    merchant_name: "Apple Store",
    date: "Aug 16, 2026 · 8:42 PM",
    document_type: "Purchase Receipt",
    total_amount: "₹2,450.00",
  },
  {
    id: "2",
    merchant_name: "Uber Rides",
    date: "Aug 15, 2026 · 10:15 AM",
    document_type: "Digital Invoice",
    total_amount: "₹450.50",
  },
  {
    id: "3",
    merchant_name: "Starbucks Coffee",
    date: "Aug 12, 2026 · 9:30 AM",
    document_type: "Physical Receipt",
    total_amount: "₹380.00",
  },
];

export const ReceiptsList: React.FC = () => {
  const [activeFilter, setActiveFilter] = useState("All");
  const [searchQuery, setSearchQuery] = useState("");

  const filters = ["All", "Latest", "This Month", "This Year"];

  // Simple filter logic for demonstration
  const filteredReceipts = mockReceipts.filter((r) =>
    r.merchant_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="w-full max-w-6xl mx-auto px-4 sm:px-6 pt-12 pb-20 animate-in fade-in slide-in-from-bottom-4 duration-500">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8">
        <div className="space-y-1">
          <h1 className="text-3xl font-extrabold text-white tracking-tight">My Receipts</h1>
          <p className="text-slate-400 font-support text-sm">
            Keep track of your purchases in one place.
          </p>
        </div>
        <div className="text-sm font-semibold text-slate-300">
          <span className="text-white">{filteredReceipts.length}</span> receipts found
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-brand-cream rounded-2xl p-2 mb-8 flex flex-col md:flex-row items-center justify-between gap-4 shadow-xl border border-white/10">
        
        <div className="flex items-center gap-2 w-full md:w-auto overflow-x-auto pb-2 md:pb-0 hide-scrollbar">
          {filters.map((f) => {
            const isActive = activeFilter === f;
            return (
              <button
                key={f}
                onClick={() => setActiveFilter(f)}
                className={`px-5 py-2.5 rounded-xl text-sm font-bold whitespace-nowrap transition-all ${
                  isActive
                    ? "bg-gradient-to-r from-brand-violet/10 to-brand-teal/10 text-transparent bg-clip-text bg-gradient-to-r shadow-sm border border-brand-violet/20 relative after:content-[''] after:absolute after:inset-0 after:rounded-xl after:border after:border-brand-teal/20"
                    : "text-slate-500 hover:bg-white hover:text-brand-navy hover:shadow-sm"
                }`}
              >
                {/* When using bg-clip-text, the text itself needs the gradient class */}
                <span className={isActive ? "bg-gradient-to-r from-brand-violet to-brand-teal bg-clip-text text-transparent" : ""}>
                  {f}
                </span>
              </button>
            );
          })}
        </div>

        <div className="relative w-full md:w-72">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search merchants..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-white border border-slate-200 rounded-xl pl-9 pr-4 py-2.5 text-sm font-semibold text-brand-navy focus:outline-none focus:border-brand-violet focus:ring-1 focus:ring-brand-violet transition-colors"
          />
        </div>
      </div>

      {/* Receipts List */}
      {filteredReceipts.length > 0 ? (
        <div className="space-y-4">
          {filteredReceipts.map((receipt) => (
            <div
              key={receipt.id}
              className="bg-brand-cream rounded-2xl p-4 sm:p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border border-slate-100 hover:border-brand-violet/30 hover:shadow-lg transition-all group cursor-pointer"
            >
              
              <div className="flex items-center gap-4 w-full sm:w-auto">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-100 to-violet-100 text-indigo-600 flex items-center justify-center shrink-0 border border-indigo-50">
                  <ReceiptText className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-brand-navy mb-0.5">{receipt.merchant_name}</h3>
                  <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-2 text-xs text-slate-500 font-support">
                    <span>{receipt.date}</span>
                    <span className="hidden sm:inline text-slate-300">•</span>
                    <span className="font-semibold text-slate-400">{receipt.document_type}</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between sm:justify-end w-full sm:w-auto gap-6 sm:gap-8 pt-4 sm:pt-0 border-t sm:border-t-0 border-slate-200">
                <div className="text-lg font-extrabold text-brand-navy">
                  {receipt.total_amount}
                </div>
                <button className="text-sm font-bold text-brand-violet group-hover:text-brand-teal transition-colors flex items-center gap-1">
                  View <span className="text-lg leading-none">&rarr;</span>
                </button>
              </div>

            </div>
          ))}
        </div>
      ) : (
        /* Empty State */
        <div className="bg-brand-cream rounded-[32px] p-12 flex flex-col items-center justify-center text-center shadow-2xl border border-white/5 mt-8">
          <div className="w-20 h-20 rounded-full bg-gradient-to-br from-brand-violet/10 to-brand-teal/10 flex items-center justify-center mb-6">
            <UploadCloud className="w-8 h-8 text-brand-violet" />
          </div>
          <h3 className="text-2xl font-extrabold text-brand-navy mb-2">No receipts found</h3>
          <p className="text-slate-500 font-support max-w-sm mb-8">
            {searchQuery
              ? `We couldn't find any receipts matching "${searchQuery}".`
              : "Upload your first physical receipt or digital invoice to start tracking your purchases automatically."}
          </p>
          {!searchQuery && (
            <Link
              to="/upload"
              className="px-8 py-3 bg-gradient-to-r from-brand-violet to-brand-teal text-white font-bold text-sm rounded-xl hover:opacity-90 transition-opacity shadow-lg"
            >
              Upload Receipt
            </Link>
          )}
        </div>
      )}

    </div>
  );
};
