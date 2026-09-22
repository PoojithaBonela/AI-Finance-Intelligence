import { useState, useEffect, useRef } from "react";
import { X, ChevronDown } from "lucide-react";

export function FilterDropdown({ 
  label, options, value, onChange, onClear, canClear = true, disabled = false
}: { 
  label: string;
  options: { label: string; value: string }[];
  value: string | null;
  onChange: (v: string) => void;
  onClear: () => void;
  canClear?: boolean;
  disabled?: boolean;
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
    <div className={`relative shrink-0 ${disabled ? "opacity-50 pointer-events-none" : ""}`} ref={dropdownRef}>
      <div 
        className={`px-4 py-2 rounded-full text-sm font-bold whitespace-nowrap transition-all flex items-center gap-1.5 border select-none ${
          disabled ? "bg-[#F5F3EA] text-[#171A3A]/40 border-[#171A3A]/10 cursor-not-allowed" : "cursor-pointer " + (
            value !== null ? "bg-[#164A3A] text-white border-[#164A3A] shadow-sm" : "bg-[#F5F3EA] text-[#171A3A] border-[#171A3A]/10 hover:bg-white"
          )
        }`}
        onClick={() => !disabled && setIsOpen(!isOpen)}
      >
        <span>{activeOption ? activeOption.label : label}</span>
        {value !== null && canClear ? (
          <button 
            onClick={(e) => { e.stopPropagation(); onClear(); }} 
            className="hover:text-[#00BFA6] transition-colors -mr-1 p-0.5"
            title="Clear"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        ) : (
          <ChevronDown className="w-3.5 h-3.5 opacity-50 -mr-1" />
        )}
      </div>

      {isOpen && !disabled && (
        <div className="absolute top-full mt-2 left-0 min-w-full bg-white rounded-xl shadow-xl border border-slate-100 py-1.5 z-20 animate-in fade-in zoom-in-95 duration-100 max-h-60 overflow-y-auto custom-scrollbar">
          {options.map(opt => {
            const isSelected = value === opt.value || (value === null && opt.value === "all");
            return (
              <button
                key={opt.value}
                onClick={() => { onChange(opt.value); setIsOpen(false); }}
                className={`w-full text-left px-4 py-2.5 text-sm font-semibold transition-colors whitespace-nowrap ${
                  isSelected ? "bg-[#0D7C66]/10 text-[#0D7C66]" : "text-[#171A3A] hover:bg-slate-50"
                }`}
              >
                {opt.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
