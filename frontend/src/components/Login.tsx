import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import logoImg from "../assets/TracePaylogo.png";

export const Login: React.FC = () => {
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Auth logic will go here
  };

  return (
    <div className="flex-1 flex items-center justify-center p-4">
      <div className="w-full max-w-[340px] bg-[#F5F3EA] rounded-3xl shadow-2xl overflow-hidden border border-white/20 p-5 sm:p-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
        
        {/* Logo */}
        <div className="flex justify-center mb-5">
          <img src={logoImg} alt="TracePay" className="h-8 w-auto" />
        </div>

        {/* Title */}
        <div className="text-center mb-6">
          <h2 className="text-xl font-bold text-[#171A3A]">Sign In</h2>
          <p className="text-[#171A3A]/60 text-xs mt-1 font-support">Welcome back to your workspace</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="block text-sm font-semibold text-[#171A3A]">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@example.com"
              className="w-full bg-white border border-[#171A3A]/10 rounded-xl px-4 py-2.5 text-sm text-[#171A3A] font-medium focus:outline-none focus:border-[#7A9B6D] focus:ring-1 focus:ring-[#7A9B6D] transition-colors shadow-sm placeholder:text-[#171A3A]/30"
              required
            />
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="block text-sm font-semibold text-[#171A3A]">Password</label>
              <a href="#" className="text-xs font-semibold text-[#164A3A] hover:text-[#7A9B6D] transition-colors">
                Forgot password?
              </a>
            </div>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                className="w-full bg-white border border-[#171A3A]/10 rounded-xl pl-4 pr-11 py-2.5 text-sm text-[#171A3A] font-medium focus:outline-none focus:border-[#7A9B6D] focus:ring-1 focus:ring-[#7A9B6D] transition-colors shadow-sm placeholder:text-[#171A3A]/30"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#171A3A]/40 hover:text-[#171A3A]/70 transition-colors p-1"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            className="w-full bg-[#7A9B6D] hover:bg-[#7A9B6D]/90 text-white font-bold py-3 px-4 rounded-xl shadow-md hover:shadow-lg transition-all active:scale-[0.98]"
          >
            Login
          </button>
        </form>

        {/* Divider */}
        <div className="my-5 flex items-center gap-3">
          <div className="flex-1 h-px bg-[#171A3A]/10"></div>
          <span className="text-[10px] font-bold text-[#171A3A]/40 tracking-wider">OR</span>
          <div className="flex-1 h-px bg-[#171A3A]/10"></div>
        </div>

        {/* Google Login */}
        <button
          type="button"
          className="w-full bg-white border border-[#171A3A]/10 hover:bg-slate-50 text-[#171A3A] font-semibold py-2.5 px-4 rounded-xl shadow-sm transition-all flex items-center justify-center gap-3 active:scale-[0.98] text-sm"
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24">
            <path
              fill="currentColor"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="#34A853"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="#FBBC05"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
            />
            <path
              fill="#EA4335"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            />
          </svg>
          Continue with Google
        </button>

        {/* Sign Up Link */}
        <p className="mt-6 text-center text-xs font-medium text-[#171A3A]/70">
          Don't have an account?{" "}
          <Link to="/signup" className="text-[#164A3A] hover:text-[#7A9B6D] font-bold transition-colors">
            Sign Up
          </Link>
        </p>

      </div>
    </div>
  );
};
