import React, { useState } from "react";
import { NavLink, Link, useNavigate } from "react-router-dom";
import logo from "../assets/TracePaylogo.png";
import { Bell, Search, ChevronDown, LogOut, Menu, X } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export const Navbar: React.FC = () => {
  const { session, user, signOut } = useAuth();
  const navigate = useNavigate();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const baseLinkCls = "text-sm font-medium transition-colors relative py-1";
  const activeLinkCls = "text-brand-navy font-semibold after:content-[''] after:absolute after:left-0 after:-bottom-1 after:w-full after:h-[2px] after:bg-brand-teal after:rounded-full";
  const inactiveLinkCls = "text-slate-500 hover:text-brand-navy";

  const handleSignOut = async () => {
    await signOut();
    navigate("/login");
  };

  const initial = user?.user_metadata?.first_name?.[0] || user?.email?.[0]?.toUpperCase() || "U";

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
            {session && (
              <>
                <NavLink to="/receipts" className={({ isActive }) => `${baseLinkCls} ${isActive ? activeLinkCls : inactiveLinkCls}`}>
                  Receipts
                </NavLink>
                <NavLink to="/purchases" className={({ isActive }) => `${baseLinkCls} ${isActive ? activeLinkCls : inactiveLinkCls}`}>
                  Purchases
                </NavLink>
                <NavLink to="/analytics" className={({ isActive }) => `${baseLinkCls} ${isActive ? activeLinkCls : inactiveLinkCls}`}>
                  Analytics
                </NavLink>
                <a href="#" className="text-sm font-medium text-slate-500 hover:text-brand-navy transition-colors py-1">
                  AI Insights
                </a>
              </>
            )}
          </div>
        </div>

        {/* Actions & Profile (Desktop) + Hamburger (Mobile) */}
        <div className="flex items-center gap-4">
          {!session ? (
            <div className="flex items-center gap-3">
              <Link to="/login" className="text-sm font-bold text-[#164A3A] hover:text-[#7A9B6D] transition-colors">
                Login
              </Link>
              <Link to="/signup" className="text-sm font-bold bg-[#7A9B6D] text-white px-4 py-1.5 rounded-full hover:bg-[#7A9B6D]/90 shadow-sm transition-all active:scale-[0.98]">
                Get Started
              </Link>
            </div>
          ) : (
            <>
              {/* Mobile Hamburger */}
              <button
                className="md:hidden p-2 text-slate-500 hover:text-brand-navy transition-colors focus:outline-none"
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              >
                {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>

              <div className="hidden md:flex items-center gap-4">
                <button className="text-slate-500 hover:text-brand-navy transition-colors">
                  <Search className="w-4 h-4" />
                </button>
                <button className="text-slate-500 hover:text-brand-navy transition-colors relative">
                  <Bell className="w-4 h-4" />
                  <span className="absolute top-0 right-0 w-1.5 h-1.5 bg-brand-teal rounded-full border border-white"></span>
                </button>
                <div className="h-4 w-px bg-slate-200 mx-1"></div>
                <div className="relative">
                  <button 
                    onClick={() => setDropdownOpen(!dropdownOpen)}
                    className="flex items-center gap-2 group focus:outline-none"
                  >
                    <div className="w-7 h-7 rounded-full bg-slate-100 flex items-center justify-center text-slate-600 font-semibold text-[11px]">
                      {initial}
                    </div>
                    <span className="text-sm font-medium text-brand-navy group-hover:text-brand-teal transition-colors flex items-center gap-1">
                      Workspace <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`} />
                    </span>
                  </button>

                  {dropdownOpen && (
                    <div className="absolute right-0 mt-3 w-48 bg-white rounded-xl shadow-lg border border-slate-100 overflow-hidden py-1">
                      <div className="px-4 py-2 border-b border-slate-100">
                        <p className="text-xs text-slate-500 font-medium">Signed in as</p>
                        <p className="text-sm font-bold text-[#171A3A] truncate">{user?.email}</p>
                      </div>
                      <button
                        onClick={handleSignOut}
                        className="w-full text-left px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 transition-colors flex items-center gap-2"
                      >
                        <LogOut className="w-4 h-4" />
                        Sign Out
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </nav>

      {/* Mobile Menu Overlay */}
      {mobileMenuOpen && session && (
        <>
          <div 
            className="fixed inset-0 z-40 bg-black/20 md:hidden backdrop-blur-sm" 
            onClick={() => setMobileMenuOpen(false)} 
          />
          <div className="absolute top-20 left-4 right-4 bg-white rounded-2xl shadow-2xl border border-slate-100 p-4 z-50 md:hidden flex flex-col gap-2 animate-in slide-in-from-top-4 duration-200 pointer-events-auto">
            <NavLink 
              to="/upload" 
              onClick={() => setMobileMenuOpen(false)}
              className={({ isActive }) => `px-4 py-3 rounded-xl text-base font-semibold transition-colors ${isActive ? "bg-[#0D7C66]/10 text-[#0D7C66]" : "text-slate-600 hover:bg-slate-50"}`}
            >
              Upload
            </NavLink>
            <NavLink 
              to="/receipts" 
              onClick={() => setMobileMenuOpen(false)}
              className={({ isActive }) => `px-4 py-3 rounded-xl text-base font-semibold transition-colors ${isActive ? "bg-[#0D7C66]/10 text-[#0D7C66]" : "text-slate-600 hover:bg-slate-50"}`}
            >
              Receipts
            </NavLink>
            <NavLink 
              to="/purchases" 
              onClick={() => setMobileMenuOpen(false)}
              className={({ isActive }) => `px-4 py-3 rounded-xl text-base font-semibold transition-colors ${isActive ? "bg-[#0D7C66]/10 text-[#0D7C66]" : "text-slate-600 hover:bg-slate-50"}`}
            >
              Purchases
            </NavLink>
            <NavLink 
              to="/analytics" 
              onClick={() => setMobileMenuOpen(false)}
              className={({ isActive }) => `px-4 py-3 rounded-xl text-base font-semibold transition-colors ${isActive ? "bg-[#0D7C66]/10 text-[#0D7C66]" : "text-slate-600 hover:bg-slate-50"}`}
            >
              Analytics
            </NavLink>
            <a 
              href="#" 
              onClick={() => setMobileMenuOpen(false)}
              className="px-4 py-3 rounded-xl text-base font-semibold text-slate-600 hover:bg-slate-50 transition-colors"
            >
              AI Insights
            </a>
            
            <div className="h-px bg-slate-100 my-2"></div>
            
            <div className="px-4 py-2">
              <p className="text-xs text-slate-500 font-medium">Signed in as</p>
              <p className="text-sm font-bold text-[#171A3A] truncate">{user?.email}</p>
            </div>
            
            <button
              onClick={() => { setMobileMenuOpen(false); handleSignOut(); }}
              className="w-full text-left px-4 py-3 rounded-xl text-base font-semibold text-red-600 hover:bg-red-50 transition-colors flex items-center gap-2"
            >
              <LogOut className="w-5 h-5" />
              Sign Out
            </button>
          </div>
        </>
      )}
    </div>
  );
};
