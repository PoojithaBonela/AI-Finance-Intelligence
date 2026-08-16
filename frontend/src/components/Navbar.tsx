import React from "react";
import { NavLink } from "react-router-dom";
import logo from "../assets/TracePaylogo.png";
import { User, Bell, Search, ChevronDown } from "lucide-react";

export const Navbar: React.FC = () => {
  const baseLinkCls = "text-sm font-medium transition-colors relative py-1";
  const activeLinkCls = "text-brand-navy font-semibold after:content-[''] after:absolute after:left-0 after:-bottom-1 after:w-full after:h-[2px] after:bg-brand-teal after:rounded-full";
  const inactiveLinkCls = "text-slate-500 hover:text-brand-navy";

  return (
    <div className="sticky top-5 z-50 w-full px-4 sm:px-6 pointer-events-none">
      <nav className="mx-auto w-[94%] max-w-7xl h-14 bg-white shadow-md rounded-full border border-slate-200/60 pointer-events-auto px-6 sm:px-8 flex items-center justify-between">
        
        {/* Brand & Links */}
        <div className="flex items-center gap-8 md:gap-12">
          <div className="flex items-center gap-3">
            <img src={logo} alt="TracePay Logo" className="h-6 w-auto object-contain" />
          </div>
          
          <div className="hidden md:flex items-center gap-6">
            <NavLink to="/upload" className={({ isActive }) => `${baseLinkCls} ${isActive ? activeLinkCls : inactiveLinkCls}`}>
              Upload
            </NavLink>
            <NavLink to="/receipts" className={({ isActive }) => `${baseLinkCls} ${isActive ? activeLinkCls : inactiveLinkCls}`}>
              Receipts
            </NavLink>
            <NavLink to="/purchases" className={({ isActive }) => `${baseLinkCls} ${isActive ? activeLinkCls : inactiveLinkCls}`}>
              Purchases
            </NavLink>
            <a href="#" className="text-sm font-medium text-slate-500 hover:text-brand-navy transition-colors py-1">
              Analytics
            </a>
            <a href="#" className="text-sm font-medium text-slate-500 hover:text-brand-navy transition-colors py-1">
              AI Insights
            </a>
          </div>
        </div>

        {/* Actions & Profile */}
        <div className="flex items-center gap-4">
          <button className="text-slate-500 hover:text-brand-navy transition-colors">
            <Search className="w-4 h-4 sm:w-5 sm:h-5" />
          </button>
          <button className="text-slate-500 hover:text-brand-navy transition-colors relative">
            <Bell className="w-4 h-4 sm:w-5 sm:h-5" />
            <span className="absolute top-0 right-0 w-1.5 h-1.5 bg-brand-teal rounded-full border border-white"></span>
          </button>
          <div className="h-4 w-px bg-slate-200 mx-1"></div>
          <button className="flex items-center gap-2 group">
            <div className="w-7 h-7 rounded-full bg-slate-100 flex items-center justify-center text-slate-600 font-semibold text-[11px]">
              P
            </div>
            <span className="text-sm font-medium text-brand-navy group-hover:text-brand-teal transition-colors hidden sm:flex items-center gap-1">
              Workspace <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
            </span>
          </button>
        </div>
      </nav>
    </div>
  );
};
