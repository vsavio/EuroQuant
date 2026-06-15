"use client";

import React, { useState, useEffect } from "react";
import { 
  TrendingUp, TrendingDown, RefreshCw, AlertTriangle, 
  Search, ShieldAlert, Award, FileText, Globe, Cpu, X,
  Activity, ArrowUpRight, Newspaper, Play, Calendar, Percent,
  PieChart, Crosshair
} from "lucide-react";
import { 
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, 
  LineChart, Line, Legend, ComposedChart, Bar, ReferenceLine
} from "recharts";

const V2TX_THRESHOLD = 30.0;

// TypeScript Interfaces
interface IndexSummary {
  ticker: string;
  name: string;
  price: number;
  change_pct: number;
}

interface ForexSummary {
  ticker: string;
  name: string;
  price: number;
  change_pct: number;
}

interface VolatilitySummary {
  price: number;
  status: string;
  message: string;
}

interface MetalsSummary {
  ticker: string;
  name: string;
  price: number;
  change_pct: number;
}

interface CryptoSummary {
  ticker: string;
  name: string;
  price: number;
  change_pct: number;
}

interface MarketSummary {
  indices: IndexSummary[];
  v2tx: VolatilitySummary;
  forex: ForexSummary[];
  metals: MetalsSummary[];
  crypto: CryptoSummary[];
  global_circuit_breaker: boolean;
}

interface ScreenerRow {
  ticker: string;
  name: string;
  country: string;
  sector: string;
  price: number;
  price_change_24h: number;
  sentiment_score: number;
  signal: string;
  timestamp: string;
  ml_prediction_prob?: number;
}

interface NewsArticle {
  id: number;
  title: string;
  content: string;
  url: string;
  source: string;
  published_date: string;
  country: string;
  sentiment_label: string | null;
  sentiment_score: number | null;
  tickers: string[];
}

interface StockDetail {
  ticker: string;
  name: string;
  country: string;
  sector: string;
  industry: string;
  price: number;
  price_change_24h: number;
  sentiment_score: number;
  signal: string;
  reason_macro: string;
  reason_micro: string;
  reason_technical: string;
  history: any[];
  beta: number;
  correlation: number | null;
  hedging_suggestion: string;
  mt5_symbol: string;
  stop_loss: number;
  take_profit: number;
  ml_prediction_prob?: number;
  kelly_factor?: number;
  chandelier_exit_distance?: number;
}

interface BrokerAccount {
  account_id: string;
  broker: string;
  balance: number;
  equity: number;
  margin: number;
  margin_free: number;
  margin_level: number;
  profit: number;
  last_seen: string | null;
}

let originalFetchRef: any = null;
if (typeof window !== "undefined") {
  originalFetchRef = window.fetch;
  window.fetch = async (input, init) => {
    const token = localStorage.getItem("euroquant_token");
    if (token) {
      init = init || {};
      init.headers = init.headers || {};
      if (init.headers instanceof Headers) {
        init.headers.set("Authorization", `Bearer ${token}`);
      } else if (Array.isArray(init.headers)) {
        init.headers.push(["Authorization", `Bearer ${token}`]);
      } else {
        (init.headers as any)["Authorization"] = `Bearer ${token}`;
      }
    }
    const response = await originalFetchRef(input, init);
    if (response.status === 401) {
      localStorage.removeItem("euroquant_token");
      window.dispatchEvent(new Event("auth_failed"));
    }
    return response;
  };
}

interface LoginScreenProps {
  onLogin: () => void;
  API_URL: string;
}

function LoginScreen({ onLogin, API_URL }: LoginScreenProps) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [isRegistering, setIsRegistering] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const endpoint = isRegistering ? "/api/auth/register" : "/api/auth/login";
      const res = await originalFetchRef(`${API_URL}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Authentication failed");
      }

      const data = await res.json();
      localStorage.setItem("euroquant_token", data.access_token);
      onLogin();
    } catch (err: any) {
      setError(err.message || "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#06090e] text-[#e1e4e8] flex items-center justify-center p-4 relative overflow-hidden font-mono">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_30%,#1e2d42_0%,transparent_50%)] pointer-events-none" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_70%,#122336_0%,transparent_50%)] pointer-events-none" />
      <div className="max-w-md w-full border border-[#30363d] bg-[#0d1117]/85 backdrop-blur-md rounded-lg shadow-2xl p-8 relative z-10">
        <div className="flex items-center gap-3 mb-6 justify-center">
          <div className="w-12 h-12 bg-[#00ff66] text-black flex items-center justify-center font-bold text-2xl rounded">
            EQ
          </div>
          <div>
            <h1 className="text-[#00ff66] font-black tracking-wider text-2xl">🏛️ EUROQUANT</h1>
            <p className="text-xs text-[#8b949e]">INSTITUTIONAL QUANT SYSTEM</p>
          </div>
        </div>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs uppercase tracking-wider text-[#8b949e] mb-1">Username</label>
            <input 
              type="text" 
              value={username} 
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-[#161b22] border border-[#30363d] focus:border-[#00ff66] focus:outline-none rounded px-3 py-2 text-sm text-[#e1e4e8]"
              required
            />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wider text-[#8b949e] mb-1">Password</label>
            <input 
              type="password" 
              value={password} 
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-[#161b22] border border-[#30363d] focus:border-[#00ff66] focus:outline-none rounded px-3 py-2 text-sm text-[#e1e4e8]"
              required
            />
          </div>
          
          {error && (
            <div className="border border-red-500/50 bg-red-900/20 text-red-400 text-xs p-3 rounded flex items-center gap-2">
              ⚠️ {error}
            </div>
          )}
          
          <button 
            type="submit" 
            disabled={loading}
            className="w-full bg-[#00ff66] hover:bg-[#00e55c] transition-colors disabled:opacity-50 text-black font-bold py-2 rounded text-sm uppercase tracking-wider"
          >
            {loading ? "AUTHENTICATING..." : isRegistering ? "Register Account" : "Access System"}
          </button>
        </form>

        <div className="mt-6 text-center text-xs">
          <button 
            onClick={() => setIsRegistering(!isRegistering)}
            className="text-[#8b949e] hover:text-[#00ff66] underline transition-colors"
          >
            {isRegistering ? "Already have an account? Log in" : "Create new Trader credentials"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function TerminalDashboard() {
  // States
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [marketSummary, setMarketSummary] = useState<MarketSummary | null>(null);
  const [screener, setScreener] = useState<ScreenerRow[]>([]);
  const [news, setNews] = useState<NewsArticle[]>([]);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [stockDetail, setStockDetail] = useState<StockDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [sectorFilter, setSectorFilter] = useState("ALL");
  const [countryFilter, setCountryFilter] = useState("ALL");
  const [activeTab, setActiveTab] = useState<"macro" | "micro" | "technical" | "history">("micro");
  const [currentZuluTime, setCurrentZuluTime] = useState("");
  const [chartTab, setChartTab] = useState<"price" | "rsi" | "macd">("price");
  const [backtestBuyRsi, setBacktestBuyRsi] = useState(30);
  const [backtestSellRsi, setBacktestSellRsi] = useState(70);
  const [backtestBuySent, setBacktestBuySent] = useState(0.1);
  const [backtestSellSent, setBacktestSellSent] = useState(-0.1);
  const [backtestResults, setBacktestResults] = useState<any | null>(null);
  const [backtestLoading, setBacktestLoading] = useState(false);
  const [optimizationLoading, setOptimizationLoading] = useState(false);
  const [optimizationResults, setOptimizationResults] = useState<any>(null);
  const [riskAccounts, setRiskAccounts] = useState<any[]>([]);
  const [activeOverrides, setActiveOverrides] = useState<Record<string, any>>({});
  const [signalHistory, setSignalHistory] = useState<any[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [showBollinger, setShowBollinger] = useState(false);
  const [forexScreener, setForexScreener] = useState<ScreenerRow[]>([]);
  const [mt5Clients, setMt5Clients] = useState<any[]>([]);
  const [screenerTab, setScreenerTab] = useState<"stocks" | "forex">("stocks");
  const [brokerAccounts, setBrokerAccounts] = useState<BrokerAccount[]>([]);

  // Risk control state
  const [maxDrawdownPercent, setMaxDrawdownPercent] = useState(5.0);
  const [emergencyKillSwitch, setEmergencyKillSwitch] = useState(false);
  const [currentDrawdownPercent, setCurrentDrawdownPercent] = useState(0.0);
  const [showRiskModal, setShowRiskModal] = useState(false);
  const [riskModalValue, setRiskModalValue] = useState("5.0");

  // Advanced components states
  const [mainTab, setMainTab] = useState<"dashboard" | "risk_telemetry" | "correlation" | "backtest" | "audit_log" | "ai_ml" | "system_logs" | "portfolio_weights" | "hedging" | "live_trading" | "asset_config">("dashboard");
  const [correlationData, setCorrelationData] = useState<{ tickers: string[]; matrix: number[][] } | null>(null);
  const [riskAnalytics, setRiskAnalytics] = useState<{ value_at_risk_95: number; sharpe_ratio: number; sortino_ratio: number; max_drawdown: number; equity_curve: any[] } | null>(null);
  const [stressTest, setStressTest] = useState<{ scenarios: { name: string; max_drawdown: number }[] } | null>(null);
  const [hedgingBeta, setHedgingBeta] = useState<{ index: string; required_short_lots: number; portfolio_value: number; beta: number } | null>(null);
  const [portfolioBacktestResults, setPortfolioBacktestResults] = useState<any | null>(null);
  const [portfolioBacktestLoading, setPortfolioBacktestLoading] = useState(false);
  const [selectedPortfolioTickers, setSelectedPortfolioTickers] = useState<string[]>([]);
  const [telegramBotToken, setTelegramBotToken] = useState("");
  
  // Compliance Audit & ML States
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [auditLogsLoading, setAuditLogsLoading] = useState(false);
  const [mlMetrics, setMlMetrics] = useState<any[]>([]);
  const [mlMetricsLoading, setMlMetricsLoading] = useState(false);
  const [mlRetraining, setMlRetraining] = useState(false);
  const [systemLogs, setSystemLogs] = useState<any[]>([]);
  const [systemLogsLoading, setSystemLogsLoading] = useState(false);
  const [globalPortfolioWeights, setGlobalPortfolioWeights] = useState<any[]>([]);
  const [hedgingStrategies, setHedgingStrategies] = useState<any[]>([]);
  const [livePositions, setLivePositions] = useState<any[]>([]);
  const [executionLogs, setExecutionLogs] = useState<any[]>([]);
  const [tickersConfig, setTickersConfig] = useState<any[]>([]);
  const [newTicker, setNewTicker] = useState({ ticker: "", name: "", country: "USA", sector: "Equities", industry: "" });

  // MVO, WFO, and Monte Carlo States
  const [monteCarloResults, setMonteCarloResults] = useState<any | null>(null);
  const [monteCarloLoading, setMonteCarloLoading] = useState(false);
  const [portfolioWeights, setPortfolioWeights] = useState<Record<string, number> | null>(null);
  const [portfolioWeightsLoading, setPortfolioWeightsLoading] = useState(false);
  const [economicCalendar, setEconomicCalendar] = useState<any[]>([]);
  const [marketRegimes, setMarketRegimes] = useState<any[]>([]);
  const [optMethod, setOptMethod] = useState<"max_sharpe" | "min_volatility">("max_sharpe");
  const [useBL, setUseBL] = useState(true);
  const [wfoResults, setWfoResults] = useState<any[]>([]);
  const [wfoLoading, setWfoLoading] = useState(false);
  const [telegramChatId, setTelegramChatId] = useState("");
  const [discordWebhookUrl, setDiscordWebhookUrl] = useState("");
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [llmSummary, setLlmSummary] = useState("");
  const [llmSummaryLoading, setLlmSummaryLoading] = useState(false);
  const [backtestCapital, setBacktestCapital] = useState(10000);

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      const isoString = now.toISOString();
      const datePart = isoString.substring(0, 10);
      const timePart = isoString.substring(11, 19);
      setCurrentZuluTime(`${datePart} ${timePart} Z`);
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const token = localStorage.getItem("euroquant_token");
    if (token) {
      setIsAuthenticated(true);
    }
    const handleAuthFailed = () => {
      setIsAuthenticated(false);
    };
    window.addEventListener("auth_failed", handleAuthFailed);
    return () => window.removeEventListener("auth_failed", handleAuthFailed);
  }, []);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // Fetch initial data
  const fetchData = async () => {
    try {
      // Fetch market summary
      const marketRes = await fetch(`${API_URL}/api/market-summary`);
      if (marketRes.ok) {
        const data = await marketRes.json();
        setMarketSummary(data);
      }

      // Fetch screener
      const screenerRes = await fetch(`${API_URL}/api/screener`);
      if (screenerRes.ok) {
        const data = await screenerRes.json();
        setScreener(data);
      }

      // Fetch forex screener
      const forexRes = await fetch(`${API_URL}/api/forex/screener`);
      if (forexRes.ok) {
        const data = await forexRes.json();
        setForexScreener(data);
      }

      // Fetch mt5 clients
      const mt5Res = await fetch(`${API_URL}/api/mt5/clients`);
      if (mt5Res.ok) {
        const data = await mt5Res.json();
        setMt5Clients(data);
      }

      // Fetch news
      const newsRes = await fetch(`${API_URL}/api/news`);
      if (newsRes.ok) {
        const data = await newsRes.json();
        setNews(data);
      }

      // Fetch overrides
      const overridesRes = await fetch(`${API_URL}/api/mt5/overrides`);
      if (overridesRes.ok) {
        const data = await overridesRes.json();
        setActiveOverrides(data);
      }

      // Fetch broker accounts
      const accountsRes = await fetch(`${API_URL}/api/mt5/accounts`);
      if (accountsRes.ok) {
        const data = await accountsRes.json();
        setBrokerAccounts(data);
      }

      // Fetch risk settings
      const riskRes = await fetch(`${API_URL}/api/mt5/risk`);
      if (riskRes.ok) {
        const data = await riskRes.json();
        setMaxDrawdownPercent(data.max_drawdown_percent);
        setEmergencyKillSwitch(data.emergency_kill_switch);
        setCurrentDrawdownPercent(data.current_drawdown_percent);
        setRiskModalValue(String(data.max_drawdown_percent));
        if (data.accounts) {
          setRiskAccounts(data.accounts);
        }
      }

      // Fetch system settings
      const settingsRes = await fetch(`${API_URL}/api/system-settings`);
      if (settingsRes.ok) {
        const data = await settingsRes.json();
        setTelegramBotToken(data.telegram_bot_token || "");
        setTelegramChatId(data.telegram_chat_id || "");
        setDiscordWebhookUrl(data.discord_webhook_url || "");
      }

      // Fetch market correlation
      const correlationRes = await fetch(`${API_URL}/api/market-correlation`);
      if (correlationRes.ok) {
        const data = await correlationRes.json();
        setCorrelationData(data);
      }

      // Fetch risk analytics
      const riskAnalyticsRes = await fetch(`${API_URL}/api/mt5/risk-analytics`);
      if (riskAnalyticsRes.ok) {
        const data = await riskAnalyticsRes.json();
        setRiskAnalytics(data);
      }
      
      const stressRes = await fetch(`${API_URL}/api/mt5/stress-test`);
      if (stressRes.ok) {
        setStressTest(await stressRes.json());
      }
      
      const hedgeRes = await fetch(`${API_URL}/api/mt5/hedging/beta`);
      if (hedgeRes.ok) {
        setHedgingBeta(await hedgeRes.json());
      }

      // Fetch economic calendar
      try {
        const calendarRes = await fetch(`${API_URL}/api/economic-calendar`);
        if (calendarRes.ok) {
          const data = await calendarRes.json();
          setEconomicCalendar(data);
        }
      } catch (err) {
        console.error("Error fetching calendar:", err);
      }

      // Fetch market regimes
      try {
        const regimesRes = await fetch(`${API_URL}/api/market-regimes`);
        if (regimesRes.ok) {
          const data = await regimesRes.json();
          setMarketRegimes(data);
        }
      } catch (err) {
        console.error("Error fetching regimes:", err);
      }

      // Fetch portfolio weights
      try {
        const weightsRes = await fetch(`${API_URL}/api/portfolio/weights`);
        if (weightsRes.ok) {
          const data = await weightsRes.json();
          setPortfolioWeights(data);
        }
      } catch (err) {
        console.error("Error fetching portfolio weights:", err);
      }
    } catch (error) {
      console.error("Error fetching dashboard data:", error);
    }
  };

  const fetchLiveTrading = async () => {
    try {
      const token = localStorage.getItem("euroquant_token");
      if (token) {
        const resPos = await fetch("http://localhost:8000/api/live-positions", {
          headers: { Authorization: `Bearer ${token}` }
        });
        const posData = await resPos.json();
        setLivePositions(posData.positions || []);
        
        const resLogs = await fetch("http://localhost:8000/api/execution-logs", {
          headers: { Authorization: `Bearer ${token}` }
        });
        const logData = await resLogs.json();
        setExecutionLogs(logData.logs || []);
      }
    } catch (error) {
      console.error("Error fetching live trading data:", error);
    }
  };

  useEffect(() => {
    if (mainTab === "live_trading") {
      fetchLiveTrading();
    } else if (mainTab === "asset_config") {
      fetchTickersConfig();
    }
  }, [mainTab]);

  const fetchTickersConfig = async () => {
    try {
      const token = localStorage.getItem("euroquant_token");
      if (token) {
        const res = await fetch("http://localhost:8000/api/tickers", {
          headers: { Authorization: `Bearer ${token}` }
        });
        const data = await res.json();
        setTickersConfig(data || []);
      }
    } catch (error) {
      console.error("Error fetching tickers config:", error);
    }
  };

  const toggleTickerStatus = async (ticker: string, currentStatus: boolean) => {
    try {
      const token = localStorage.getItem("euroquant_token");
      if (token) {
        await fetch("http://localhost:8000/api/tickers/toggle", {
          method: "POST",
          headers: { 
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}` 
          },
          body: JSON.stringify({ ticker, is_active: !currentStatus })
        });
        fetchTickersConfig();
      }
    } catch (error) {
      console.error("Error toggling ticker status:", error);
    }
  };

  const submitNewTicker = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const token = localStorage.getItem("euroquant_token");
      if (token) {
        const res = await fetch("http://localhost:8000/api/tickers/add", {
          method: "POST",
          headers: { 
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}` 
          },
          body: JSON.stringify(newTicker)
        });
        if (res.ok) {
          setNewTicker({ ticker: "", name: "", country: "USA", sector: "Equities", industry: "" });
          fetchTickersConfig();
        } else {
          const err = await res.json();
          alert("Errore: " + err.detail);
        }
      }
    } catch (error) {
      console.error("Error adding new ticker:", error);
    }
  };

  const fetchHedgingStrategies = async () => {
    try {
      const token = localStorage.getItem("euroquant_token");
      if (token) {
        const res = await fetch("http://localhost:8000/api/hedging-strategies", {
          headers: { Authorization: `Bearer ${token}` }
        });
        const data = await res.json();
        setHedgingStrategies(data.strategies || []);
      }
    } catch (error) {
      console.error("Error fetching hedging strategies:", error);
    }
  };

  const fetchPortfolioWeights = async () => {
    try {
      const token = localStorage.getItem("euroquant_token");
      if (token) {
        const res = await fetch("http://localhost:8000/api/portfolio-weights", {
          headers: { Authorization: `Bearer ${token}` }
        });
        const data = await res.json();
        setGlobalPortfolioWeights(data.weights || []);
      }
    } catch (error) {
      console.error("Error fetching portfolio weights:", error);
    }
  };

  const fetchSystemLogs = async () => {
    try {
      const token = localStorage.getItem("euroquant_token");
      const res = await fetch(`${API_URL}/api/system-logs?limit=200`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setSystemLogs(data);
      }
    } catch (err) {
      console.error("Error fetching system logs:", err);
    }
  };

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (mainTab === "system_logs") {
      fetchSystemLogs();
      interval = setInterval(fetchSystemLogs, 3000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [mainTab]);

  const fetchAuditLogs = async () => {
    setAuditLogsLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/audit-log?limit=200`);
      if (res.ok) {
        const data = await res.json();
        setAuditLogs(data);
      }
    } catch (err) {
      console.error("Error fetching audit logs:", err);
    } finally {
      setAuditLogsLoading(false);
    }
  };

  const fetchMlMetrics = async () => {
    setMlMetricsLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/ml/metrics`);
      if (res.ok) {
        const data = await res.json();
        setMlMetrics(data);
      }
    } catch (err) {
      console.error("Error fetching ML metrics:", err);
    } finally {
      setMlMetricsLoading(false);
    }
  };

  const triggerMlRetrain = async () => {
    setMlRetraining(true);
    try {
      const res = await fetch(`${API_URL}/api/ml/retrain`, { method: "POST" });
      if (res.ok) {
        alert("Retrain dei modelli ML avviato in background con successo!");
        setTimeout(fetchMlMetrics, 2000);
      } else {
        alert("Errore durante l'avvio del retrain dei modelli.");
      }
    } catch (err) {
      console.error("Error triggering ML retrain:", err);
      alert("Errore di rete durante l'avvio del retrain.");
    } finally {
      setMlRetraining(false);
    }
  };

  useEffect(() => {
    if (!isAuthenticated) return;
    if (mainTab === "audit_log") {
      fetchAuditLogs();
    } else if (mainTab === "ai_ml") {
      fetchMlMetrics();
    }
  }, [mainTab, isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated) return;
    fetchData();
    const interval = setInterval(fetchData, 60000);
    
    const eventSource = new EventSource(`${API_URL}/api/events`);
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data && data.forex) {
          setMarketSummary((prev) => {
            if (!prev) return prev;
            return { ...prev, forex: data.forex };
          });
        }
      } catch (err) {
        console.error("SSE parsing error:", err);
      }
    };

    // WebSocket real-time client
    const wsUrl = `${API_URL.replace("http://", "ws://").replace("https://", "wss://")}/ws/telemetry`;
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "telemetry_update" || msg.type === "overrides_update" || msg.type === "risk_update") {
          fetchData();
        }
      } catch (err) {
        console.error("WS parsing error:", err);
      }
    };
    
    return () => {
      clearInterval(interval);
      eventSource.close();
      ws.close();
    };
  }, [isAuthenticated]);

  // Fetch Monte Carlo simulations on tab shift
  useEffect(() => {
    if (!isAuthenticated || mainTab !== "risk_telemetry") return;
    if (mainTab === "risk_telemetry") {
      const fetchMonteCarlo = async () => {
        setMonteCarloLoading(true);
        try {
          const res = await fetch(`${API_URL}/api/portfolio/monte-carlo`);
          if (res.ok) {
            const data = await res.json();
            setMonteCarloResults(data);
          }
        } catch (err) {
          console.error("Monte Carlo error:", err);
        } finally {
          setMonteCarloLoading(false);
        }
      };
      fetchMonteCarlo();
    }
  }, [mainTab]);

  // Fetch stock details when ticker is selected
  useEffect(() => {
    if (!isAuthenticated) return;
    setBacktestResults(null);
    setChartTab("price");
    if (!selectedTicker) {
      setStockDetail(null);
      return;
    }

    const fetchStockDetail = async () => {
      setDetailLoading(true);
      try {
        const res = await fetch(`${API_URL}/api/stock/${selectedTicker}`);
        if (res.ok) {
          const data = await res.json();
          setStockDetail(data);
          // Set default tab based on signal or macro risk
          if (data.reason_micro) setActiveTab("micro");
          else if (data.reason_macro) setActiveTab("macro");
        }
      } catch (error) {
        console.error(`Error fetching detail for ${selectedTicker}:`, error);
      } finally {
        setDetailLoading(false);
      }
    };

    const fetchSignalHistory = async () => {
      setHistoryLoading(true);
      try {
        const res = await fetch(`${API_URL}/api/recommendations/history?ticker=${selectedTicker}`);
        if (res.ok) {
          const data = await res.json();
          setSignalHistory(data);
        }
      } catch (err) {
        console.error("Error fetching signal history:", err);
      } finally {
        setHistoryLoading(false);
      }
    };

    const fetchLlmSummary = async () => {
      setLlmSummary("");
      setLlmSummaryLoading(true);
      try {
        const res = await fetch(`${API_URL}/api/stock/${selectedTicker}/summary`);
        if (res.ok) {
          const data = await res.json();
          setLlmSummary(data.summary || "");
        }
      } catch (err) {
        console.error("Error fetching LLM summary:", err);
      } finally {
        setLlmSummaryLoading(false);
      }
    };

    fetchStockDetail();
    fetchSignalHistory();
    fetchLlmSummary();
  }, [selectedTicker]);

  // Trigger manual backend worker sync
  const triggerSync = async () => {
    setSyncing(true);
    setSyncStatus("Invio richiesta sincronizzazione in corso...");
    try {
      const res = await fetch(`${API_URL}/api/trigger-job`, { method: "POST" });
      if (res.ok) {
        setSyncStatus("Worker avviato. Download prezzi e analisi news in tempo reale...");
        
        // Poll backend for updates
        let attempts = 0;
        const checkInterval = setInterval(async () => {
          attempts++;
          const checkRes = await fetch(`${API_URL}/api/screener`);
          if (checkRes.ok) {
            const data = await checkRes.json();
            // If we have data, we assume it's updated or ready
            if (data.length > 0 || attempts > 10) {
              setScreener(data);
              await fetchData(); // refresh everything
              setSyncStatus("Sincronizzazione completata con successo!");
              clearInterval(checkInterval);
              setTimeout(() => {
                setSyncing(false);
                setSyncStatus(null);
              }, 3000);
            }
          }
        }, 5000);
      } else {
        setSyncStatus("Errore nell'avvio del worker.");
        setTimeout(() => setSyncing(false), 3000);
      }
    } catch (error) {
      setSyncStatus("Errore di connessione.");
      setTimeout(() => setSyncing(false), 3000);
    }
  };

  const toggleEmergencyKillSwitch = async () => {
    const nextState = !emergencyKillSwitch;
    try {
      const res = await fetch(`${API_URL}/api/mt5/risk/kill-switch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active: nextState })
      });
      if (res.ok) {
        setEmergencyKillSwitch(nextState);
      }
    } catch (err) {
      console.error("Failed to toggle emergency kill-switch:", err);
    }
  };

  const saveRiskSettings = async () => {
    try {
      const res = await fetch(`${API_URL}/api/mt5/risk`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ max_drawdown_percent: Number(riskModalValue) })
      });
      if (res.ok) {
        setMaxDrawdownPercent(Number(riskModalValue));
        setShowRiskModal(false);
      }
    } catch (err) {
      console.error("Failed to save risk settings:", err);
    }
  };

  const updateAccountRiskLimit = async (accountId: string, maxDd: number) => {
    try {
      const res = await fetch(`${API_URL}/api/mt5/accounts/${accountId}/risk`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ max_drawdown_percent: maxDd })
      });
      if (res.ok) {
        fetchData();
      }
    } catch (err) {
      console.error("Failed to update account risk limit:", err);
    }
  };


  const optimizeParameters = async () => {
    if (!selectedTicker) return;
    setOptimizationLoading(true);
    setOptimizationResults(null);
    try {
      const res = await fetch(`${API_URL}/api/backtest/optimize`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ ticker: selectedTicker }),
      });
      if (res.ok) {
        const data = await res.json();
        setOptimizationResults(data);
      }
    } catch (error) {
      console.error("Optimization failed:", error);
    } finally {
      setOptimizationLoading(false);
    }
  };

  const saveAccountRisk = async (accountId: string, limit: number) => {
    try {
      const res = await fetch(`${API_URL}/api/mt5/accounts/${accountId}/risk`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ max_drawdown_percent: limit })
      });
      if (res.ok) {
        fetchData();
      }
    } catch (error) {
      console.error("Failed to save account risk:", error);
    }
  };

  const runBacktest = async () => {
    if (!selectedTicker) return;
    setBacktestLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/backtest`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          ticker: selectedTicker,
          buy_rsi: Number(backtestBuyRsi),
          sell_rsi: Number(backtestSellRsi),
          buy_sentiment: Number(backtestBuySent),
          sell_sentiment: Number(backtestSellSent),
          initial_capital: Number(backtestCapital),
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setBacktestResults(data);
      }
    } catch (error) {
      console.error("Backtest execution failed:", error);
    } finally {
      setBacktestLoading(false);
    }
  };

  const handleSetOverride = async (ticker: string, action: string) => {
    try {
      const res = await fetch(`${API_URL}/api/mt5/overrides`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, action })
      });
      if (res.ok) {
        const data = await res.json();
        setActiveOverrides(data.overrides);
        
        // Refetch screener and current stock details immediately
        fetchData();
        const detailRes = await fetch(`${API_URL}/api/stock/${ticker}`);
        if (detailRes.ok) {
          const detailData = await detailRes.json();
          setStockDetail(detailData);
        }
      }
    } catch (error) {
      console.error("Error setting override:", error);
    }
  };

  const getChartData = () => {
    if (!stockDetail || !stockDetail.history) return [];
    return stockDetail.history.map((row, idx, arr) => {
      let bb_upper: number | null = null;
      let bb_lower: number | null = null;
      
      if (idx >= 19) {
        const period = arr.slice(idx - 19, idx + 1);
        const closes = period.map(r => r.close);
        const mean = closes.reduce((sum, val) => sum + val, 0) / 20;
        const squareDiffs = closes.map(val => Math.pow(val - mean, 2));
        const avgSquareDiff = squareDiffs.reduce((sum, val) => sum + val, 0) / 20;
        const stdDev = Math.sqrt(avgSquareDiff);
        
        const base_sma = row.sma_20 ? Number(row.sma_20) : mean;
        bb_upper = base_sma + 2 * stdDev;
        bb_lower = base_sma - 2 * stdDev;
      }
      
      return {
        ...row,
        bb_upper,
        bb_lower
      };
    });
  };

  // Filters
  const filteredScreener = screener.filter(item => {
    const matchesSearch = item.ticker.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          item.name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesSector = sectorFilter === "ALL" || item.sector === sectorFilter;
    const matchesCountry = countryFilter === "ALL" || item.country === countryFilter;
    return matchesSearch && matchesSector && matchesCountry;
  });

  const filteredForex = forexScreener.filter(item => {
    const matchesSearch = item.ticker.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          item.name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSearch;
  });

  // Unique lists for dropdowns
  const sectors = ["ALL", ...Array.from(new Set(screener.map(i => i.sector)))];
  const countries = ["ALL", ...Array.from(new Set(screener.map(i => i.country)))];

  // Helper for sentiment colors
  const getSentimentBg = (score: number) => {
    if (score > 0.4) return "bg-emerald-950/40 text-emerald-400 border border-emerald-500/30";
    if (score > 0.1) return "bg-green-950/20 text-green-300 border border-green-500/20";
    if (score < -0.4) return "bg-red-950/40 text-red-400 border border-red-500/30";
    if (score < -0.1) return "bg-amber-950/20 text-amber-300 border border-amber-500/20";
    return "bg-slate-900 text-slate-400 border border-slate-700/30";
  };

  const getHeatmapColor = (score: number) => {
    if (score > 0.4) return "bg-emerald-600 text-black font-bold";
    if (score > 0.1) return "bg-emerald-800 text-emerald-100";
    if (score < -0.4) return "bg-rose-600 text-black font-bold";
    if (score < -0.1) return "bg-rose-800 text-rose-100";
    return "bg-slate-800 text-slate-300";
  };

  // Signal Badge Styles
  const getSignalBadge = (signal: string) => {
    switch(signal.toUpperCase()) {
      case "STRONG BUY":
        return "bg-emerald-500 text-black font-extrabold shadow-[0_0_10px_rgba(16,185,129,0.5)] border border-emerald-400";
      case "BUY":
        return "bg-emerald-800 text-emerald-100 font-bold border border-emerald-700";
      case "SELL":
        return "bg-rose-800 text-rose-100 font-bold border border-rose-700";
      case "STRONG SELL":
        return "bg-rose-500 text-black font-extrabold shadow-[0_0_10px_rgba(239,68,68,0.5)] border border-rose-400";
      default:
        return "bg-slate-700 text-slate-200 border border-slate-600";
    }
  };

  // Group screener items by country for heatmap representation
  const companiesByCountry: { [key: string]: ScreenerRow[] } = {};
  screener.forEach(item => {
    if (!companiesByCountry[item.country]) {
      companiesByCountry[item.country] = [];
    }
    companiesByCountry[item.country].push(item);
  });

  if (!isAuthenticated) {
    return <LoginScreen onLogin={() => setIsAuthenticated(true)} API_URL={API_URL} />;
  }

  return (
    <div className="min-h-screen grid-terminal bg-terminal-bg flex flex-col p-3">
      {/* 1. Header & Live Ribbons */}
      <header className="flex flex-col md:flex-row md:items-center justify-between border-b border-terminal-border pb-3 mb-3 gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-terminal-accent text-black flex items-center justify-center font-bold text-xl rounded">
            EQ
          </div>
          <div>
            <h1 className="text-terminal-accent font-black tracking-wider text-xl flex items-center gap-2">
              🏛️ EUROQUANT <span className="text-terminal-muted text-sm font-normal">INSTITUTIONAL TERMINAL V1.0</span>
            </h1>
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 text-xs text-terminal-muted">
              <span>Real-time European Sentiment Engine & Quantitative screener</span>
              {currentZuluTime && (
                <span className="text-terminal-accent font-mono font-bold bg-terminal-accent/10 px-2 py-0.5 rounded border border-terminal-accent/20">
                  ⏱️ UTC/ZULU: {currentZuluTime}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Volatility Indicator */}
        {marketSummary && (
          <div className={`px-4 py-2 rounded border flex items-center gap-3 text-xs max-w-md ${
            marketSummary.v2tx.status === "RISK_WARNING" 
              ? "bg-rose-950/40 text-rose-400 border-rose-600" 
              : marketSummary.v2tx.status === "ELEVATED"
              ? "bg-amber-950/40 text-amber-400 border-amber-600"
              : "bg-emerald-950/40 text-emerald-400 border-emerald-600"
          }`}>
            <Activity className="h-5 w-5 animate-pulse shrink-0" />
            <div>
              <div className="font-bold flex items-center gap-2">
                VSTOXX (V2TX): {marketSummary.v2tx.price.toFixed(2)}
                <span className="font-black">[{marketSummary.v2tx.status}]</span>
              </div>
              <p className="text-slate-400 leading-tight">{marketSummary.v2tx.message}</p>
            </div>
          </div>
        )}

        <div className="flex items-center gap-2">
          {/* Risk Limit Controller */}
          <button
            onClick={() => setShowRiskModal(true)}
            className="px-3 py-2 text-[10px] font-bold uppercase rounded border border-terminal-border bg-terminal-card text-slate-300 hover:border-terminal-accent hover:text-terminal-accent transition flex items-center gap-1.5"
          >
            🛡️ RISCHIO: {maxDrawdownPercent}% DD
          </button>

          {/* Emergency Kill Switch */}
          <button
            onClick={toggleEmergencyKillSwitch}
            className={`px-3 py-2 text-[10px] font-bold uppercase rounded border transition flex items-center gap-1.5 ${
              emergencyKillSwitch 
                ? "bg-rose-600 border-rose-500 text-white hover:bg-rose-700 animate-pulse shadow-[0_0_12px_rgba(239,68,68,0.5)]" 
                : "bg-terminal-card border-rose-950 text-rose-500 hover:bg-rose-950/30 hover:border-rose-700 transition"
            }`}
          >
            🚨 {emergencyKillSwitch ? "BLOCCO ATTIVO" : "KILL-SWITCH"}
          </button>
          
          {/* AI Circuit Breaker (Auto) */}
          {marketSummary?.global_circuit_breaker && (
            <div className="px-3 py-2 text-[10px] font-bold uppercase rounded border border-rose-500 bg-rose-600/20 text-rose-400 flex items-center gap-1.5 animate-pulse">
              ⚠️ AI CIRCUIT BREAKER ON
            </div>
          )}

          {/* Sync Trigger */}
          <button
            onClick={triggerSync}
            disabled={syncing}
            className={`px-3 py-2 text-[10px] font-bold uppercase rounded border transition flex items-center gap-1.5 ${
              syncing 
                ? "bg-terminal-card border-terminal-border text-terminal-muted cursor-not-allowed" 
                : "bg-terminal-accent/10 border-terminal-accent text-terminal-accent hover:bg-terminal-accent hover:text-black shadow-[0_0_8px_rgba(255,153,0,0.2)]"
            }`}
          >
            <RefreshCw className={`h-3 w-3 ${syncing ? "animate-spin" : ""}`} />
            {syncing ? "RUNNING..." : "RUN SYNC"}
          </button>
        </div>
      </header>

      {/* Risk Alert Banner */}
      {(emergencyKillSwitch || currentDrawdownPercent > maxDrawdownPercent) && (
        <div className="bg-rose-950/85 border border-rose-600 text-rose-200 px-4 py-3 text-xs mb-3 flex flex-col md:flex-row md:items-center justify-between gap-3 rounded shadow-lg animate-pulse">
          <div className="flex items-center gap-2 font-black tracking-wider uppercase text-rose-400">
            <span>⚠️ BLOCCO OPERATIVO ATTIVO (CLOSE_ALL)</span>
          </div>
          <div>
            {emergencyKillSwitch 
              ? "L'interruttore di emergenza globale (Kill-Switch) è attivo." 
              : `Il drawdown massimo consentito (${maxDrawdownPercent}%) è stato superato (drawdown corrente: ${currentDrawdownPercent}%).`} Tutti gli EA riceveranno l'ordine di chiusura immediata delle posizioni.
          </div>
        </div>
      )}

      {/* Sync Status Overlay */}
      {syncStatus && (
        <div className="bg-terminal-card border border-terminal-accent/30 text-terminal-accent px-4 py-2 text-xs mb-3 flex items-center gap-2 rounded shadow-md">
          <Cpu className="h-4 w-4 animate-pulse shrink-0" />
          <span>{syncStatus}</span>
        </div>
      )}

      {/* Index Ticker Ribbon */}
      {marketSummary && (
        <div className="bg-terminal-card border border-terminal-border p-2 mb-2 rounded flex items-center overflow-x-auto whitespace-nowrap text-xs gap-6 scrollbar-none">
          <span className="text-terminal-accent font-bold tracking-wider shrink-0 border-r border-terminal-border pr-4">INDEX MONITOR:</span>
          {marketSummary.indices.map((idx) => (
            <div key={idx.ticker} className="flex items-center gap-2 shrink-0">
              <span className="text-slate-400 font-bold">{idx.name}</span>
              <span className="font-bold">{idx.price.toLocaleString("de-DE", { minimumFractionDigits: 2 })}</span>
              <span className={`flex items-center gap-0.5 ${idx.change_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {idx.change_pct >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                {idx.change_pct >= 0 ? "+" : ""}{idx.change_pct.toFixed(2)}%
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Forex Ticker Ribbon */}
      {marketSummary && marketSummary.forex && (
        <div className="bg-terminal-card border border-terminal-border p-2 mb-2 rounded flex items-center overflow-x-auto whitespace-nowrap text-xs gap-6 scrollbar-none">
          <span className="text-terminal-accent font-bold tracking-wider shrink-0 border-r border-terminal-border pr-4">FOREX MONITOR:</span>
          {marketSummary.forex.map((fx) => (
            <div key={fx.ticker} className="flex items-center gap-2 shrink-0">
              <span className="text-slate-400 font-bold">{fx.name}</span>
              <span className="font-mono font-bold">{fx.price.toFixed(4)}</span>
              <span className={`flex items-center gap-0.5 ${fx.change_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {fx.change_pct >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                {fx.change_pct >= 0 ? "+" : ""}{fx.change_pct.toFixed(2)}%
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Metals Ticker Ribbon */}
      {marketSummary && marketSummary.metals && (
        <div className="bg-terminal-card border border-terminal-border p-2 mb-2 rounded flex items-center overflow-x-auto whitespace-nowrap text-xs gap-6 scrollbar-none">
          <span className="text-terminal-accent font-bold tracking-wider shrink-0 border-r border-terminal-border pr-4">METALS (SAFE HAVEN):</span>
          {marketSummary.metals.map((mtl) => (
            <div key={mtl.ticker} className="flex items-center gap-2 shrink-0">
              <span className="text-amber-400 font-bold">{mtl.name}</span>
              <span className="font-mono font-bold">{mtl.price.toFixed(2)}</span>
              <span className={`flex items-center gap-0.5 ${mtl.change_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {mtl.change_pct >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                {mtl.change_pct >= 0 ? "+" : ""}{mtl.change_pct.toFixed(2)}%
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Crypto Ticker Ribbon */}
      {marketSummary && marketSummary.crypto && (
        <div className="bg-terminal-card border border-terminal-border p-2 mb-4 rounded flex items-center overflow-x-auto whitespace-nowrap text-xs gap-6 scrollbar-none">
          <span className="text-terminal-accent font-bold tracking-wider shrink-0 border-r border-terminal-border pr-4">CRYPTO MONITOR:</span>
          {marketSummary.crypto.map((crp) => (
            <div key={crp.ticker} className="flex items-center gap-2 shrink-0">
              <span className="text-violet-400 font-bold">{crp.name}</span>
              <span className="font-mono font-bold">{crp.price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
              <span className={`flex items-center gap-0.5 ${crp.change_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {crp.change_pct >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                {crp.change_pct >= 0 ? "+" : ""}{crp.change_pct.toFixed(2)}%
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Main Tab Navigation */}
      <div className="flex border border-terminal-border mb-3 bg-terminal-card rounded p-1 gap-1 shrink-0">
        <button
          onClick={() => setMainTab("dashboard")}
          className={`flex-1 py-1.5 text-xs font-black uppercase rounded tracking-wider transition ${
            mainTab === "dashboard"
              ? "bg-terminal-accent text-black font-extrabold shadow-[0_0_8px_rgba(255,153,0,0.3)]"
              : "text-slate-400 hover:text-white hover:bg-terminal-bg/50"
          }`}
        >
          📊 Dashboard Monitor
        </button>
        <button
          onClick={() => setMainTab("risk_telemetry")}
          className={`flex-1 py-1.5 text-xs font-black uppercase rounded tracking-wider transition ${
            mainTab === "risk_telemetry"
              ? "bg-terminal-accent text-black font-extrabold shadow-[0_0_8px_rgba(255,153,0,0.3)]"
              : "text-slate-400 hover:text-white hover:bg-terminal-bg/50"
          }`}
        >
          🛡️ Risk & Telemetry
        </button>
        <button
          onClick={() => setMainTab("correlation")}
          className={`flex-1 py-1.5 text-xs font-black uppercase rounded tracking-wider transition ${
            mainTab === "correlation"
              ? "bg-terminal-accent text-black font-extrabold shadow-[0_0_8px_rgba(255,153,0,0.3)]"
              : "text-slate-400 hover:text-white hover:bg-terminal-bg/50"
          }`}
        >
          🧮 Correlation Heatmap
        </button>
        <button
          onClick={() => setMainTab("backtest")}
          className={`flex-1 py-1.5 text-xs font-black uppercase rounded tracking-wider transition ${
            mainTab === "backtest"
              ? "bg-terminal-accent text-black font-extrabold shadow-[0_0_8px_rgba(255,153,0,0.3)]"
              : "text-slate-400 hover:text-white hover:bg-terminal-bg/50"
          }`}
        >
          🚀 Portfolio Backtest
        </button>
        <button
          onClick={() => setMainTab("ai_ml")}
          className={`flex-1 py-1.5 text-xs font-black uppercase rounded tracking-wider transition ${
            mainTab === "ai_ml"
              ? "bg-terminal-accent text-black font-extrabold shadow-[0_0_8px_rgba(255,153,0,0.3)]"
              : "text-slate-400 hover:text-white hover:bg-terminal-bg/50"
          }`}
        >
          🧠 AI/ML Engine
        </button>
        <button
          onClick={() => setMainTab("audit_log")}
          className={`flex-1 py-1.5 text-xs font-black uppercase rounded tracking-wider transition ${
            mainTab === "audit_log"
              ? "bg-terminal-accent text-black font-extrabold shadow-[0_0_8px_rgba(255,153,0,0.3)]"
              : "text-slate-400 hover:text-white hover:bg-terminal-bg/50"
          }`}
        >
          🔐 Compliance Audit
        </button>
        <button
          onClick={() => setMainTab("system_logs")}
          className={`flex-1 py-1.5 text-xs font-black uppercase rounded tracking-wider transition ${
            mainTab === "system_logs"
              ? "bg-terminal-accent text-black font-extrabold shadow-[0_0_8px_rgba(255,153,0,0.3)]"
              : "text-slate-400 hover:text-white hover:bg-terminal-bg/50"
          }`}
        >
          🖥️ Docker Logs
        </button>
        <button
          onClick={() => setMainTab("portfolio_weights")}
          className={`flex-1 py-1.5 text-xs font-black uppercase rounded tracking-wider transition ${
            mainTab === "portfolio_weights"
              ? "bg-terminal-accent text-black font-extrabold shadow-[0_0_8px_rgba(255,153,0,0.3)]"
              : "text-slate-400 hover:text-white hover:bg-terminal-bg/50"
          }`}
        >
          <PieChart className="inline h-3 w-3 mr-1" /> Weights
        </button>
        <button
          onClick={() => setMainTab("hedging")}
          className={`flex-1 py-1.5 text-xs font-black uppercase rounded tracking-wider transition ${
            mainTab === "hedging"
              ? "bg-terminal-accent text-black font-extrabold shadow-[0_0_8px_rgba(255,153,0,0.3)]"
              : "text-slate-400 hover:text-white hover:bg-terminal-bg/50"
          }`}
        >
          <ShieldAlert className="inline h-3 w-3 mr-1" /> Hedging
        </button>
        <button
          onClick={() => setMainTab("live_trading")}
          className={`flex-1 py-1.5 text-xs font-black uppercase rounded tracking-wider transition ${
            mainTab === "live_trading"
              ? "bg-red-500 text-white font-extrabold shadow-[0_0_8px_rgba(239,68,68,0.5)]"
              : "text-red-400/70 hover:text-red-400 hover:bg-red-500/10"
          }`}
        >
          <Crosshair className="inline h-3 w-3 mr-1 animate-pulse" /> LIVE TRADING
        </button>
        <button
          onClick={() => setMainTab("asset_config")}
          className={`flex-1 py-1.5 text-xs font-black uppercase rounded tracking-wider transition ${
            mainTab === "asset_config"
              ? "bg-[#00ff66] text-black font-extrabold shadow-[0_0_8px_rgba(0,255,102,0.3)]"
              : "text-slate-400 hover:text-white hover:bg-terminal-bg/50"
          }`}
        >
          <Search className="inline h-3 w-3 mr-1" /> Asset Config
        </button>
      </div>

      {mainTab === "dashboard" && (
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-3 flex-1">
        
        {/* Left 3 columns: Heatmap & Screener */}
        <div className="xl:col-span-3 flex flex-col gap-3">
          
          {/* A. Heatmap Section */}
          <div className="bg-terminal-card border border-terminal-border p-4 rounded">
            <div className="flex items-center justify-between mb-3 border-b border-terminal-border pb-2">
              <h2 className="text-xs font-black uppercase text-slate-400 flex items-center gap-2">
                <Globe className="h-4 w-4 text-terminal-accent" /> Europe Heatmap (Sentiment Aggregation)
              </h2>
              <div className="text-[10px] text-terminal-muted flex gap-2">
                <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 bg-emerald-600 inline-block"></span> Bullish (&gt;0.4)</span>
                <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 bg-emerald-800 inline-block"></span> Mild Bull</span>
                <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 bg-slate-800 inline-block"></span> Neutral</span>
                <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 bg-rose-800 inline-block"></span> Mild Bear</span>
                <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 bg-rose-600 inline-block"></span> Bearish (&lt;-0.4)</span>
              </div>
            </div>

            {screener.length === 0 ? (
              <div className="h-40 flex items-center justify-center text-xs text-terminal-muted">
                Nessun dato caricato. Esegui la sincronizzazione per popolare il database.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
                {Object.keys(companiesByCountry).map((country) => (
                  <div key={country} className="border border-terminal-border p-2 rounded bg-terminal-bg/50">
                    <h3 className="text-[10px] font-black uppercase text-terminal-accent mb-2 tracking-wider flex items-center gap-1">
                      {country === "Italy" ? "🇮🇹 ITALY" :
                       country === "France" ? "🇫🇷 FRANCE" :
                       country === "Germany" ? "🇩🇪 GERMANY" :
                       country === "Spain" ? "🇪🇸 SPAIN" :
                       country === "United Kingdom" ? "🇬🇧 UK" :
                       country === "USA" ? "🇺🇸 USA" :
                       country === "Japan" ? "🇯🇵 JAPAN" :
                       country === "Hong Kong" ? "🇭🇰 HK" :
                       country === "South Korea" ? "🇰🇷 KOREA" :
                       country === "Taiwan" ? "🇹🇼 TAIWAN" : 
                       country === "Crypto" ? "🪙 CRYPTO" : country.toUpperCase()}
                    </h3>
                    <div className="grid grid-cols-2 gap-1.5">
                      {companiesByCountry[country].map((stock) => (
                        <button
                          key={stock.ticker}
                          onClick={() => setSelectedTicker(stock.ticker)}
                          className={`p-2 rounded text-[10px] text-left transition flex flex-col justify-between h-14 border border-terminal-border/20 ${getHeatmapColor(stock.sentiment_score)} hover:scale-105 hover:shadow-md duration-150`}
                        >
                          <span className="font-extrabold">{stock.ticker.split('.')[0]}</span>
                          <div className="flex items-center justify-between w-full mt-1">
                            <span className="text-[9px] opacity-80">{stock.price_change_24h >= 0 ? "+" : ""}{stock.price_change_24h.toFixed(1)}%</span>
                            <span className="font-mono text-[9px] bg-black/40 px-1 rounded font-bold">
                              {stock.sentiment_score >= 0 ? "+" : ""}{stock.sentiment_score.toFixed(2)}
                            </span>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* B. Screener Section */}
          <div className="bg-terminal-card border border-terminal-border p-4 rounded flex-1 flex flex-col">
            <div className="flex flex-col md:flex-row md:items-center justify-between mb-3 border-b border-terminal-border pb-3 gap-2">
              <div className="flex items-center gap-3">
                <h2 className="text-xs font-black uppercase text-slate-400 flex items-center gap-2">
                  <Award className="h-4 w-4 text-terminal-accent" /> Alpha Generator Screener
                </h2>
                <div className="flex border border-terminal-border rounded overflow-hidden text-[9px] uppercase font-bold">
                  <button
                    onClick={() => setScreenerTab("stocks")}
                    className={`px-2.5 py-1 transition ${screenerTab === "stocks" ? "bg-terminal-accent text-black" : "bg-terminal-bg text-slate-400 hover:text-terminal-text"}`}
                  >
                    European Stocks
                  </button>
                  <button
                    onClick={() => setScreenerTab("forex")}
                    className={`px-2.5 py-1 transition ${screenerTab === "forex" ? "bg-terminal-accent text-black" : "bg-terminal-bg text-slate-400 hover:text-terminal-text"}`}
                  >
                    Forex Pairs
                  </button>
                </div>
              </div>
              
              {/* Filters Panel */}
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <div className="relative shrink-0">
                  <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-terminal-muted" />
                  <input
                    type="text"
                    placeholder="Cerca ticker/nome..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="bg-terminal-bg border border-terminal-border text-terminal-text pl-8 pr-2.5 py-1.5 rounded text-xs focus:outline-none focus:border-terminal-accent w-40"
                  />
                </div>
                
                {screenerTab === "stocks" && (
                  <>
                    <select
                      value={sectorFilter}
                      onChange={(e) => setSectorFilter(e.target.value)}
                      className="bg-terminal-bg border border-terminal-border text-terminal-text py-1.5 px-2 rounded text-xs focus:outline-none focus:border-terminal-accent"
                    >
                      <option value="ALL">Settore: ALL</option>
                      {sectors.filter(s => s !== "ALL").map(sec => (
                        <option key={sec} value={sec}>{sec}</option>
                      ))}
                    </select>

                    <select
                      value={countryFilter}
                      onChange={(e) => setCountryFilter(e.target.value)}
                      className="bg-terminal-bg border border-terminal-border text-terminal-text py-1.5 px-2 rounded text-xs focus:outline-none focus:border-terminal-accent"
                    >
                      <option value="ALL">Paese: ALL</option>
                      {countries.filter(c => c !== "ALL").map(c => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  </>
                )}
              </div>
            </div>

            <div className="overflow-y-auto max-h-[360px] flex-1">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-terminal-border text-terminal-muted">
                    <th className="py-2 font-black">COMPANY / TICKER</th>
                    <th className="py-2 font-black">PAESE</th>
                    <th className="py-2 font-black">SETTORE</th>
                    <th className="py-2 font-black text-right">PREZZO</th>
                    <th className="py-2 font-black text-right">VAR. 24H</th>
                    <th className="py-2 font-black text-center">DEC. SENTIMENT</th>
                    <th className="py-2 font-black text-center">AI SIGNAL</th>
                    <th className="py-2 font-black text-center">ML CONF.</th>
                    <th className="py-2 font-black text-center">AZIONE</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-terminal-border/40">
                  {screenerTab === "stocks" ? (
                    filteredScreener.map((row) => (
                      <tr key={row.ticker} className="hover:bg-terminal-bg/50 transition">
                        <td className="py-2.5 font-bold">
                          <div>{row.name}</div>
                          <div className="text-[10px] text-terminal-accent">{row.ticker}</div>
                        </td>
                        <td className="py-2.5">{row.country}</td>
                        <td className="py-2.5 text-terminal-muted">{row.sector}</td>
                        <td className="py-2.5 text-right font-mono font-bold">€ {row.price.toFixed(2)}</td>
                        <td className={`py-2.5 text-right font-mono font-bold ${row.price_change_24h >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                          {row.price_change_24h >= 0 ? "+" : ""}{row.price_change_24h.toFixed(2)}%
                        </td>
                        <td className="py-2.5 text-center">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${getSentimentBg(row.sentiment_score)}`}>
                            {row.sentiment_score >= 0 ? "+" : ""}{row.sentiment_score.toFixed(3)}
                          </span>
                        </td>
                        <td className="py-2.5 text-center">
                          <span className={`px-2 py-0.5 rounded text-[9px] uppercase ${getSignalBadge(row.signal)}`}>
                            {row.signal}
                          </span>
                        </td>
                        <td className="py-2.5 text-center font-mono font-bold text-slate-350">
                          🧠 {row.ml_prediction_prob ? `${(row.ml_prediction_prob * 100).toFixed(0)}%` : "50%"}
                        </td>
                        <td className="py-2.5 text-center">
                          <button
                            onClick={() => setSelectedTicker(row.ticker)}
                            className="bg-terminal-bg border border-terminal-border hover:border-terminal-accent hover:text-terminal-accent text-slate-300 px-2.5 py-1 rounded text-[10px] font-bold transition flex items-center gap-1 mx-auto"
                          >
                            <FileText className="h-3 w-3" /> Leggi Analisi
                          </button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    filteredForex.map((row) => (
                      <tr key={row.ticker} className="hover:bg-terminal-bg/50 transition">
                        <td className="py-2.5 font-bold">
                          <div>{row.name}</div>
                          <div className="text-[10px] text-terminal-accent">{row.ticker}</div>
                        </td>
                        <td className="py-2.5">{row.country}</td>
                        <td className="py-2.5 text-terminal-muted">{row.sector}</td>
                        <td className="py-2.5 text-right font-mono font-bold">{row.price.toFixed(4)}</td>
                        <td className={`py-2.5 text-right font-mono font-bold ${row.price_change_24h >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                          {row.price_change_24h >= 0 ? "+" : ""}{row.price_change_24h.toFixed(2)}%
                        </td>
                        <td className="py-2.5 text-center">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${getSentimentBg(row.sentiment_score)}`}>
                            {row.sentiment_score >= 0 ? "+" : ""}{row.sentiment_score.toFixed(3)}
                          </span>
                        </td>
                        <td className="py-2.5 text-center">
                          <span className={`px-2 py-0.5 rounded text-[9px] uppercase ${getSignalBadge(row.signal)}`}>
                            {row.signal}
                          </span>
                        </td>
                        <td className="py-2.5 text-center font-mono text-slate-500">
                          -
                        </td>
                        <td className="py-2.5 text-center">
                          <button
                            onClick={() => setSelectedTicker(row.ticker)}
                            className="bg-terminal-bg border border-terminal-border hover:border-terminal-accent hover:text-terminal-accent text-slate-300 px-2.5 py-1 rounded text-[10px] font-bold transition flex items-center gap-1 mx-auto"
                          >
                            <FileText className="h-3 w-3" /> Leggi Analisi
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                  {((screenerTab === "stocks" && filteredScreener.length === 0) || (screenerTab === "forex" && filteredForex.length === 0)) && (
                    <tr>
                      <td colSpan={9} className="py-8 text-center text-terminal-muted">
                        Nessun asset corrispondente ai filtri.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right 1 column: News & MT5 Bridge */}
        <div className="xl:col-span-1 flex flex-col gap-3">
          {/* A. News Feed */}
          <div className="bg-terminal-card border border-terminal-border p-4 rounded flex flex-col h-[360px] overflow-hidden">
            <h2 className="text-xs font-black uppercase text-slate-400 mb-3 border-b border-terminal-border pb-2 flex items-center gap-2">
              <Newspaper className="h-4 w-4 text-terminal-accent" /> Live News Feed (24H-48H)
            </h2>
            
            <div className="overflow-y-auto flex-1 divide-y divide-terminal-border/40 pr-1">
              {news.map((art) => (
                <div key={art.id} className="py-2.5 hover:bg-terminal-bg/30 px-1 rounded transition text-xs">
                  <div className="flex items-center justify-between text-[10px] text-terminal-muted mb-1">
                    <span>{art.source}</span>
                    <span>
                      {(() => {
                        const d = new Date(art.published_date);
                        const hours = String(d.getUTCHours()).padStart(2, '0');
                        const minutes = String(d.getUTCMinutes()).padStart(2, '0');
                        return `${hours}:${minutes} Z`;
                      })()}
                    </span>
                  </div>
                  <h3 className="font-bold text-slate-200 leading-snug mb-1.5 hover:text-terminal-accent transition">
                    <a href={art.url} target="_blank" rel="noopener noreferrer">{art.title}</a>
                  </h3>
                  
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap gap-1">
                      {art.tickers.map(ticker => (
                        <button
                          key={ticker}
                          onClick={() => setSelectedTicker(ticker)}
                          className="text-[9px] bg-terminal-accent/10 border border-terminal-accent/30 text-terminal-accent font-extrabold px-1.5 rounded hover:bg-terminal-accent hover:text-black transition"
                        >
                          {ticker.split('.')[0]}
                        </button>
                      ))}
                    </div>
                    
                    {art.sentiment_label && (
                      <span className={`text-[8px] font-mono uppercase px-1.5 py-0.2 rounded font-bold ${
                        art.sentiment_label === "positive" 
                          ? "bg-emerald-950 text-emerald-400 border border-emerald-500/20" 
                          : art.sentiment_label === "negative"
                          ? "bg-rose-950 text-rose-400 border border-rose-500/20"
                          : "bg-slate-850 text-slate-400 border border-slate-700/20"
                      }`}>
                        {art.sentiment_label}
                      </span>
                    )}
                  </div>
                </div>
              ))}
              {news.length === 0 && (
                <div className="h-full flex items-center justify-center text-xs text-terminal-muted text-center py-10">
                  Nessuna notizia scaricata.
                </div>
              )}
            </div>
          </div>

          {/* B. MT5 Bridge Diagnostics */}
          <div className="bg-terminal-card border border-terminal-border p-3 rounded flex flex-col h-[150px] shrink-0 overflow-hidden">
            <div className="flex items-center justify-between mb-1.5 border-b border-terminal-border pb-1.5">
              <h2 className="text-[10px] font-black uppercase text-slate-400 flex items-center gap-1.5">
                <Cpu className="h-3.5 w-3.5 text-terminal-accent" /> MT5 Bridge Diagnostics
              </h2>
              <div className="flex items-center gap-1">
                <span className={`h-1.5 w-1.5 rounded-full ${mt5Clients.length > 0 ? "bg-emerald-500 animate-pulse" : "bg-rose-500"}`}></span>
                <span className="text-[9px] text-slate-400 font-bold uppercase">
                  {mt5Clients.length > 0 ? "Connected" : "Idle"}
                </span>
              </div>
            </div>

            <div className="overflow-y-auto flex-1 text-[10px] pr-1">
              {mt5Clients.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center text-terminal-muted">
                  <Activity className="h-4 w-4 text-terminal-muted/30 mb-0.5" />
                  <span>Nessun client MT5 rilevato negli ultimi 5 min.</span>
                </div>
              ) : (
                <div className="divide-y divide-terminal-border/20">
                  {mt5Clients.map((client, idx) => (
                    <div key={idx} className="py-1 flex flex-col gap-0.5">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-300">IP: {client.ip}</span>
                        <span className="text-terminal-accent font-semibold">{client.ticker}</span>
                      </div>
                      <div className="flex items-center justify-between text-[9px] text-terminal-muted">
                        <span>Ultimo Ping:</span>
                        <span>
                          {(() => {
                            const d = new Date(client.last_seen);
                            const hours = String(d.getUTCHours()).padStart(2, '0');
                            const minutes = String(d.getUTCMinutes()).padStart(2, '0');
                            const seconds = String(d.getUTCSeconds()).padStart(2, '0');
                            return `${hours}:${minutes}:${seconds} Z`;
                          })()}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* C. MT5 Broker Accounts Telemetry */}
          <div className="bg-terminal-card border border-terminal-border p-3 rounded flex flex-col h-[230px] shrink-0 overflow-hidden">
            <div className="flex items-center justify-between mb-1.5 border-b border-terminal-border pb-1.5">
              <h2 className="text-[10px] font-black uppercase text-slate-400 flex items-center gap-1.5">
                <ShieldAlert className="h-3.5 w-3.5 text-terminal-accent" /> Broker Accounts Telemetry
              </h2>
              <span className="text-[8px] bg-slate-800 text-slate-400 font-mono px-1.5 py-0.2 rounded uppercase font-bold">
                {brokerAccounts.length} Active
              </span>
            </div>

            <div className="overflow-y-auto flex-1 text-[10px] pr-1">
              {brokerAccounts.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center text-terminal-muted">
                  <Activity className="h-4 w-4 text-terminal-muted/30 mb-0.5" />
                  <span>Nessun account MT5 rilevato.</span>
                </div>
              ) : (
                <div className="divide-y divide-terminal-border/20">
                  {brokerAccounts.map((acct, idx) => (
                    <div key={idx} className="py-1 flex flex-col gap-1">
                      <div className="flex items-center justify-between text-[9px]">
                        <span className="font-bold text-slate-200">Acc: {acct.account_id}</span>
                        <span className="text-[8px] bg-terminal-accent/10 text-terminal-accent border border-terminal-accent/20 px-1 py-0.2 rounded font-mono font-bold">
                          {acct.broker}
                        </span>
                      </div>
                      
                      <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 bg-terminal-bg/40 p-1.5 rounded border border-terminal-border/10 font-mono text-[9px]">
                        <div className="flex justify-between">
                          <span className="text-slate-500">Balance:</span>
                          <span className="text-slate-350 font-bold">€{acct.balance.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-500">Equity:</span>
                          <span className="text-slate-350 font-bold">€{acct.equity.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-500">Margin:</span>
                          <span className="text-slate-350 font-bold">€{acct.margin.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-500">Profit:</span>
                          <span className={`font-bold ${acct.profit >= 0 ? "text-emerald-400" : "text-rose-450"}`}>
                            {acct.profit >= 0 ? "+" : ""}€{acct.profit.toFixed(2)}
                          </span>
                        </div>
                        <div className="col-span-2 flex justify-between border-t border-terminal-border/10 pt-0.5 mt-0.5 text-[8px]">
                          <span className="text-slate-500">Margin Level:</span>
                          <span className={`font-bold ${acct.margin_level > 200 ? "text-emerald-400" : acct.margin_level > 100 ? "text-amber-450" : "text-rose-450 animate-pulse"}`}>
                            {acct.margin_level.toFixed(1)}%
                          </span>
                        </div>
                      </div>
                      
                      <div className="flex items-center justify-between text-[8px] text-terminal-muted">
                        <span>Last Update:</span>
                        <span>
                          {acct.last_seen ? (() => {
                            const d = new Date(acct.last_seen);
                            const hours = String(d.getUTCHours()).padStart(2, '0');
                            const minutes = String(d.getUTCMinutes()).padStart(2, '0');
                            const seconds = String(d.getUTCSeconds()).padStart(2, '0');
                            return `${hours}:${minutes}:${seconds} Z`;
                          })() : "N/A"}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* D. Economic Calendar & News Freeze */}
          <div className="bg-terminal-card border border-terminal-border p-3 rounded flex flex-col h-[220px] shrink-0 overflow-hidden">
            <div className="flex items-center justify-between mb-1.5 border-b border-terminal-border pb-1.5">
              <h2 className="text-[10px] font-black uppercase text-slate-400 flex items-center gap-1.5">
                <Calendar className="h-3.5 w-3.5 text-terminal-accent" /> Economic Calendar (Freeze Zones)
              </h2>
              <span className="text-[8px] bg-slate-800 text-slate-400 font-mono px-1.5 py-0.2 rounded uppercase font-bold">
                {economicCalendar.length} Events
              </span>
            </div>

            <div className="overflow-y-auto flex-1 text-[10px] pr-1">
              {economicCalendar.length === 0 ? (
                <div className="h-full flex items-center justify-center text-terminal-muted">
                  Nessun evento in calendario.
                </div>
              ) : (
                <div className="divide-y divide-terminal-border/20">
                  {economicCalendar.map((ev) => {
                    const eventTime = new Date(ev.scheduled_time);
                    const now = new Date();
                    const diffMins = (eventTime.getTime() - now.getTime()) / (1000 * 60);
                    const isFreezeActive = Math.abs(diffMins) <= 15;

                    return (
                      <div key={ev.id} className="py-1.5 flex flex-col gap-1">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-slate-200">{ev.title}</span>
                          <span className={`text-[8px] px-1 py-0.2 rounded font-mono font-bold ${
                            isFreezeActive ? "bg-rose-950 text-rose-400 border border-rose-500/30 animate-pulse" : "bg-slate-800 text-slate-400"
                          }`}>
                            {isFreezeActive ? "FREEZE ACTIVE" : "HIGH IMPACT"}
                          </span>
                        </div>
                        <div className="flex items-center justify-between text-[9px] text-terminal-muted">
                          <span>Paese: <b className="text-slate-350">{ev.country}</b></span>
                          <span>
                            {eventTime.getUTCHours().toString().padStart(2, '0')}:
                            {eventTime.getUTCMinutes().toString().padStart(2, '0')} UTC
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* E. Institutional Portfolio Allocation */}
          <div className="bg-terminal-card border border-terminal-border p-3 rounded flex flex-col h-[220px] shrink-0 overflow-hidden">
            <div className="flex items-center justify-between mb-1.5 border-b border-terminal-border pb-1.5">
              <h2 className="text-[10px] font-black uppercase text-slate-400 flex items-center gap-1.5">
                <Percent className="h-3.5 w-3.5 text-terminal-accent" /> Markowitz Portfolio Allocation
              </h2>
              <span className="text-[8px] bg-slate-800 text-slate-400 font-mono px-1.5 py-0.2 rounded uppercase font-bold">
                Optimal weights
              </span>
            </div>

            <div className="overflow-y-auto flex-1 text-[10px] pr-1">
              {!portfolioWeights ? (
                <div className="h-full flex items-center justify-center text-terminal-muted">
                  Nessuna allocazione calcolata.
                </div>
              ) : (
                <div className="divide-y divide-terminal-border/20">
                  {Object.entries(portfolioWeights)
                    .filter(([_, weight]) => weight > 0)
                    .map(([ticker, weight]) => {
                      const tickerRegime = marketRegimes.find(r => r.ticker === ticker);
                      return (
                        <div key={ticker} className="py-1.5 flex items-center justify-between">
                          <div className="flex flex-col">
                            <span className="font-bold text-slate-200">{ticker.split('.')[0]}</span>
                            <span className="text-[8px] text-terminal-muted">
                              Regime: {tickerRegime ? tickerRegime.regime.replace("REGIME_", "") : "UNKNOWN"}
                            </span>
                          </div>
                          <div className="text-right">
                            <span className="font-black text-terminal-accent font-mono">{(weight * 100).toFixed(2)}%</span>
                          </div>
                        </div>
                      );
                    })}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
      )}

      {/* Tab 2: Risk Analytics & Telemetry */}
      {mainTab === "risk_telemetry" && (
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-3 flex-1">
          {/* Left 2 columns: Notification Config & Multi-Account Limit */}
          <div className="xl:col-span-2 flex flex-col gap-3">
            {/* Notifications panel */}
            <div className="bg-terminal-card border border-terminal-border p-4 rounded">
              <h2 className="text-xs font-black uppercase text-slate-400 mb-3 border-b border-terminal-border pb-2 flex items-center gap-2">
                🔔 Impostazioni Notifiche di Segnale (Telegram / Discord)
              </h2>
              
              <div className="flex flex-col gap-3 text-xs">
                <div>
                  <label className="block text-slate-500 font-bold mb-1">Telegram Bot Token</label>
                  <input
                    type="password"
                    placeholder="E.g., 123456:ABC-DEF..."
                    value={telegramBotToken}
                    onChange={(e) => setTelegramBotToken(e.target.value)}
                    className="w-full bg-terminal-bg border border-terminal-border rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-terminal-accent font-mono"
                  />
                </div>
                <div>
                  <label className="block text-slate-500 font-bold mb-1">Telegram Chat ID</label>
                  <input
                    type="text"
                    placeholder="E.g., -100123456789"
                    value={telegramChatId}
                    onChange={(e) => setTelegramChatId(e.target.value)}
                    className="w-full bg-terminal-bg border border-terminal-border rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-terminal-accent font-mono"
                  />
                </div>
                <div>
                  <label className="block text-slate-500 font-bold mb-1">Discord Webhook URL</label>
                  <input
                    type="password"
                    placeholder="https://discord.com/api/webhooks/..."
                    value={discordWebhookUrl}
                    onChange={(e) => setDiscordWebhookUrl(e.target.value)}
                    className="w-full bg-terminal-bg border border-terminal-border rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-terminal-accent font-mono"
                  />
                </div>
                <button
                  onClick={async () => {
                    setSettingsSaving(true);
                    try {
                      const res = await fetch(`${API_URL}/api/system-settings`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                          telegram_bot_token: telegramBotToken,
                          telegram_chat_id: telegramChatId,
                          discord_webhook_url: discordWebhookUrl
                        })
                      });
                      if (res.ok) alert("Impostazioni notifica salvate con successo!");
                    } catch (err) {
                      console.error(err);
                    } finally {
                      setSettingsSaving(false);
                    }
                  }}
                  disabled={settingsSaving}
                  className="mt-2 w-full bg-terminal-accent text-black font-extrabold py-2 px-4 rounded hover:bg-terminal-accent/80 transition"
                >
                  {settingsSaving ? "SALVATAGGIO IN CORSO..." : "SALVA IMPOSTAZIONI DI NOTIFICA"}
                </button>
              </div>
            </div>

            {/* Per-Account Risk Limits table */}
            <div className="bg-terminal-card border border-terminal-border p-4 rounded flex-1">
              <h2 className="text-xs font-black uppercase text-slate-400 mb-3 border-b border-terminal-border pb-2 flex items-center gap-2">
                🛡️ Account Drawdown Limiti Granulari (MetaTrader 5)
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse">
                  <thead>
                    <tr className="border-b border-terminal-border text-slate-500 uppercase tracking-wider text-[9px] font-black">
                      <th className="py-2">Account ID</th>
                      <th className="py-2">Broker</th>
                      <th className="py-2">Balance</th>
                      <th className="py-2">Drawdown %</th>
                      <th className="py-2">Max DD Limit %</th>
                      <th className="py-2 text-right">Azione</th>
                    </tr>
                  </thead>
                  <tbody>
                    {brokerAccounts.map((acct) => {
                      const bal_val = acct.balance || 0.0;
                      const eq_val = acct.equity || 0.0;
                      const dd = bal_val > eq_val && bal_val > 0 ? ((bal_val - eq_val) / bal_val * 100.0) : 0.0;
                      const riskAcc = riskAccounts.find(r => r.account_id === acct.account_id);
                      const max_dd_limit = riskAcc ? riskAcc.max_drawdown_percent : 5.0;

                      return (
                        <tr key={acct.account_id} className="border-b border-terminal-border/20 hover:bg-terminal-bg/20 font-mono">
                          <td className="py-2.5 font-bold text-terminal-accent">{acct.account_id}</td>
                          <td className="py-2.5 text-slate-350 font-sans font-bold">{acct.broker}</td>
                          <td className="py-2.5">€ {bal_val.toFixed(2)}</td>
                          <td className={`py-2.5 font-bold ${dd > max_dd_limit ? "text-rose-455" : "text-slate-300"}`}>
                            {dd.toFixed(2)}%
                          </td>
                          <td className="py-2.5">{max_dd_limit.toFixed(1)}%</td>
                          <td className="py-2.5 text-right font-sans">
                            <button
                              onClick={() => {
                                const val = prompt("Inserisci il nuovo limite di drawdown (%) per questo account:", String(max_dd_limit));
                                if (val && !isNaN(parseFloat(val))) {
                                  updateAccountRiskLimit(acct.account_id, parseFloat(val));
                                }
                              }}
                              className="bg-terminal-border hover:bg-terminal-accent hover:text-black px-2.5 py-1 rounded text-[10px] font-bold uppercase transition"
                            >
                              Modifica
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                    {brokerAccounts.length === 0 && (
                      <tr>
                        <td colSpan={6} className="py-8 text-center text-terminal-muted font-sans">
                          Nessun account MT5 connesso rilevato.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Right 2 columns: VaR / Sharpe / Sortino & Equity Curve Area Chart */}
          <div className="xl:col-span-2 flex flex-col gap-3">
            <div className="bg-terminal-card border border-terminal-border p-4 rounded flex-1 flex flex-col">
              <h2 className="text-xs font-black uppercase text-slate-400 mb-3 border-b border-terminal-border pb-2">
                🧮 Portfolio Risk Analytics & Telemetry
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-center mb-4">
                <div className="bg-terminal-bg/50 border border-terminal-border p-2.5 rounded">
                  <span className="text-[9px] text-slate-500 block uppercase font-bold">Value at Risk (VaR 95%)</span>
                  <span className="text-base font-mono font-black text-rose-400">
                    {riskAnalytics ? `${riskAnalytics.value_at_risk_95.toFixed(2)}%` : "CALCULATING..."}
                  </span>
                </div>
                <div className="bg-terminal-bg/50 border border-terminal-border p-2.5 rounded">
                  <span className="text-[9px] text-slate-500 block uppercase font-bold">Sharpe Ratio</span>
                  <span className="text-base font-mono font-black text-emerald-400">
                    {riskAnalytics ? riskAnalytics.sharpe_ratio.toFixed(2) : "CALCULATING..."}
                  </span>
                </div>
                <div className="bg-terminal-bg/50 border border-terminal-border p-2.5 rounded">
                  <span className="text-[9px] text-slate-500 block uppercase font-bold">Sortino Ratio</span>
                  <span className="text-base font-mono font-black text-emerald-400">
                    {riskAnalytics ? riskAnalytics.sortino_ratio.toFixed(2) : "CALCULATING..."}
                  </span>
                </div>
                <div className="bg-terminal-bg/50 border border-terminal-border p-2.5 rounded">
                  <span className="text-[9px] text-slate-500 block uppercase font-bold">Max Drawdown</span>
                  <span className="text-base font-mono font-black text-amber-500">
                    {riskAnalytics ? `${riskAnalytics.max_drawdown.toFixed(2)}%` : "CALCULATING..."}
                  </span>
                </div>
              </div>

              <h3 className="text-[10px] font-black uppercase text-slate-500 mb-2 tracking-wider">
                Simulazione Curve Equity Portafoglio (Modello Equal-Weight 60gg)
              </h3>
              <div className="flex-1 min-h-[280px] bg-terminal-bg/30 border border-terminal-border rounded p-2">
                {riskAnalytics && riskAnalytics.equity_curve && riskAnalytics.equity_curve.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={riskAnalytics.equity_curve} margin={{ top: 10, right: 10, left: 10, bottom: 5 }}>
                      <defs>
                        <linearGradient id="colorEq" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#ff9900" stopOpacity={0.25}/>
                          <stop offset="95%" stopColor="#ff9900" stopOpacity={0.0}/>
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="date" stroke="#475569" fontSize={9} tickLine={false} />
                      <YAxis stroke="#475569" fontSize={9} domain={['dataMin - 500', 'dataMax + 500']} tickLine={false} />
                      <Tooltip
                        contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #334155" }}
                        labelStyle={{ color: "#94a3b8", fontWeight: "bold" }}
                        itemStyle={{ color: "#ff9900", fontFamily: "monospace" }}
                      />
                      <Area type="monotone" dataKey="equity" stroke="#ff9900" strokeWidth={2} fillOpacity={1} fill="url(#colorEq)" name="Equity (€)" />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-xs text-terminal-muted font-sans">
                    Caricamento curva equity in corso...
                  </div>
                )}
              </div>
            </div>

            <div className="bg-terminal-card border border-terminal-border p-4 rounded flex-1 flex flex-col">
              <h2 className="text-xs font-black uppercase text-slate-400 mb-3 border-b border-terminal-border pb-2 flex items-center gap-2">
                🎲 Stress-Test & Proiezioni Predittive Monte Carlo (30 Giorni)
              </h2>
              {monteCarloLoading ? (
                <div className="h-48 flex items-center justify-center text-xs text-terminal-muted">
                  Simulazione di 1.000 percorsi di portafoglio in corso...
                </div>
              ) : monteCarloResults ? (
                <div className="flex-1 flex flex-col gap-3">
                  <div className="grid grid-cols-3 gap-3 text-center mb-2">
                    <div className="bg-terminal-bg/50 border border-terminal-border p-2.5 rounded">
                      <span className="text-[9px] text-slate-500 block uppercase font-bold">VaR 95% (30-gg)</span>
                      <span className="text-xs font-mono font-black text-rose-400">
                        {monteCarloResults.var_95.toFixed(2)}%
                      </span>
                    </div>
                    <div className="bg-terminal-bg/50 border border-terminal-border p-2.5 rounded">
                      <span className="text-[9px] text-slate-500 block uppercase font-bold">CVaR 95% (Stress)</span>
                      <span className="text-xs font-mono font-black text-rose-500">
                        {monteCarloResults.cvar_95.toFixed(2)}%
                      </span>
                    </div>
                    <div className="bg-terminal-bg/50 border border-terminal-border p-2.5 rounded">
                      <span className="text-[9px] text-slate-500 block uppercase font-bold">Prob. Drawdown &gt; 5%</span>
                      <span className="text-xs font-mono font-black text-amber-500">
                        {monteCarloResults.prob_drawdown_5.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                  
                  <div className="flex-1 min-h-[220px] bg-terminal-bg/30 border border-terminal-border rounded p-2">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={monteCarloResults.paths} margin={{ top: 10, right: 10, left: 10, bottom: 5 }}>
                        <defs>
                          <linearGradient id="colorP95" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#10b981" stopOpacity={0.15}/>
                            <stop offset="95%" stopColor="#10b981" stopOpacity={0.0}/>
                          </linearGradient>
                          <linearGradient id="colorP5" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.15}/>
                            <stop offset="95%" stopColor="#ef4444" stopOpacity={0.0}/>
                          </linearGradient>
                        </defs>
                        <XAxis dataKey="day" stroke="#475569" fontSize={9} tickLine={false} />
                        <YAxis stroke="#475569" fontSize={9} domain={['dataMin - 200', 'dataMax + 200']} tickLine={false} />
                        <Tooltip
                          contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #334155" }}
                          labelStyle={{ color: "#94a3b8", fontWeight: "bold" }}
                          itemStyle={{ fontFamily: "monospace", fontSize: 10 }}
                        />
                        <Area type="monotone" dataKey="p95" stroke="#10b981" strokeWidth={1.5} fillOpacity={1} fill="url(#colorP95)" name="Ottimistico (P95)" />
                        <Area type="monotone" dataKey="p50" stroke="#f97316" strokeWidth={2} fill="none" name="Mediano (P50)" />
                        <Area type="monotone" dataKey="p5" stroke="#ef4444" strokeWidth={1.5} fillOpacity={1} fill="url(#colorP5)" name="Stress Test (P5)" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              ) : (
                <div className="h-48 flex items-center justify-center text-xs text-terminal-muted">
                  Nessun dato di simulazione disponibile.
                </div>
              )}
            </div>

            {/* New Panel for Stress Test & Hedging */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
              {/* Stress Test */}
              <div className="bg-terminal-card border border-terminal-border p-4 rounded flex-1 flex flex-col">
                <h2 className="text-xs font-black uppercase text-slate-400 mb-3 border-b border-terminal-border pb-2 flex items-center gap-2">
                  🏛 Historical Stress Test (Portfolio: €{hedgingBeta?.portfolio_value || 0})
                </h2>
                {stressTest ? (
                  <div className="flex flex-col gap-2">
                    {stressTest.scenarios.map((s, idx) => (
                      <div key={idx} className="flex items-center justify-between bg-terminal-bg border border-terminal-border p-2 rounded">
                        <span className="text-[10px] text-slate-300 font-bold">{s.name}</span>
                        <span className="text-xs font-mono font-black text-rose-500">{s.max_drawdown.toFixed(1)}%</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-xs text-terminal-muted">Caricamento stress test...</div>
                )}
              </div>

              {/* Hedging Beta */}
              <div className="bg-terminal-card border border-terminal-border p-4 rounded flex-1 flex flex-col">
                <h2 className="text-xs font-black uppercase text-slate-400 mb-3 border-b border-terminal-border pb-2 flex items-center gap-2">
                  🛡 Dynamic Hedging (Beta Neutral)
                </h2>
                {hedgingBeta ? (
                  <div className="flex flex-col gap-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-slate-500 uppercase font-bold">Hedge Index</span>
                      <span className="text-xs text-slate-200 font-bold">{hedgingBeta.index}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-slate-500 uppercase font-bold">Portfolio Beta</span>
                      <span className="text-xs text-amber-500 font-mono font-bold">{hedgingBeta.beta.toFixed(2)}</span>
                    </div>
                    <div className="flex items-center justify-between bg-terminal-bg border border-terminal-border p-2 rounded">
                      <span className="text-xs text-slate-300 font-bold">Recommended Short Lots</span>
                      <span className="text-sm font-mono font-black text-emerald-400">{hedgingBeta.required_short_lots}</span>
                    </div>
                  </div>
                ) : (
                  <div className="text-xs text-terminal-muted">Caricamento hedging...</div>
                )}
              </div>
            </div>

          </div>
        </div>
      )}

      {/* Tab 3: Correlation Matrix */}
      {mainTab === "correlation" && (
        <div className="bg-terminal-card border border-terminal-border p-4 rounded flex flex-col flex-1">
          <div className="border-b border-terminal-border pb-2 mb-3">
            <h2 className="text-xs font-black uppercase text-slate-400 flex items-center gap-2">
              🧮 Matrix di Correlazione Storica Multi-Asset (Pearson - 60 Giorni)
            </h2>
            <p className="text-[10px] text-terminal-muted mt-1">
              Fornisce una mappa di calore della correlazione giornaliera dei rendimenti a 60 giorni. I colori verdi indicano correlazione positiva, i rossi indicano correlazione negativa, mentre i grigi indicano correlazione debole o assente.
            </p>
          </div>

          {correlationData ? (
            <div className="overflow-auto flex-1 flex flex-col items-center justify-start p-4">
              <div className="min-w-[800px]">
                {/* Header Row */}
                <div className="flex mb-1.5">
                  <div className="w-24 shrink-0"></div>
                  {correlationData.tickers.map((t) => (
                    <div key={t} className="w-14 text-center text-[9px] font-black text-slate-400 shrink-0 font-mono truncate px-0.5">
                      {t.split('.')[0]}
                    </div>
                  ))}
                </div>

                {/* Matrix Rows */}
                {correlationData.tickers.map((rowTicker, rIdx) => (
                  <div key={rowTicker} className="flex mb-1 items-center">
                    {/* Row Label */}
                    <div className="w-24 text-right text-[10px] font-bold text-slate-400 shrink-0 pr-3 font-mono truncate">
                      {rowTicker.split('.')[0]}
                    </div>

                    {/* Grid Cells */}
                    {correlationData.matrix[rIdx].map((val, cIdx) => {
                      let cellClass = "bg-slate-900/50 text-slate-400";
                      if (val > 0.7) cellClass = "bg-emerald-900 text-emerald-100 font-bold";
                      else if (val > 0.3) cellClass = "bg-emerald-950 text-emerald-350";
                      else if (val < -0.7) cellClass = "bg-rose-900 text-rose-100 font-bold";
                      else if (val < -0.3) cellClass = "bg-rose-950 text-rose-350";

                      return (
                        <div
                          key={cIdx}
                          title={`Correlazione ${rowTicker} & ${correlationData.tickers[cIdx]} = ${val.toFixed(3)}`}
                          className={`w-14 h-10 flex items-center justify-center text-[10px] font-mono shrink-0 rounded border border-terminal-bg/40 transition hover:scale-110 hover:shadow-lg ${cellClass}`}
                        >
                          {val.toFixed(2)}
                        </div>
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="h-64 flex items-center justify-center text-xs text-terminal-muted">
              Caricamento matrice di correlazione in corso...
            </div>
          )}
        </div>
      )}

      {/* Tab 4: Portfolio Backtester */}
      {mainTab === "backtest" && (
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-3 flex-1">
          {/* Left Column: Config Parameters & Asset Checkboxes */}
          <div className="xl:col-span-1 bg-terminal-card border border-terminal-border p-4 rounded flex flex-col shrink-0">
            <h2 className="text-xs font-black uppercase text-slate-400 mb-3 border-b border-terminal-border pb-2 flex items-center gap-1.5">
              ⚙️ Configurazione Portfolio Backtest
            </h2>
            
            <div className="flex flex-col gap-3 text-xs flex-1">
              <div>
                <label className="block text-slate-500 font-bold mb-1">Capitale Iniziale (€)</label>
                <input
                  type="number"
                  value={backtestCapital}
                  onChange={(e) => setBacktestCapital(Number(e.target.value))}
                  className="w-full bg-terminal-bg border border-terminal-border rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-terminal-accent font-mono"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-slate-500 font-bold mb-1">Buy RSI &lt;=</label>
                  <input
                    type="number"
                    value={backtestBuyRsi}
                    onChange={(e) => setBacktestBuyRsi(Number(e.target.value))}
                    className="w-full bg-terminal-bg border border-terminal-border rounded px-2 py-1 text-slate-200 focus:outline-none focus:border-terminal-accent font-mono"
                  />
                </div>
                <div>
                  <label className="block text-slate-500 font-bold mb-1">Sell RSI &gt;=</label>
                  <input
                    type="number"
                    value={backtestSellRsi}
                    onChange={(e) => setBacktestSellRsi(Number(e.target.value))}
                    className="w-full bg-terminal-bg border border-terminal-border rounded px-2 py-1 text-slate-200 focus:outline-none focus:border-terminal-accent font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-slate-500 font-bold mb-1">Buy Sentiment &gt;=</label>
                  <input
                    type="number"
                    step="0.05"
                    value={backtestBuySent}
                    onChange={(e) => setBacktestBuySent(Number(e.target.value))}
                    className="w-full bg-terminal-bg border border-terminal-border rounded px-2 py-1 text-slate-200 focus:outline-none focus:border-terminal-accent font-mono"
                  />
                </div>
                <div>
                  <label className="block text-slate-500 font-bold mb-1">Sell Sentiment &lt;=</label>
                  <input
                    type="number"
                    step="0.05"
                    value={backtestSellSent}
                    onChange={(e) => setBacktestSellSent(Number(e.target.value))}
                    className="w-full bg-terminal-bg border border-terminal-border rounded px-2 py-1 text-slate-200 focus:outline-none focus:border-terminal-accent font-mono"
                  />
                </div>
              </div>

              {/* Ticker checklist */}
              <div className="flex-1 flex flex-col min-h-[160px]">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-slate-500 font-bold">Tickers ({selectedPortfolioTickers.length})</span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setSelectedPortfolioTickers(screener.map(s => s.ticker))}
                      className="text-[9px] text-terminal-accent hover:underline uppercase font-bold"
                    >
                      Tutti
                    </button>
                    <button
                      onClick={() => setSelectedPortfolioTickers([])}
                      className="text-[9px] text-slate-500 hover:underline uppercase font-bold"
                    >
                      Nessuno
                    </button>
                  </div>
                </div>
                <div className="border border-terminal-border rounded bg-terminal-bg/50 p-2 overflow-y-auto flex-1 max-h-[180px]">
                  {screener.map((s) => (
                    <label key={s.ticker} className="flex items-center gap-2 py-1 hover:bg-terminal-bg/30 px-1 rounded cursor-pointer">
                      <input
                        type="checkbox"
                        checked={selectedPortfolioTickers.includes(s.ticker)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedPortfolioTickers([...selectedPortfolioTickers, s.ticker]);
                          } else {
                            setSelectedPortfolioTickers(selectedPortfolioTickers.filter(t => t !== s.ticker));
                          }
                        }}
                        className="rounded border-slate-700 text-terminal-accent focus:ring-terminal-accent"
                      />
                      <span className="font-mono text-xs">{s.ticker}</span>
                    </label>
                  ))}
                </div>
              </div>

              <button
                onClick={async () => {
                  if (selectedPortfolioTickers.length === 0) {
                    alert("Seleziona almeno un ticker per avviare il backtest!");
                    return;
                  }
                  setPortfolioBacktestLoading(true);
                  try {
                    const res = await fetch(`${API_URL}/api/backtest/portfolio`, {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({
                        tickers: selectedPortfolioTickers,
                        capital: backtestCapital,
                        buy_rsi: backtestBuyRsi,
                        sell_rsi: backtestSellRsi,
                        buy_sentiment: backtestBuySent,
                        sell_sentiment: backtestSellSent
                      })
                    });
                    if (res.ok) {
                      const data = await res.json();
                      setPortfolioBacktestResults(data);
                    } else {
                      const err = await res.json();
                      alert(`Errore: ${err.detail || "Impossibile eseguire il backtest"}`);
                    }
                  } catch (err) {
                    console.error(err);
                  } finally {
                    setPortfolioBacktestLoading(false);
                  }
                }}
                disabled={portfolioBacktestLoading || selectedPortfolioTickers.length === 0}
                className={`w-full font-black uppercase text-xs py-2 px-4 rounded transition flex items-center justify-center gap-1.5 ${
                  portfolioBacktestLoading || selectedPortfolioTickers.length === 0
                    ? "bg-terminal-card border border-terminal-border text-terminal-muted cursor-not-allowed"
                    : "bg-terminal-accent text-black font-extrabold hover:bg-terminal-accent/80 shadow-[0_0_8px_rgba(255,153,0,0.3)]"
                }`}
              >
                {portfolioBacktestLoading ? "ESECUZIONE BACKTEST..." : "AVVIA PORTFOLIO BACKTEST"}
              </button>

              {/* Portfolio Weight Optimization Section */}
              <div className="border-t border-terminal-border pt-4 mt-2">
                <h3 className="text-[10px] font-black uppercase text-slate-400 mb-2 tracking-wider flex items-center gap-1">
                  💼 Ottimizzazione Pesi (MVO)
                </h3>
                <div className="grid grid-cols-2 gap-2 mb-2">
                  <div>
                    <label className="block text-slate-500 font-bold mb-0.5">Metodo</label>
                    <select
                      value={optMethod}
                      onChange={(e) => setOptMethod(e.target.value as any)}
                      className="w-full bg-terminal-bg border border-terminal-border rounded px-1.5 py-1 text-slate-200 focus:outline-none focus:border-terminal-accent text-xs font-mono"
                    >
                      <option value="max_sharpe">Max Sharpe</option>
                      <option value="min_volatility">Min Vol</option>
                    </select>
                  </div>
                  <div className="flex items-center gap-1.5 mt-4">
                    <input
                      type="checkbox"
                      id="useBLCheck"
                      checked={useBL}
                      onChange={(e) => setUseBL(e.target.checked)}
                      className="rounded border-slate-700 text-terminal-accent focus:ring-terminal-accent"
                    />
                    <label htmlFor="useBLCheck" className="text-slate-400 text-[10px] cursor-pointer">Black-Litterman</label>
                  </div>
                </div>
                <button
                  onClick={async () => {
                    if (selectedPortfolioTickers.length === 0) {
                      alert("Seleziona almeno un ticker per ottimizzare i pesi!");
                      return;
                    }
                    setPortfolioWeightsLoading(true);
                    try {
                      const res = await fetch(`${API_URL}/api/portfolio/optimize`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                          tickers: selectedPortfolioTickers,
                          method: optMethod,
                          use_black_litterman: useBL,
                          rf_rate: 0.0
                        })
                      });
                      if (res.ok) {
                        const data = await res.json();
                        setPortfolioWeights(data.weights);
                      } else {
                        const err = await res.json();
                        alert(`Errore: ${err.detail || "Impossibile ottimizzare i pesi"}`);
                      }
                    } catch (err) {
                      console.error(err);
                    } finally {
                      setPortfolioWeightsLoading(false);
                    }
                  }}
                  disabled={portfolioWeightsLoading || selectedPortfolioTickers.length === 0}
                  className="w-full bg-terminal-border hover:bg-terminal-accent hover:text-black font-black uppercase text-[10px] py-1.5 px-3 rounded transition text-slate-200"
                >
                  {portfolioWeightsLoading ? "CALCOLO IN CORSO..." : "CALCOLA PESI OTTIMALI"}
                </button>
                
                {portfolioWeights && (
                  <div className="mt-2 border border-terminal-border bg-terminal-bg/30 p-2 rounded max-h-[120px] overflow-y-auto">
                    <table className="w-full text-[10px] font-mono text-left">
                      <thead>
                        <tr className="text-slate-500 font-bold border-b border-terminal-border/40">
                          <th className="pb-1">Asset</th>
                          <th className="pb-1 text-right">Peso</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(portfolioWeights).map(([t, w]) => (
                          <tr key={t} className="border-b border-terminal-border/10">
                            <td className="py-1 text-slate-300 font-bold">{t}</td>
                            <td className="py-1 text-right text-terminal-accent font-black">{(w * 100).toFixed(1)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* WFO Parameter Sweep Section */}
              <div className="border-t border-terminal-border pt-4 mt-2">
                <h3 className="text-[10px] font-black uppercase text-slate-400 mb-2 tracking-wider flex items-center gap-1">
                  🔍 Sweep Parametri Ottimali (WFO)
                </h3>
                <button
                  onClick={async () => {
                    if (selectedPortfolioTickers.length === 0) {
                      alert("Seleziona almeno un ticker per avviare lo sweep!");
                      return;
                    }
                    setWfoLoading(true);
                    try {
                      const res = await fetch(`${API_URL}/api/backtest/optimize-params`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                          tickers: selectedPortfolioTickers,
                          capital: backtestCapital
                        })
                      });
                      if (res.ok) {
                        const data = await res.json();
                        if (data.status === "success") {
                          setWfoResults(data.best_params);
                        } else {
                          alert("Nessun dato sufficiente per calcolare lo sweep.");
                        }
                      }
                    } catch (err) {
                      console.error(err);
                    } finally {
                      setWfoLoading(false);
                    }
                  }}
                  disabled={wfoLoading || selectedPortfolioTickers.length === 0}
                  className="w-full bg-terminal-border hover:bg-terminal-accent hover:text-black font-black uppercase text-[10px] py-1.5 px-3 rounded transition text-slate-200"
                >
                  {wfoLoading ? "SWEEP IN CORSO..." : "AVVIA SWEEP DI PARAMETRI"}
                </button>
                
                {wfoResults && wfoResults.length > 0 && (
                  <div className="mt-2 flex flex-col gap-2 max-h-[180px] overflow-y-auto">
                    {wfoResults.map((r, idx) => (
                      <div key={idx} className="border border-terminal-border/60 bg-terminal-bg/50 p-2 rounded text-[10px] font-mono flex flex-col gap-1">
                        <div className="flex justify-between items-center text-slate-400 font-bold border-b border-terminal-border/20 pb-1">
                          <span>Combo #{idx + 1}</span>
                          <span className="text-emerald-400">Sharpe: {r.sharpe_ratio}</span>
                        </div>
                        <div className="grid grid-cols-2 gap-x-2 text-[9px] text-slate-350">
                          <div>Buy RSI: <span className="text-slate-100 font-bold">{r.buy_rsi}</span></div>
                          <div>Sell RSI: <span className="text-slate-100 font-bold">{r.sell_rsi}</span></div>
                          <div>Buy Sent: <span className="text-slate-100 font-bold">{r.buy_sentiment}</span></div>
                          <div>Sell Sent: <span className="text-slate-100 font-bold">{r.sell_sentiment}</span></div>
                          <div className="col-span-2 text-slate-400 mt-1">Ret: <span className="text-emerald-400 font-bold">{r.total_return_percent}%</span> | DD: <span className="text-amber-500 font-bold">{r.max_drawdown}%</span></div>
                        </div>
                        <button
                          onClick={() => {
                            setBacktestBuyRsi(r.buy_rsi);
                            setBacktestSellRsi(r.sell_rsi);
                            setBacktestBuySent(r.buy_sentiment);
                            setBacktestSellSent(r.sell_sentiment);
                          }}
                          className="mt-1 bg-terminal-bg border border-terminal-border hover:border-terminal-accent text-terminal-accent hover:text-white uppercase font-bold py-0.5 rounded text-[8px] transition"
                        >
                          Applica Parametri
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

            </div>
          </div>

          {/* Right Column: Key Metrics & Backtest Equity Curve */}
          <div className="xl:col-span-3 bg-terminal-card border border-terminal-border p-4 rounded flex flex-col">
            <h2 className="text-xs font-black uppercase text-slate-400 mb-3 border-b border-terminal-border pb-2">
              📈 Risultati Simulazione Backtest di Portafoglio
            </h2>

            {portfolioBacktestResults ? (
              <div className="flex-1 flex flex-col gap-3">
                {/* Key Metrics grid */}
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-center">
                  <div className="bg-terminal-bg/50 border border-terminal-border p-2.5 rounded">
                    <span className="text-[9px] text-slate-500 block uppercase font-bold">Capitale Finale</span>
                    <span className="text-base font-mono font-black text-slate-200">
                      € {portfolioBacktestResults.final_capital.toLocaleString("de-DE", { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="bg-terminal-bg/50 border border-terminal-border p-2.5 rounded">
                    <span className="text-[9px] text-slate-500 block uppercase font-bold">Rendimento Totale</span>
                    <span className={`text-base font-mono font-black ${portfolioBacktestResults.total_return_percent >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {portfolioBacktestResults.total_return_percent >= 0 ? "+" : ""}{portfolioBacktestResults.total_return_percent.toFixed(2)}%
                    </span>
                  </div>
                  <div className="bg-terminal-bg/50 border border-terminal-border p-2.5 rounded">
                    <span className="text-[9px] text-slate-500 block uppercase font-bold">Max Drawdown</span>
                    <span className="text-base font-mono font-black text-amber-500">
                      {portfolioBacktestResults.max_drawdown.toFixed(2)}%
                    </span>
                  </div>
                  <div className="bg-terminal-bg/50 border border-terminal-border p-2.5 rounded">
                    <span className="text-[9px] text-slate-500 block uppercase font-bold">Win Rate</span>
                    <span className="text-base font-mono font-black text-emerald-400">
                      {portfolioBacktestResults.win_rate.toFixed(1)}%
                    </span>
                  </div>
                  <div className="bg-terminal-bg/50 border border-terminal-border p-2.5 rounded">
                    <span className="text-[9px] text-slate-500 block uppercase font-bold">Operazioni Totali</span>
                    <span className="text-base font-mono font-black text-slate-300">
                      {portfolioBacktestResults.total_trades}
                    </span>
                  </div>
                </div>

                {/* Equity Chart */}
                <div className="flex-1 min-h-[300px] mt-2 bg-terminal-bg/30 border border-terminal-border rounded p-2">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={portfolioBacktestResults.equity_curve} margin={{ top: 10, right: 10, left: 10, bottom: 5 }}>
                      <defs>
                        <linearGradient id="colorEqBacktest" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#ff9900" stopOpacity={0.25}/>
                          <stop offset="95%" stopColor="#ff9900" stopOpacity={0.0}/>
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="date" stroke="#475569" fontSize={9} tickLine={false} />
                      <YAxis stroke="#475569" fontSize={9} domain={['dataMin - 500', 'dataMax + 500']} tickLine={false} />
                      <Tooltip
                        contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #334155" }}
                        labelStyle={{ color: "#94a3b8", fontWeight: "bold" }}
                        itemStyle={{ color: "#ff9900", fontFamily: "monospace" }}
                      />
                      <Area type="monotone" dataKey="equity" stroke="#ff9900" strokeWidth={2} fillOpacity={1} fill="url(#colorEqBacktest)" name="Capitale (€)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-center text-terminal-muted p-10 border border-dashed border-terminal-border/40 rounded">
                <Play className="h-8 w-8 text-terminal-muted/30 mb-2" />
                <span className="text-xs">
                  Imposta i parametri a sinistra, seleziona i ticker e premi "Avvia Portfolio Backtest" per visualizzare l'analisi di simulazione.
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {mainTab === "audit_log" && (
        <div className="bg-terminal-card border border-terminal-border p-4 rounded flex flex-col flex-1 min-h-[500px]">
          <div className="flex justify-between items-center border-b border-terminal-border pb-3 mb-4">
            <div>
              <h2 className="text-xs font-black uppercase text-slate-200 flex items-center gap-1.5">
                🔐 Registro Audit di Sicurezza & Compliance
              </h2>
              <p className="text-[10px] text-slate-400 mt-1">
                Tracciamento immutabile di tutte le azioni di controllo, override e modifiche ai parametri di rischio eseguiti sul framework.
              </p>
            </div>
            <button
              onClick={fetchAuditLogs}
              disabled={auditLogsLoading}
              className="bg-terminal-bg border border-terminal-border hover:border-terminal-accent text-slate-300 hover:text-white px-3 py-1.5 rounded text-xs font-bold transition flex items-center gap-1.5"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${auditLogsLoading ? "animate-spin" : ""}`} />
              AGGIORNA LOGS
            </button>
          </div>

          {auditLogsLoading ? (
            <div className="flex-1 flex items-center justify-center text-slate-400">
              <RefreshCw className="h-6 w-6 animate-spin text-terminal-accent mr-2" />
              Caricamento del registro di audit in corso...
            </div>
          ) : auditLogs.length === 0 ? (
            <div className="flex-1 flex items-center justify-center text-xs text-slate-500 border border-dashed border-terminal-border/40 rounded p-10">
              Nessun evento registrato nel log di audit.
            </div>
          ) : (
            <div className="flex-1 overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs font-mono">
                <thead>
                  <tr className="border-b border-terminal-border text-slate-500 font-bold uppercase text-[10px] tracking-wider">
                    <th className="py-2.5 px-3">Data (Zulu)</th>
                    <th className="py-2.5 px-3">Utente</th>
                    <th className="py-2.5 px-3">Azione</th>
                    <th className="py-2.5 px-3">Indirizzo IP</th>
                    <th className="py-2.5 px-3 w-1/2">Dettagli Modifica</th>
                  </tr>
                </thead>
                <tbody>
                  {auditLogs.map((log) => (
                    <tr key={log.id} className="border-b border-terminal-border/40 hover:bg-terminal-bg/30 transition text-slate-300">
                      <td className="py-2 px-3 text-[11px] text-slate-400 whitespace-nowrap">
                        {log.timestamp ? log.timestamp.replace("T", " ").substring(0, 19) : ""}
                      </td>
                      <td className="py-2 px-3 font-bold text-slate-200">
                        {log.username}
                      </td>
                      <td className="py-2 px-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-sans font-bold uppercase ${
                          log.action.includes("kill") || log.action.includes("override")
                            ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                            : "bg-terminal-accent/20 text-terminal-accent border border-terminal-accent/30"
                        }`}>
                          {log.action}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-slate-400">
                        {log.ip_address}
                      </td>
                      <td className="py-2 px-3 text-slate-350 max-w-xs truncate font-mono text-[10px]">
                        {typeof log.details === "object" ? JSON.stringify(log.details) : String(log.details)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {mainTab === "ai_ml" && (
        <div className="bg-terminal-card border border-terminal-border p-4 rounded flex flex-col flex-1 min-h-[500px]">
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center border-b border-terminal-border pb-3 mb-4 gap-3">
            <div>
              <h2 className="text-xs font-black uppercase text-slate-200 flex items-center gap-1.5">
                🧠 Pannello di Controllo Intelligenza Artificiale & Machine Learning
              </h2>
              <p className="text-[10px] text-slate-400 mt-1">
                Visualizzazione delle metriche di validazione walk-forward (ultimo 20% test split) e controllo dell'addestramento online dei modelli predittivi.
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={fetchMlMetrics}
                disabled={mlMetricsLoading}
                className="bg-terminal-bg border border-terminal-border hover:border-terminal-accent text-slate-300 hover:text-white px-3 py-1.5 rounded text-xs font-bold transition flex items-center gap-1.5"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${mlMetricsLoading ? "animate-spin" : ""}`} />
                METRICHE
              </button>
              <button
                onClick={triggerMlRetrain}
                disabled={mlRetraining}
                className="bg-terminal-accent hover:bg-amber-500 text-black px-4 py-1.5 rounded text-xs font-black uppercase transition flex items-center gap-1.5 shadow-[0_0_8px_rgba(255,153,0,0.25)]"
              >
                <Cpu className={`h-3.5 w-3.5 ${mlRetraining ? "animate-spin" : ""}`} />
                {mlRetraining ? "ADDESTRAMENTO..." : "AVVIA RETRAIN ONLINE"}
              </button>
            </div>
          </div>

          {mlMetricsLoading ? (
            <div className="flex-1 flex items-center justify-center text-slate-400">
              <RefreshCw className="h-6 w-6 animate-spin text-terminal-accent mr-2" />
              Caricamento metriche di validazione modelli in corso...
            </div>
          ) : mlMetrics.length === 0 ? (
            <div className="flex-1 flex items-center justify-center text-xs text-slate-500 border border-dashed border-terminal-border/40 rounded p-10">
              Nessuna metrica ML salvata nel database. Avvia un retrain per calcolare le metriche iniziali.
            </div>
          ) : (
            <div className="flex-1 overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs font-mono">
                <thead>
                  <tr className="border-b border-terminal-border text-slate-500 font-bold uppercase text-[10px] tracking-wider">
                    <th className="py-2.5 px-3">Ticker</th>
                    <th className="py-2.5 px-3">Ultimo Addestramento</th>
                    <th className="py-2.5 px-3">Accuracy (Test Split)</th>
                    <th className="py-2.5 px-3">Precision</th>
                    <th className="py-2.5 px-3">Recall</th>
                    <th className="py-2.5 px-3">F1-Score</th>
                    <th className="py-2.5 px-3">Campioni</th>
                    <th className="py-2.5 px-3">Features Utilizzate</th>
                  </tr>
                </thead>
                <tbody>
                  {mlMetrics.map((metric) => (
                    <tr key={metric.ticker} className="border-b border-terminal-border/40 hover:bg-terminal-bg/30 transition text-slate-300">
                      <td className="py-2 px-3 font-bold text-slate-200 text-sm">
                        {metric.ticker}
                      </td>
                      <td className="py-2 px-3 text-[11px] text-slate-400 whitespace-nowrap">
                        {metric.last_trained ? metric.last_trained.replace("T", " ").substring(0, 19) : "N/D"}
                      </td>
                      <td className="py-2 px-3">
                        <div className="flex items-center gap-2">
                          <span className={`font-bold font-mono ${
                            metric.accuracy >= 0.60
                              ? "text-emerald-400"
                              : metric.accuracy >= 0.52
                              ? "text-amber-400"
                              : "text-rose-400"
                          }`}>
                            {(metric.accuracy * 100).toFixed(1)}%
                          </span>
                          <div className="w-16 bg-slate-800 rounded-full h-1.5 overflow-hidden hidden sm:block">
                            <div
                              className={`h-full ${
                                metric.accuracy >= 0.60
                                  ? "bg-emerald-500"
                                  : metric.accuracy >= 0.52
                                  ? "bg-amber-500"
                                  : "bg-rose-500"
                              }`}
                              style={{ width: `${Math.min(100, metric.accuracy * 100)}%` }}
                            />
                          </div>
                        </div>
                      </td>
                      <td className="py-2 px-3 font-mono font-semibold text-slate-250">
                        {(metric.precision * 100).toFixed(1)}%
                      </td>
                      <td className="py-2 px-3 font-mono font-semibold text-slate-250">
                        {(metric.recall * 100).toFixed(1)}%
                      </td>
                      <td className="py-2 px-3 font-mono font-semibold text-slate-250">
                        {(metric.f1_score * 100).toFixed(1)}%
                      </td>
                      <td className="py-2 px-3 text-slate-400 font-mono text-[11px]">
                        {metric.total_samples}
                      </td>
                      <td className="py-2 px-3">
                        <div className="flex flex-wrap gap-1 max-w-xs">
                          {Array.isArray(metric.features_used) && metric.features_used.map((feat: string, idx: number) => (
                            <span key={idx} className="bg-terminal-bg px-1.5 py-0.5 rounded text-[8px] border border-terminal-border/60 text-slate-450 uppercase font-sans">
                              {feat}
                            </span>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {mainTab === "portfolio_weights" && (
        <div className="bg-terminal-card border border-terminal-border p-4 rounded flex flex-col flex-1 min-h-[500px]">
          <div className="flex justify-between items-center border-b border-terminal-border pb-3 mb-4">
            <div>
              <h2 className="text-xs font-black uppercase text-slate-200 flex items-center gap-1.5">
                <PieChart className="h-4 w-4 text-terminal-accent" />
                Portfolio Optimization (Markowitz MVO)
              </h2>
              <p className="text-[10px] text-slate-400 mt-1">
                Asset allocation ottimizzata per Max Sharpe Ratio calcolata dal motore quantistico
              </p>
            </div>
            <button
              onClick={fetchPortfolioWeights}
              className="bg-terminal-bg border border-terminal-border hover:border-terminal-accent text-slate-300 hover:text-white px-3 py-1.5 rounded text-[10px] font-bold transition flex items-center gap-1.5"
            >
              <RefreshCw className="h-3 w-3" />
              AGGIORNA
            </button>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {globalPortfolioWeights.length === 0 ? (
              <div className="text-slate-500 italic col-span-3 p-4 bg-terminal-bg rounded border border-terminal-border">
                Nessun peso calcolato di recente. Il worker deve ancora terminare l'ottimizzazione.
              </div>
            ) : (
              globalPortfolioWeights.map((w: any) => (
                <div key={w.ticker} className="bg-terminal-bg border border-terminal-border/50 rounded p-3 flex flex-col gap-2 relative overflow-hidden group">
                  <div className="absolute top-0 left-0 h-full bg-terminal-accent/10 transition-all duration-500 ease-out" style={{ width: `${w.weight * 100}%` }}></div>
                  <div className="flex justify-between items-center z-10">
                    <span className="text-white font-black text-sm">{w.ticker}</span>
                    <span className="text-terminal-accent font-bold text-lg">{(w.weight * 100).toFixed(1)}%</span>
                  </div>
                  <div className="flex flex-col z-10">
                    <span className="text-slate-400 text-[10px] truncate">{w.name}</span>
                    <span className="text-slate-500 text-[9px] uppercase tracking-wider">{w.sector}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {mainTab === "hedging" && (
        <div className="bg-terminal-card border border-terminal-border p-4 rounded flex flex-col flex-1 min-h-[500px]">
          <div className="flex justify-between items-center border-b border-terminal-border pb-3 mb-4">
            <div>
              <h2 className="text-xs font-black uppercase text-slate-200 flex items-center gap-1.5">
                <ShieldAlert className="h-4 w-4 text-terminal-accent" />
                Black-Scholes Options Hedging
              </h2>
              <p className="text-[10px] text-slate-400 mt-1">
                Suggerimenti per opzioni Put difensive calcolate in scenari di alta volatilità
              </p>
            </div>
            <button
              onClick={fetchHedgingStrategies}
              className="bg-terminal-bg border border-terminal-border hover:border-terminal-accent text-slate-300 hover:text-white px-3 py-1.5 rounded text-[10px] font-bold transition flex items-center gap-1.5"
            >
              <RefreshCw className="h-3 w-3" />
              AGGIORNA
            </button>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-4">
            {hedgingStrategies.length === 0 ? (
              <div className="text-slate-500 italic col-span-2 p-4 bg-terminal-bg rounded border border-terminal-border">
                Nessuna strategia di Hedging attiva. La volatilità di mercato (V2TX) è sotto la soglia di allerta.
              </div>
            ) : (
              hedgingStrategies.map((s: any, idx: number) => (
                <div key={`${s.ticker}-${s.option_type}-${idx}`} className="bg-terminal-bg border border-terminal-border rounded p-4 flex flex-col gap-3">
                  <div className="flex justify-between items-center border-b border-slate-700/50 pb-2">
                    <span className="text-white font-black text-lg">{s.ticker} <span className="text-xs text-slate-400 font-normal ml-1">{s.name}</span></span>
                    <span className="text-terminal-accent font-bold px-2 py-0.5 bg-terminal-accent/10 rounded text-xs border border-terminal-accent/30">{s.option_type}</span>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
                    <div className="flex justify-between"><span className="text-slate-500">Strike Price:</span> <span className="text-slate-200 font-mono">€ {s.strike.toFixed(2)}</span></div>
                    <div className="flex justify-between"><span className="text-slate-500">Scadenza:</span> <span className="text-slate-200 font-mono">{s.expiry_days} Giorni</span></div>
                    <div className="flex justify-between"><span className="text-slate-500">Prezzo B-S:</span> <span className="text-red-400 font-mono font-bold">€ {s.theoretical_price.toFixed(4)}</span></div>
                  </div>
                  
                  <div className="mt-2 pt-2 border-t border-slate-700/50 grid grid-cols-4 gap-2 text-[10px]">
                    <div className="flex flex-col items-center"><span className="text-slate-500 uppercase">Delta</span><span className="text-slate-300 font-mono">{s.delta ? s.delta.toFixed(4) : 'N/A'}</span></div>
                    <div className="flex flex-col items-center"><span className="text-slate-500 uppercase">Gamma</span><span className="text-slate-300 font-mono">{s.gamma ? s.gamma.toFixed(4) : 'N/A'}</span></div>
                    <div className="flex flex-col items-center"><span className="text-slate-500 uppercase">Theta</span><span className="text-slate-300 font-mono">{s.theta ? s.theta.toFixed(4) : 'N/A'}</span></div>
                    <div className="flex flex-col items-center"><span className="text-slate-500 uppercase">Vega</span><span className="text-slate-300 font-mono">{s.vega ? s.vega.toFixed(4) : 'N/A'}</span></div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {mainTab === "live_trading" && (
        <div className="bg-terminal-card border border-terminal-border p-4 rounded flex flex-col flex-1 min-h-[500px]">
          <div className="flex justify-between items-center border-b border-terminal-border pb-3 mb-4">
            <div>
              <h2 className="text-xs font-black uppercase text-red-500 flex items-center gap-1.5 animate-pulse">
                <Crosshair className="h-4 w-4" />
                EuroQuant Live Execution Engine
              </h2>
              <p className="text-[10px] text-slate-400 mt-1">
                Portafoglio reale e storico ordini eseguiti sul broker istituzionale
              </p>
            </div>
            <button
              onClick={fetchLiveTrading}
              className="bg-terminal-bg border border-terminal-border hover:border-terminal-accent text-slate-300 hover:text-white px-3 py-1.5 rounded text-[10px] font-bold transition flex items-center gap-1.5"
            >
              <RefreshCw className="h-3 w-3" />
              SINC PORTAFOGLIO
            </button>
          </div>
          
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Live Positions */}
            <div className="flex flex-col gap-3">
              <h3 className="text-xs font-black text-white border-b border-slate-700/50 pb-2">POSIZIONI APERTE</h3>
              {livePositions.length === 0 ? (
                <div className="text-slate-500 italic p-4 bg-terminal-bg rounded border border-terminal-border text-sm text-center">
                  Nessuna posizione aperta sul broker.
                </div>
              ) : (
                <div className="flex flex-col gap-2">
                  {livePositions.map((p: any) => (
                    <div key={p.ticker} className="flex justify-between items-center bg-terminal-bg border border-slate-700/50 p-3 rounded">
                      <div className="flex flex-col">
                        <span className="font-bold text-white text-sm">{p.ticker} <span className="text-xs font-normal text-slate-500 ml-1">{p.name}</span></span>
                        <span className="text-xs text-slate-400">Qty: <span className="font-mono text-slate-200">{p.quantity}</span> @ <span className="font-mono text-slate-200">€{p.avg_price.toFixed(2)}</span></span>
                      </div>
                      <div className="flex flex-col items-end">
                        <span className="text-xs text-slate-500 uppercase">Unrealized P&L</span>
                        <span className={`font-mono font-bold ${p.unrealized_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                          {p.unrealized_pnl >= 0 ? '+' : ''}€{p.unrealized_pnl.toFixed(2)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            
            {/* Execution Logs */}
            <div className="flex flex-col gap-3">
              <h3 className="text-xs font-black text-white border-b border-slate-700/50 pb-2">ULTIMI ORDINI ESEGUITI</h3>
              {executionLogs.length === 0 ? (
                <div className="text-slate-500 italic p-4 bg-terminal-bg rounded border border-terminal-border text-sm text-center">
                  Nessun ordine eseguito di recente.
                </div>
              ) : (
                <div className="flex flex-col gap-2 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
                  {executionLogs.map((l: any) => (
                    <div key={l.id} className="flex justify-between items-center bg-terminal-bg border border-slate-700/50 p-2 rounded text-xs">
                      <div className="flex items-center gap-3">
                        <span className={`font-black px-2 py-0.5 rounded ${l.action === 'BUY' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                          {l.action}
                        </span>
                        <span className="font-bold text-slate-200">{l.ticker}</span>
                      </div>
                      <div className="flex items-center gap-4">
                        <span className="font-mono text-slate-400">{l.quantity} px @ €{l.fill_price.toFixed(2)}</span>
                        <span className="text-slate-500 text-[9px]">{new Date(l.timestamp).toLocaleTimeString()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {mainTab === "system_logs" && (
        <div className="bg-terminal-card border border-terminal-border p-4 rounded flex flex-col flex-1 min-h-[500px]">
          <div className="flex justify-between items-center border-b border-terminal-border pb-3 mb-4">
            <div>
              <h2 className="text-xs font-black uppercase text-slate-200 flex items-center gap-1.5">
                🖥️ Docker Terminal Logs
              </h2>
              <p className="text-[10px] text-slate-400 mt-1">
                Monitor in tempo reale delle attività dei container in background (Worker, NLP, Sync)
              </p>
            </div>
            <button
              onClick={fetchSystemLogs}
              className="bg-terminal-bg border border-terminal-border hover:border-terminal-accent text-slate-300 hover:text-white px-3 py-1.5 rounded text-[10px] font-bold transition flex items-center gap-1.5"
            >
              <RefreshCw className="h-3 w-3" />
              AGGIORNA
            </button>
          </div>
          
          <div className="flex-1 bg-black rounded p-3 font-mono text-[10px] overflow-y-auto border border-terminal-border/30">
            {systemLogs.length === 0 ? (
              <div className="text-slate-500 italic">Nessun log presente...</div>
            ) : (
              <div className="flex flex-col gap-1">
                {systemLogs.map((log) => (
                  <div key={log.id} className="flex gap-2">
                    <span className="text-slate-500 shrink-0">
                      {log.timestamp.replace("T", " ").substring(0, 19)}
                    </span>
                    <span className={`shrink-0 w-12 font-bold ${
                      log.level === "ERROR" ? "text-rose-500" :
                      log.level === "WARN" ? "text-amber-500" :
                      "text-emerald-500"
                    }`}>
                      [{log.level}]
                    </span>
                    <span className="text-slate-400 shrink-0 w-16">[{log.source}]</span>
                    <span className={`${log.level === "ERROR" ? "text-rose-400 font-bold" : "text-slate-300"}`}>
                      {log.message}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 4. Stock Detail Modal (Explainable AI reasoning) */}
      {selectedTicker && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-fadeIn">
          <div className="bg-terminal-card border border-terminal-border rounded-lg max-w-5xl w-full flex flex-col max-h-[90vh] overflow-hidden shadow-2xl">
            
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 border-b border-terminal-border bg-terminal-bg/50">
              {stockDetail ? (
                <div className="flex flex-wrap items-center gap-3">
                  <div>
                    <h2 className="text-sm font-black text-terminal-accent tracking-wider">{stockDetail.name}</h2>
                    <div className="text-xs text-terminal-muted flex items-center gap-2">
                      <span>{stockDetail.ticker}</span> • <span>{stockDetail.sector} ({stockDetail.industry})</span> • <span>{stockDetail.country}</span>
                    </div>
                  </div>
                  <span className={`px-2.5 py-1 rounded text-xs uppercase font-extrabold ${getSignalBadge(stockDetail.signal)}`}>
                    {stockDetail.signal}
                  </span>
                  <div className="text-right ml-4">
                    <span className="font-mono text-sm font-bold">€ {stockDetail.price.toFixed(2)}</span>
                    <span className={`text-xs ml-2 font-mono ${stockDetail.price_change_24h >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {stockDetail.price_change_24h >= 0 ? "+" : ""}{stockDetail.price_change_24h.toFixed(2)}%
                    </span>
                  </div>
                </div>
              ) : (
                <span className="text-xs text-terminal-muted">Caricamento scheda di dettaglio...</span>
              )}
              
              <button 
                onClick={() => setSelectedTicker(null)}
                className="p-1.5 bg-terminal-bg border border-terminal-border hover:border-rose-500 hover:text-rose-400 text-slate-400 rounded transition"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Modal Content */}
            {detailLoading ? (
              <div className="p-20 flex flex-col items-center justify-center gap-3 text-xs text-terminal-muted">
                <RefreshCw className="h-8 w-8 animate-spin text-terminal-accent" />
                <span>Analisi quantitativa e sentiment in corso...</span>
              </div>
            ) : stockDetail ? (
              <div className="grid grid-cols-1 lg:grid-cols-5 divide-y lg:divide-y-0 lg:divide-x divide-terminal-border overflow-hidden flex-1">
                
                {/* Left side: Chart and Technical indicators (3 columns) */}
                <div className="lg:col-span-3 p-4 overflow-y-auto flex flex-col gap-4">
                  <div className="flex justify-between items-center">
                    <h3 className="text-[10px] font-black uppercase text-slate-400 tracking-wider">
                      Price Chart & Technical Trend Indicators
                    </h3>
                    <div className="flex gap-2 items-center">
                      {chartTab === "price" && (
                        <label className="flex items-center gap-1 text-[9px] font-bold text-slate-400 cursor-pointer hover:text-white uppercase select-none mr-2">
                          <input
                            type="checkbox"
                            checked={showBollinger}
                            onChange={(e) => setShowBollinger(e.target.checked)}
                            className="rounded border-terminal-border bg-black text-terminal-accent focus:ring-0 focus:ring-offset-0 h-3 w-3"
                          />
                          Bande di Bollinger
                        </label>
                      )}
                      <div className="flex gap-1 bg-terminal-bg p-0.5 rounded border border-terminal-border">
                        <button
                          onClick={() => setChartTab("price")}
                          className={`px-2 py-0.5 text-[9px] uppercase font-bold rounded transition ${
                            chartTab === "price" ? "bg-terminal-accent text-black" : "text-slate-400 hover:text-white"
                          }`}
                        >
                          Prezzo & SMA
                        </button>
                        <button
                          onClick={() => setChartTab("rsi")}
                          className={`px-2 py-0.5 text-[9px] uppercase font-bold rounded transition ${
                            chartTab === "rsi" ? "bg-terminal-accent text-black" : "text-slate-400 hover:text-white"
                          }`}
                        >
                          RSI
                        </button>
                        <button
                          onClick={() => setChartTab("macd")}
                          className={`px-2 py-0.5 text-[9px] uppercase font-bold rounded transition ${
                            chartTab === "macd" ? "bg-terminal-accent text-black" : "text-slate-400 hover:text-white"
                          }`}
                        >
                          MACD
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Chart */}
                  <div className="h-60 bg-terminal-bg rounded border border-terminal-border p-2 shrink-0">
                    {stockDetail.history && stockDetail.history.length > 0 ? (
                      chartTab === "price" ? (
                        <ResponsiveContainer width="99%" height="100%" key={`price-${stockDetail.ticker}`}>
                          <ComposedChart data={getChartData()}>
                            <defs>
                              <linearGradient id="colorClose" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#FF9900" stopOpacity={0.2}/>
                                <stop offset="95%" stopColor="#FF9900" stopOpacity={0}/>
                              </linearGradient>
                            </defs>
                            <XAxis dataKey="date" stroke="#64748B" fontSize={10} tickLine={false} />
                            <YAxis stroke="#64748B" fontSize={10} domain={["auto", "auto"]} orientation="right" tickLine={false} />
                            <Tooltip 
                              contentStyle={{ backgroundColor: "#151922", borderColor: "#232936", color: "#E2E8F0" }} 
                              labelClassName="font-bold text-[10px] text-terminal-accent"
                            />
                            <Area type="monotone" dataKey="close" stroke="#FF9900" strokeWidth={2} fillOpacity={1} fill="url(#colorClose)" name="Prezzo" />
                            <Line type="monotone" dataKey="sma_20" stroke="#00E676" strokeWidth={1} dot={false} name="SMA 20" />
                            <Line type="monotone" dataKey="sma_50" stroke="#00B0FF" strokeWidth={1} dot={false} name="SMA 50" />
                            <Line type="monotone" dataKey="sma_200" stroke="#D500F9" strokeWidth={1} dot={false} name="SMA 200" />
                            {showBollinger && (
                              <>
                                <Line type="monotone" dataKey="bb_upper" stroke="#FF5722" strokeWidth={1.2} strokeDasharray="3 3" dot={false} name="Banda Superiore" />
                                <Line type="monotone" dataKey="bb_lower" stroke="#FF5722" strokeWidth={1.2} strokeDasharray="3 3" dot={false} name="Banda Inferiore" />
                              </>
                            )}
                          </ComposedChart>
                        </ResponsiveContainer>
                      ) : chartTab === "rsi" ? (
                        <ResponsiveContainer width="99%" height="100%" key={`rsi-${stockDetail.ticker}`}>
                          <LineChart data={stockDetail.history}>
                            <XAxis dataKey="date" stroke="#64748B" fontSize={10} tickLine={false} />
                            <YAxis stroke="#64748B" fontSize={10} domain={[0, 100]} orientation="right" tickLine={false} />
                            <Tooltip 
                              contentStyle={{ backgroundColor: "#151922", borderColor: "#232936", color: "#E2E8F0" }} 
                              labelClassName="font-bold text-[10px] text-terminal-accent"
                            />
                            <ReferenceLine y={70} stroke="#EF4444" strokeDasharray="3 3" label={{ value: '70', fill: '#EF4444', fontSize: 9, position: 'insideRight' }} />
                            <ReferenceLine y={50} stroke="#64748B" strokeDasharray="3 3" />
                            <ReferenceLine y={30} stroke="#10B981" strokeDasharray="3 3" label={{ value: '30', fill: '#10B981', fontSize: 9, position: 'insideRight' }} />
                            <Line type="monotone" dataKey="rsi" stroke="#FF9900" strokeWidth={2} dot={false} name="RSI (14)" />
                          </LineChart>
                        </ResponsiveContainer>
                      ) : (
                        <ResponsiveContainer width="99%" height="100%" key={`macd-${stockDetail.ticker}`}>
                          <ComposedChart data={stockDetail.history}>
                            <XAxis dataKey="date" stroke="#64748B" fontSize={10} tickLine={false} />
                            <YAxis stroke="#64748B" fontSize={10} domain={["auto", "auto"]} orientation="right" tickLine={false} />
                            <Tooltip 
                              contentStyle={{ backgroundColor: "#151922", borderColor: "#232936", color: "#E2E8F0" }} 
                              labelClassName="font-bold text-[10px] text-terminal-accent"
                            />
                            <Legend verticalAlign="top" height={24} iconSize={8} wrapperStyle={{ fontSize: 9 }} />
                            <Bar dataKey={(row) => (row.macd && row.macd_signal) ? row.macd - row.macd_signal : 0} fill="#64748B" name="MACD Hist" />
                            <Line type="monotone" dataKey="macd" stroke="#00E676" strokeWidth={1.5} dot={false} name="MACD" />
                            <Line type="monotone" dataKey="macd_signal" stroke="#D500F9" strokeWidth={1.5} dot={false} name="Segnale" />
                          </ComposedChart>
                        </ResponsiveContainer>
                      )
                    ) : (
                      <div className="h-full flex items-center justify-center text-xs text-terminal-muted">
                        Nessun dato storico dei prezzi disponibile per il grafico.
                      </div>
                    )}
                  </div>

                  {/* Technicals Stats Grid */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    <div className="bg-terminal-bg/50 border border-terminal-border p-2.5 rounded text-center">
                      <div className="text-[10px] text-terminal-muted uppercase">RSI (14)</div>
                      <div className="font-mono text-sm font-black mt-1">
                        {stockDetail.history && stockDetail.history.length > 0 && stockDetail.history[stockDetail.history.length-1].rsi
                          ? stockDetail.history[stockDetail.history.length-1].rsi.toFixed(2)
                          : "N/D"}
                      </div>
                      <div className="text-[9px] mt-0.5 text-terminal-accent font-bold">
                        {stockDetail.history && stockDetail.history.length > 0 && stockDetail.history[stockDetail.history.length-1].rsi
                          ? stockDetail.history[stockDetail.history.length-1].rsi > 70 ? "OVERBOUGHT" : stockDetail.history[stockDetail.history.length-1].rsi < 30 ? "OVERSOLD" : "NEUTRAL"
                          : ""}
                      </div>
                    </div>

                    <div className="bg-terminal-bg/50 border border-terminal-border p-2.5 rounded text-center">
                      <div className="text-[10px] text-terminal-muted uppercase">MACD</div>
                      <div className="font-mono text-sm font-black mt-1">
                        {stockDetail.history && stockDetail.history.length > 0 && stockDetail.history[stockDetail.history.length-1].macd
                          ? stockDetail.history[stockDetail.history.length-1].macd.toFixed(4)
                          : "N/D"}
                      </div>
                      <div className="text-[9px] mt-0.5 text-slate-400 font-mono">
                        Sig: {stockDetail.history && stockDetail.history.length > 0 && stockDetail.history[stockDetail.history.length-1].macd_signal
                          ? stockDetail.history[stockDetail.history.length-1].macd_signal.toFixed(4)
                          : "N/D"}
                      </div>
                    </div>

                    <div className="bg-terminal-bg/50 border border-terminal-border p-2.5 rounded text-center">
                      <div className="text-[10px] text-terminal-muted uppercase">Sentiment Z-Score</div>
                      <div className={`font-mono text-sm font-black mt-1 ${
                        stockDetail.sentiment_score > 0.4 ? "text-emerald-400" : stockDetail.sentiment_score < -0.4 ? "text-rose-400" : "text-slate-300"
                      }`}>
                        {stockDetail.sentiment_score >= 0 ? "+" : ""}{stockDetail.sentiment_score.toFixed(3)}
                      </div>
                      <div className="text-[9px] mt-0.5 text-slate-400 uppercase">Aggregato 48h</div>
                    </div>

                    <div className="bg-terminal-bg/50 border border-terminal-border p-2.5 rounded text-center">
                      <div className="text-[10px] text-terminal-muted uppercase">Trend (SMA 20/50)</div>
                      <div className="font-mono text-sm font-black mt-1 flex items-center justify-center gap-1">
                        {stockDetail.history && stockDetail.history.length > 0 
                          ? stockDetail.price > stockDetail.history[stockDetail.history.length-1].sma_50 
                            ? <span className="text-emerald-400">BULLISH</span>
                            : <span className="text-rose-400">BEARISH</span>
                          : "N/D"}
                      </div>
                      <div className="text-[9px] mt-0.5 text-slate-400">vs SMA50</div>
                    </div>
                  </div>

                  {/* AI sentiment summary */}
                  <div className="bg-terminal-bg/50 border border-terminal-border/80 p-3 rounded shadow-md">
                    <h4 className="text-[10px] font-black uppercase text-terminal-accent tracking-wider mb-1 flex items-center gap-1.5">
                      🤖 Sintesi Sentiment (AI locale)
                    </h4>
                    {llmSummaryLoading ? (
                      <div className="text-[10px] text-terminal-muted flex items-center gap-1.5 py-1">
                        <RefreshCw className="h-3 w-3 animate-spin text-terminal-accent" />
                        <span>Generazione analisi in corso da Ollama locale...</span>
                      </div>
                    ) : llmSummary ? (
                      <p className="text-[10px] text-slate-350 leading-relaxed font-mono whitespace-pre-wrap">
                        {llmSummary}
                      </p>
                    ) : (
                      <p className="text-[10px] text-terminal-muted italic">
                        Nessuna sintesi generata o Ollama non raggiungibile.
                      </p>
                    )}
                  </div>

                  {/* News list mapped to this stock */}
                  <div>
                    <h4 className="text-[10px] font-black uppercase text-slate-400 tracking-wider mb-2">
                      Specific News Coverage
                    </h4>
                    <div className="space-y-2 max-h-32 overflow-y-auto pr-1">
                      {news.filter(art => art.tickers.includes(selectedTicker)).map(art => (
                        <div key={art.id} className="p-2 border border-terminal-border rounded bg-terminal-bg/30 text-xs flex justify-between items-start gap-3">
                          <div>
                            <div className="font-bold text-slate-200">{art.title}</div>
                            <span className="text-[10px] text-terminal-muted">
                              {art.source} • {(() => {
                                const d = new Date(art.published_date);
                                const year = d.getUTCFullYear();
                                const month = String(d.getUTCMonth() + 1).padStart(2, '0');
                                const day = String(d.getUTCDate()).padStart(2, '0');
                                const hours = String(d.getUTCHours()).padStart(2, '0');
                                const minutes = String(d.getUTCMinutes()).padStart(2, '0');
                                return `${year}-${month}-${day} ${hours}:${minutes} Z`;
                              })()}
                            </span>
                          </div>
                          {art.sentiment_label && (
                            <span className={`text-[9px] px-1.5 rounded uppercase font-bold shrink-0 ${
                              art.sentiment_label === "positive" ? "text-emerald-400 bg-emerald-950/20" : art.sentiment_label === "negative" ? "text-rose-400 bg-rose-950/20" : "text-slate-400"
                            }`}>
                              {art.sentiment_label}
                            </span>
                          )}
                        </div>
                      ))}
                      {news.filter(art => art.tickers.includes(selectedTicker)).length === 0 && (
                        <div className="text-center py-4 text-terminal-muted text-[10px] border border-dashed border-terminal-border rounded">
                          Nessuna notizia recente specificamente mappata a questo ticker nelle ultime 48 ore.
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Risk & Hedging Card */}
                  <div className="bg-terminal-bg/50 border border-terminal-border p-3 rounded">
                    <div className="flex items-center gap-2 mb-2">
                      <ShieldAlert className="h-4 w-4 text-terminal-accent" />
                      <h4 className="text-[10px] font-black uppercase text-slate-200 tracking-wider">
                        Risk & Hedging Analysis (Benchmark: ^STOXX)
                      </h4>
                    </div>
                    <div className="grid grid-cols-2 gap-4 mb-2">
                      <div className="bg-terminal-card/50 border border-terminal-border p-2 rounded">
                        <span className="text-[9px] text-terminal-muted uppercase block">Beta (60gg vs ^STOXX)</span>
                        <span className="font-mono text-xs font-black text-white">{stockDetail.beta.toFixed(2)}</span>
                        <span className="text-[8px] text-slate-400 block mt-0.5">
                          {stockDetail.beta > 1.2 ? "Alta sensibilità di mercato" : stockDetail.beta < 0.8 ? "Titolo difensivo" : "Sensibilità standard"}
                        </span>
                      </div>
                      <div className="bg-terminal-card/50 border border-terminal-border p-2 rounded">
                        <span className="text-[9px] text-terminal-muted uppercase block">Correlazione Sentiment/Ritorno</span>
                        <span className="font-mono text-xs font-black text-white">
                          {stockDetail.correlation !== null ? stockDetail.correlation.toFixed(3) : "N/D"}
                        </span>
                        <span className="text-[8px] text-slate-400 block mt-0.5">
                          {stockDetail.correlation !== null 
                            ? stockDetail.correlation > 0.3 ? "Correlazione positiva" : stockDetail.correlation < -0.3 ? "Correlazione inversa" : "Correlazione debole"
                            : "Dati insufficienti"}
                        </span>
                      </div>
                    </div>
                    <p className="text-[10px] text-slate-300 italic border-l-2 border-terminal-accent pl-2 bg-terminal-bg/30 p-2 rounded mt-2">
                      {stockDetail.hedging_suggestion}
                    </p>
                  </div>

                  {/* MetaTrader 5 Integration Card */}
                  <div className="bg-terminal-bg/50 border border-terminal-border p-3 rounded flex flex-col gap-2">
                    <div className="flex items-center gap-2 mb-1">
                      <Cpu className="h-4 w-4 text-terminal-accent" />
                      <h4 className="text-[10px] font-black uppercase text-slate-200 tracking-wider">
                        Integrazione MetaTrader 5 (MT5 Bridge)
                      </h4>
                    </div>

                    <div className="grid grid-cols-6 gap-2 text-center text-[10px]">
                      <div className="bg-terminal-card border border-terminal-border p-1.5 rounded">
                        <span className="text-[8px] text-terminal-muted block uppercase">MT5 Symbol</span>
                        <span className="font-mono text-[10px] font-black text-white">{stockDetail.mt5_symbol}</span>
                      </div>
                      <div className="bg-terminal-card border border-terminal-border p-1.5 rounded">
                        <span className="text-[8px] text-terminal-muted block uppercase">Azione</span>
                        <span className={`font-mono text-[10px] font-black uppercase ${
                          stockDetail.signal === "BUY" ? "text-emerald-400" : stockDetail.signal === "SELL" ? "text-rose-400" : "text-slate-400"
                        }`}>{stockDetail.signal}</span>
                      </div>
                      <div className="bg-terminal-card border border-terminal-border p-1.5 rounded">
                        <span className="text-[8px] text-terminal-muted block uppercase">ML Confidenza</span>
                        <span className="font-mono text-[10px] font-black text-slate-200">
                          🧠 {stockDetail.ml_prediction_prob ? `${(stockDetail.ml_prediction_prob * 100).toFixed(0)}%` : "50%"}
                        </span>
                      </div>
                      <div className="bg-terminal-card border border-terminal-border p-1.5 rounded">
                        <span className="text-[8px] text-terminal-muted block uppercase">Kelly Sizing</span>
                        <span className="font-mono text-[10px] font-black text-amber-400">
                          ⚖️ {stockDetail.kelly_factor ? `${(stockDetail.kelly_factor * 100).toFixed(1)}%` : "N/D"}
                        </span>
                      </div>
                      <div className="bg-terminal-card border border-terminal-border p-1.5 rounded">
                        <span className="text-[8px] text-terminal-muted block uppercase">Chandelier Exit SL</span>
                        <span className="font-mono text-[10px] font-bold text-rose-400">
                          {stockDetail.stop_loss > 0 ? stockDetail.stop_loss.toFixed(4) : "N/D"}
                        </span>
                      </div>
                      <div className="bg-terminal-card border border-terminal-border p-1.5 rounded">
                        <span className="text-[8px] text-terminal-muted block uppercase">Take Profit (TP)</span>
                        <span className="font-mono text-[10px] font-bold text-emerald-400">
                          {stockDetail.take_profit > 0 ? stockDetail.take_profit.toFixed(4) : "N/D"}
                        </span>
                      </div>
                    </div>

                    {/* Manual Signal Override Section */}
                    <div className="border-t border-terminal-border/40 pt-2 mt-1 flex flex-col gap-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-[9px] font-black uppercase text-slate-300">Override Segnale Manuale</span>
                        {activeOverrides[stockDetail.ticker] && (
                          <span className="text-[8px] text-terminal-accent uppercase font-mono font-bold animate-pulse">
                            Override Attivo ({activeOverrides[stockDetail.ticker].action})
                          </span>
                        )}
                      </div>
                      <div className="grid grid-cols-4 gap-1">
                        <button
                          onClick={() => handleSetOverride(stockDetail.ticker, "BUY")}
                          className={`px-2 py-1 text-[8px] font-black rounded uppercase transition ${
                            activeOverrides[stockDetail.ticker]?.action === "BUY"
                              ? "bg-emerald-500 text-black shadow-lg shadow-emerald-500/20"
                              : "bg-terminal-card text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/10"
                          }`}
                        >
                          FORZA BUY
                        </button>
                        <button
                          onClick={() => handleSetOverride(stockDetail.ticker, "SELL")}
                          className={`px-2 py-1 text-[8px] font-black rounded uppercase transition ${
                            activeOverrides[stockDetail.ticker]?.action === "SELL"
                              ? "bg-rose-500 text-black shadow-lg shadow-rose-500/20"
                              : "bg-terminal-card text-rose-400 border border-rose-500/30 hover:bg-rose-500/10"
                          }`}
                        >
                          FORZA SELL
                        </button>
                        <button
                          onClick={() => handleSetOverride(stockDetail.ticker, "HOLD")}
                          className={`px-2 py-1 text-[8px] font-black rounded uppercase transition ${
                            activeOverrides[stockDetail.ticker]?.action === "HOLD"
                              ? "bg-slate-500 text-black shadow-lg shadow-slate-500/20"
                              : "bg-terminal-card text-slate-400 border border-slate-500/30 hover:bg-slate-500/10"
                          }`}
                        >
                          FORZA HOLD
                        </button>
                        <button
                          onClick={() => handleSetOverride(stockDetail.ticker, "CLEAR")}
                          disabled={!activeOverrides[stockDetail.ticker]}
                          className="px-2 py-1 text-[8px] font-black rounded uppercase transition bg-terminal-card text-slate-400 border border-terminal-border hover:bg-white/5 disabled:opacity-30 disabled:hover:bg-transparent"
                        >
                          RESET
                        </button>
                      </div>
                    </div>

                    {/* Code Snippet for MQL5 WebRequest */}
                    <div className="mt-1">
                      <span className="text-[9px] text-slate-400 block mb-1">Snippet MQL5 (da copiare nel tuo EA):</span>
                      <pre className="p-2 bg-black border border-terminal-border rounded text-[9px] font-mono text-slate-300 overflow-x-auto max-h-28 whitespace-pre leading-normal">
{`// Integrazione Segnale EuroQuant
string url = "http://localhost:8000/api/mt5/signals?ticker=${stockDetail.ticker}";
char post[], result[];
string headers;
ResetLastError();
int res = WebRequest("GET", url, NULL, NULL, 3000, post, 0, result, headers);
if (res > 0) {
   string json_resp = CharArrayToString(result);
   Print("Segnale Ricevuto: ", json_resp);
   // Esegui parsing di Action, Entry, SL, TP
} else {
   Print("Errore API EuroQuant: ", GetLastError());
}`}
                      </pre>
                    </div>
                  </div>

                  {/* Quantitative Backtester Panel */}
                  <div className="bg-terminal-bg/50 border border-terminal-border p-3 rounded flex flex-col gap-2">
                    <div className="flex items-center justify-between border-b border-terminal-border pb-2">
                      <div className="flex items-center gap-2">
                        <Play className="h-4 w-4 text-terminal-accent" />
                        <h4 className="text-[10px] font-black uppercase text-slate-200 tracking-wider">
                          Quantitative Backtest Simulator (RSI + Sentiment)
                        </h4>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={optimizeParameters}
                          disabled={optimizationLoading || !selectedTicker}
                          className="border border-terminal-accent text-terminal-accent hover:bg-terminal-accent hover:text-black px-2 py-1 text-[9px] font-black uppercase rounded transition disabled:opacity-50"
                        >
                          {optimizationLoading ? "Calcolo..." : "💡 Ottimizza"}
                        </button>
                        <button
                          onClick={runBacktest}
                          disabled={backtestLoading}
                          className="bg-terminal-accent text-black px-3 py-1 text-[9px] font-black uppercase rounded hover:bg-white transition disabled:opacity-50"
                        >
                          {backtestLoading ? "Simulazione..." : "Esegui Backtest"}
                        </button>
                      </div>
                    </div>

                    {/* Params grid */}
                    <div className="grid grid-cols-4 gap-2 text-[10px]">
                      <div>
                        <label className="text-terminal-muted block mb-0.5 text-[8px] uppercase">RSI Acquisto (≤)</label>
                        <input
                          type="number"
                          value={backtestBuyRsi}
                          onChange={(e) => setBacktestBuyRsi(Number(e.target.value))}
                          className="w-full bg-terminal-card border border-terminal-border rounded p-1 font-mono text-white text-center text-[10px]"
                        />
                      </div>
                      <div>
                        <label className="text-terminal-muted block mb-0.5 text-[8px] uppercase">RSI Vendita (≥)</label>
                        <input
                          type="number"
                          value={backtestSellRsi}
                          onChange={(e) => setBacktestSellRsi(Number(e.target.value))}
                          className="w-full bg-terminal-card border border-terminal-border rounded p-1 font-mono text-white text-center text-[10px]"
                        />
                      </div>
                      <div>
                        <label className="text-terminal-muted block mb-0.5 text-[8px] uppercase">Sent. Acquisto (≥)</label>
                        <input
                          type="number"
                          step="0.05"
                          value={backtestBuySent}
                          onChange={(e) => setBacktestBuySent(Number(e.target.value))}
                          className="w-full bg-terminal-card border border-terminal-border rounded p-1 font-mono text-white text-center text-[10px]"
                        />
                      </div>
                      <div>
                        <label className="text-terminal-muted block mb-0.5 text-[8px] uppercase">Sent. Vendita (≤)</label>
                        <input
                          type="number"
                          step="0.05"
                          value={backtestSellSent}
                          onChange={(e) => setBacktestSellSent(Number(e.target.value))}
                          className="w-full bg-terminal-card border border-terminal-border rounded p-1 font-mono text-white text-center text-[10px]"
                        />
                      </div>
                    </div>

                    {/* Optimization results grid */}
                    {optimizationResults && optimizationResults.top_configs && (
                      <div className="bg-terminal-card border border-terminal-border/60 p-2.5 rounded text-[10px] space-y-2">
                        <div className="flex justify-between items-center border-b border-terminal-border/30 pb-1">
                          <span className="font-bold text-terminal-accent uppercase text-[9px]">💡 Top 3 Configs Ottimizzate ({optimizationResults.ticker})</span>
                          <button
                            onClick={() => setOptimizationResults(null)}
                            className="text-slate-400 hover:text-white text-[8px]"
                          >
                            Chiudi
                          </button>
                        </div>
                        <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
                          {optimizationResults.top_configs.map((config: any, index: number) => (
                            <div key={index} className="flex items-center justify-between p-1.5 bg-terminal-bg/40 rounded border border-terminal-border/20">
                              <div className="flex flex-col gap-0.5 text-left">
                                <div className="font-semibold text-slate-300">
                                  Config #{index + 1}: Sharpe {config.sharpe_ratio.toFixed(2)} | Ritorno {config.total_return >= 0 ? "+" : ""}{config.total_return}%
                                </div>
                                <div className="text-[8px] text-terminal-muted">
                                  RSI: {config.buy_rsi}/{config.sell_rsi} | Sent: {config.buy_sentiment}/{config.sell_sentiment} | Max DD: -{config.max_drawdown}%
                                </div>
                              </div>
                              <button
                                onClick={() => {
                                  setBacktestBuyRsi(config.buy_rsi);
                                  setBacktestSellRsi(config.sell_rsi);
                                  setBacktestBuySent(config.buy_sentiment);
                                  setBacktestSellSent(config.sell_sentiment);
                                  setOptimizationResults(null);
                                }}
                                className="bg-slate-800 hover:bg-terminal-accent hover:text-black px-2 py-0.5 text-[8px] font-bold uppercase rounded transition text-white"
                              >
                                Applica
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Simulation Results */}
                    {backtestResults && (
                      <div className="mt-2 space-y-2">
                        <div className="grid grid-cols-5 gap-1 text-center">
                          <div className="bg-terminal-card border border-terminal-border p-1.5 rounded">
                            <span className="text-[7px] text-terminal-muted block uppercase">Ritorno</span>
                            <span className={`font-mono text-[10px] font-bold ${backtestResults.total_return >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                              {backtestResults.total_return >= 0 ? "+" : ""}{backtestResults.total_return.toFixed(1)}%
                            </span>
                          </div>
                          <div className="bg-terminal-card border border-terminal-border p-1.5 rounded">
                            <span className="text-[7px] text-terminal-muted block uppercase">Benchmark</span>
                            <span className={`font-mono text-[10px] font-bold ${backtestResults.benchmark_return >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                              {backtestResults.benchmark_return >= 0 ? "+" : ""}{backtestResults.benchmark_return.toFixed(1)}%
                            </span>
                          </div>
                          <div className="bg-terminal-card border border-terminal-border p-1.5 rounded">
                            <span className="text-[7px] text-terminal-muted block uppercase">Max DD</span>
                            <span className="font-mono text-[10px] font-bold text-rose-400">
                              -{backtestResults.max_drawdown.toFixed(1)}%
                            </span>
                          </div>
                          <div className="bg-terminal-card border border-terminal-border p-1.5 rounded">
                            <span className="text-[7px] text-terminal-muted block uppercase">Sharpe</span>
                            <span className="font-mono text-[10px] font-bold text-white">
                              {backtestResults.sharpe_ratio.toFixed(2)}
                            </span>
                          </div>
                          <div className="bg-terminal-card border border-terminal-border p-1.5 rounded">
                            <span className="text-[7px] text-terminal-muted block uppercase">Win Rate</span>
                            <span className="font-mono text-[10px] font-bold text-white">
                              {backtestResults.win_rate.toFixed(0)}%
                            </span>
                          </div>
                        </div>

                        {/* Equity Curve plot */}
                        <div className="h-28 bg-terminal-bg rounded border border-terminal-border p-1">
                          <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={backtestResults.equity_curve}>
                              <XAxis dataKey="date" stroke="#64748B" fontSize={8} tickLine={false} />
                              <YAxis stroke="#64748B" fontSize={8} domain={["auto", "auto"]} orientation="right" tickLine={false} />
                              <Tooltip 
                                contentStyle={{ backgroundColor: "#151922", borderColor: "#232936", color: "#E2E8F0", fontSize: 9 }}
                                labelClassName="font-bold text-terminal-accent"
                              />
                              <Line type="monotone" dataKey="equity" stroke="#10B981" strokeWidth={1.5} dot={false} name="Equity" />
                            </LineChart>
                          </ResponsiveContainer>
                        </div>
                      </div>
                    )}
                  </div>

                </div>

                {/* Right side: AI Decision Reasoning Engine (2 columns) */}
                <div className="lg:col-span-2 p-4 overflow-y-auto flex flex-col gap-3 bg-terminal-bg/20">
                  <div className="flex items-center gap-2 border-b border-terminal-border pb-2">
                    <Cpu className="h-5 w-5 text-terminal-accent" />
                    <h3 className="text-xs font-black uppercase text-slate-400 tracking-wider">
                      Explainable AI Decision Engine
                    </h3>
                  </div>

                  {/* VSTOXX risk warnings overlay if systemic risk is detected */}
                  {marketSummary && marketSummary.v2tx.price >= V2TX_THRESHOLD && (
                    <div className="bg-rose-950/40 border border-rose-600 p-3 rounded text-xs text-rose-300 flex items-start gap-2">
                      <ShieldAlert className="h-5 w-5 text-rose-500 shrink-0 mt-0.5" />
                      <div>
                        <span className="font-black">BLOCCO ACQUISTI ATTIVO</span>
                        <p className="text-[11px] text-slate-300 mt-1">
                          L'indice di volatilità VSTOXX ({marketSummary.v2tx.price.toFixed(2)}) supera la soglia critica di {V2TX_THRESHOLD}. I segnali di acquisto sono forzati a HOLD.
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Tabs selector */}
                  <div className="flex border-b border-terminal-border">
                    <button
                      onClick={() => setActiveTab("micro")}
                      className={`flex-1 py-2 text-center text-xs font-bold transition-all border-b-2 uppercase ${
                        activeTab === "micro" 
                          ? "border-terminal-accent text-terminal-accent" 
                          : "border-transparent text-terminal-muted hover:text-slate-200"
                      }`}
                    >
                      Micro Analisi
                    </button>
                    <button
                      onClick={() => setActiveTab("macro")}
                      className={`flex-1 py-2 text-center text-xs font-bold transition-all border-b-2 uppercase ${
                        activeTab === "macro" 
                          ? "border-terminal-accent text-terminal-accent" 
                          : "border-transparent text-terminal-muted hover:text-slate-200"
                      }`}
                    >
                      Macro Scenario
                    </button>
                    <button
                      onClick={() => setActiveTab("technical")}
                      className={`flex-1 py-2 text-center text-xs font-bold transition-all border-b-2 uppercase ${
                        activeTab === "technical" 
                          ? "border-terminal-accent text-terminal-accent" 
                          : "border-transparent text-terminal-muted hover:text-slate-200"
                      }`}
                    >
                      Analisi Tecnica
                    </button>
                    <button
                      onClick={() => setActiveTab("history")}
                      className={`flex-1 py-2 text-center text-xs font-bold transition-all border-b-2 uppercase ${
                        activeTab === "history" 
                          ? "border-terminal-accent text-terminal-accent" 
                          : "border-transparent text-terminal-muted hover:text-slate-200"
                      }`}
                    >
                      Storico Segnali
                    </button>
                  </div>

                  {/* Tab Contents */}
                  <div className="flex-1 text-xs leading-relaxed text-slate-300 overflow-y-auto pr-1">
                    {activeTab === "micro" && (
                      <div className="space-y-3">
                        <div className="text-[11px] text-terminal-accent uppercase font-bold">Analisi Societaria e Sentiment News</div>
                        <p className="bg-terminal-bg/40 p-3 rounded border border-terminal-border/40 whitespace-pre-line">
                          {stockDetail.reason_micro}
                        </p>
                      </div>
                    )}
                    {activeTab === "macro" && (
                      <div className="space-y-3">
                        <div className="text-[11px] text-terminal-accent uppercase font-bold">Impatto Macroeconomico & Indici di Riferimento</div>
                        <p className="bg-terminal-bg/40 p-3 rounded border border-terminal-border/40 whitespace-pre-line">
                          {stockDetail.reason_macro}
                        </p>
                      </div>
                    )}
                    {activeTab === "technical" && (
                      <div className="space-y-3">
                        <div className="text-[11px] text-terminal-accent uppercase font-bold">Analisi Quantitativa degli Indicatori e Medie Mobili</div>
                        <p className="bg-terminal-bg/40 p-3 rounded border border-terminal-border/40 whitespace-pre-line">
                          {stockDetail.reason_technical}
                        </p>
                      </div>
                    )}
                    {activeTab === "history" && (
                      <div className="space-y-3">
                        <div className="text-[11px] text-terminal-accent uppercase font-bold">Storico delle Raccomandazioni ed Eventi AI</div>
                        {historyLoading ? (
                          <div className="text-center py-8 text-terminal-muted">Caricamento storico...</div>
                        ) : signalHistory.length === 0 ? (
                          <div className="text-center py-8 text-terminal-muted">Nessun segnale storico disponibile per questo ticker.</div>
                        ) : (
                          <div className="space-y-2 max-h-[280px] overflow-y-auto pr-1">
                            {signalHistory.map((item, idx) => (
                              <div key={idx} className="bg-terminal-bg/40 p-2.5 rounded border border-terminal-border/40 flex flex-col gap-1 text-[11px]">
                                <div className="flex items-center justify-between border-b border-terminal-border/30 pb-1 mb-1">
                                  <span className="font-mono text-[9px] text-terminal-muted">
                                    {item.timestamp.replace("T", " ").substring(0, 19)} Z
                                  </span>
                                  <span className={`font-mono font-black uppercase text-[10px] ${
                                    item.signal === "BUY" ? "text-emerald-400" : item.signal === "SELL" ? "text-rose-400" : "text-slate-400"
                                  }`}>
                                    {item.signal}
                                  </span>
                                </div>
                                <div className="flex justify-between text-[10px]">
                                  <span className="text-slate-400">Sentiment Score:</span>
                                  <span className={`font-mono font-bold ${item.sentiment_score >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                                    {item.sentiment_score >= 0 ? "+" : ""}{item.sentiment_score.toFixed(3)}
                                  </span>
                                </div>
                                <div className="text-[10px] text-slate-300 mt-1 italic">
                                  {item.reason_technical || "Nessun dettaglio tecnico registrato."}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>

              </div>
            ) : (
              <div className="p-20 text-center text-xs text-terminal-muted">
                Errore nel caricamento dei dati di dettaglio.
              </div>
            )}

            {/* Modal Footer */}
            <div className="p-3 border-t border-terminal-border bg-terminal-bg/50 flex items-center justify-between text-[10px] text-terminal-muted">
              <span>Modello Decisionale: Llama3-8B (Ollama Local Instance)</span>
              <span>Generato il (Zulu): {stockDetail && stockDetail.history.length > 0 ? stockDetail.history[stockDetail.history.length-1].date + " Z" : ""}</span>
            </div>
            
          </div>
        </div>
      )}

      {mainTab === "asset_config" && (
        <div className="flex flex-col gap-3 flex-1 h-[calc(100vh-140px)]">
          <div className="bg-terminal-card border border-terminal-border p-4 rounded shrink-0">
            <h2 className="text-sm font-black uppercase text-[#00ff66] mb-4 flex items-center gap-2">
              <Search className="h-5 w-5" /> Aggiungi Nuovo Ticker
            </h2>
            <form onSubmit={submitNewTicker} className="flex gap-4 items-end">
              <div className="flex-1">
                <label className="block text-xs uppercase text-slate-400 mb-1">Simbolo (es. US500, AAPL, BTCUSD)</label>
                <input 
                  type="text" 
                  value={newTicker.ticker} 
                  onChange={(e) => setNewTicker({...newTicker, ticker: e.target.value.toUpperCase()})}
                  className="w-full bg-terminal-bg border border-terminal-border focus:border-[#00ff66] focus:outline-none rounded px-3 py-1.5 text-sm text-white uppercase"
                  required
                />
              </div>
              <div className="flex-1">
                <label className="block text-xs uppercase text-slate-400 mb-1">Nome Azienda / Asset</label>
                <input 
                  type="text" 
                  value={newTicker.name} 
                  onChange={(e) => setNewTicker({...newTicker, name: e.target.value})}
                  className="w-full bg-terminal-bg border border-terminal-border focus:border-[#00ff66] focus:outline-none rounded px-3 py-1.5 text-sm text-white"
                  required
                />
              </div>
              <div className="flex-1">
                <label className="block text-xs uppercase text-slate-400 mb-1">Mercato (es. USA, Europe, Crypto)</label>
                <input 
                  type="text" 
                  value={newTicker.country} 
                  onChange={(e) => setNewTicker({...newTicker, country: e.target.value})}
                  className="w-full bg-terminal-bg border border-terminal-border focus:border-[#00ff66] focus:outline-none rounded px-3 py-1.5 text-sm text-white"
                  required
                />
              </div>
              <div className="flex-1">
                <label className="block text-xs uppercase text-slate-400 mb-1">Settore (es. Index, Technology, Crypto)</label>
                <input 
                  type="text" 
                  value={newTicker.sector} 
                  onChange={(e) => setNewTicker({...newTicker, sector: e.target.value})}
                  className="w-full bg-terminal-bg border border-terminal-border focus:border-[#00ff66] focus:outline-none rounded px-3 py-1.5 text-sm text-white"
                  required
                />
              </div>
              <button 
                type="submit" 
                className="bg-[#00ff66] text-black font-bold py-1.5 px-6 rounded text-sm uppercase tracking-wider hover:bg-[#00e55c] transition"
              >
                + Aggiungi
              </button>
            </form>
          </div>

          <div className="bg-terminal-card border border-terminal-border rounded flex-1 flex flex-col overflow-hidden">
            <div className="p-3 border-b border-terminal-border bg-terminal-bg/50 flex justify-between items-center">
              <h2 className="text-xs font-black uppercase text-slate-400 flex items-center gap-2">
                <Activity className="h-4 w-4" /> Configurazione Asset Monitorati
              </h2>
              <button onClick={fetchTickersConfig} className="text-slate-400 hover:text-white transition">
                <RefreshCw className="h-4 w-4" />
              </button>
            </div>
            
            <div className="flex-1 overflow-auto custom-scrollbar p-3">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-terminal-border/50 text-slate-500 uppercase tracking-wider">
                    <th className="p-2 font-medium">Stato</th>
                    <th className="p-2 font-medium">Ticker</th>
                    <th className="p-2 font-medium">Nome</th>
                    <th className="p-2 font-medium">Mercato</th>
                    <th className="p-2 font-medium">Settore</th>
                    <th className="p-2 font-medium text-center">Azione</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-terminal-border/30">
                  {tickersConfig.map((t, idx) => (
                    <tr key={idx} className="hover:bg-terminal-bg/30 transition-colors group">
                      <td className="p-2">
                        {t.is_active ? (
                          <span className="text-[#00ff66] font-bold">● ATTIVO</span>
                        ) : (
                          <span className="text-rose-500 font-bold">○ DISATTIVO</span>
                        )}
                      </td>
                      <td className={`p-2 font-bold font-mono ${t.is_active ? 'text-white' : 'text-slate-500'}`}>{t.ticker}</td>
                      <td className={`p-2 ${t.is_active ? 'text-slate-300' : 'text-slate-500'}`}>{t.name}</td>
                      <td className={`p-2 ${t.is_active ? 'text-slate-400' : 'text-slate-600'}`}>{t.country}</td>
                      <td className={`p-2 ${t.is_active ? 'text-slate-400' : 'text-slate-600'}`}>{t.sector}</td>
                      <td className="p-2 text-center">
                        <button
                          onClick={() => toggleTickerStatus(t.ticker, t.is_active)}
                          className={`px-3 py-1 rounded text-xs font-bold uppercase transition ${
                            t.is_active 
                              ? 'bg-rose-500/20 text-rose-500 hover:bg-rose-500 hover:text-white' 
                              : 'bg-[#00ff66]/20 text-[#00ff66] hover:bg-[#00ff66] hover:text-black'
                          }`}
                        >
                          {t.is_active ? 'Disattiva' : 'Riattiva'}
                        </button>
                      </td>
                    </tr>
                  ))}
                  {tickersConfig.length === 0 && (
                    <tr>
                      <td colSpan={6} className="p-4 text-center text-slate-500 italic">Nessun asset configurato.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Risk Configuration Modal */}
      {showRiskModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-terminal-card border border-terminal-border rounded-lg shadow-2xl max-w-md w-full overflow-hidden">
            {/* Modal Header */}
            <div className="p-4 border-b border-terminal-border bg-terminal-bg flex justify-between items-center">
              <h3 className="text-terminal-accent text-xs font-black tracking-wider uppercase flex items-center gap-2">
                🛡️ CONFIGURAZIONE PARAMETRI DI RISCHIO
              </h3>
              <button 
                onClick={() => setShowRiskModal(false)}
                className="text-slate-400 hover:text-white transition text-xs font-bold"
              >
                ✕
              </button>
            </div>
            
            {/* Modal Body */}
            <div className="p-5 space-y-4">
              <div className="space-y-1">
                <label className="text-[10px] text-slate-400 font-bold uppercase block">
                  Drawdown Massimo Consentito (%)
                </label>
                <div className="flex gap-2">
                  <input
                    type="number"
                    step="0.1"
                    min="0.5"
                    max="50.0"
                    value={riskModalValue}
                    onChange={(e) => setRiskModalValue(e.target.value)}
                    className="flex-1 bg-terminal-bg border border-terminal-border rounded px-3 py-2 text-xs text-white font-mono focus:border-terminal-accent focus:outline-none"
                  />
                  <span className="text-xs text-slate-300 flex items-center font-bold font-mono">%</span>
                </div>
                <p className="text-[10px] text-terminal-muted leading-snug">
                  Se il drawdown totale degli account connessi supera questo valore, tutti gli EA connessi eseguiranno la chiusura automatica di emergenza delle posizioni.
                </p>
              </div>

              <div className="bg-terminal-bg/50 border border-terminal-border/40 p-3 rounded space-y-1.5 text-[11px]">
                <div className="flex justify-between text-slate-400">
                  <span>Drawdown Aggregato Corrente:</span>
                  <span className={`font-mono font-bold ${currentDrawdownPercent > maxDrawdownPercent ? "text-rose-400" : "text-emerald-400"}`}>
                    {currentDrawdownPercent.toFixed(2)}%
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Stato Operativo:</span>
                  <span className={`font-bold ${currentDrawdownPercent > maxDrawdownPercent || emergencyKillSwitch ? "text-rose-400 animate-pulse" : "text-emerald-400"}`}>
                    {currentDrawdownPercent > maxDrawdownPercent || emergencyKillSwitch ? "BLOCCO (CLOSE_ALL)" : "REGOLARE"}
                  </span>
                </div>
              </div>

              {/* Individual Account Risk Controls */}
              <div className="space-y-2 border-t border-terminal-border/40 pt-4">
                <label className="text-[10px] text-slate-400 font-bold uppercase block">
                  Limiti Drawdown per Account MT5
                </label>
                {riskAccounts.length === 0 ? (
                  <div className="text-[10px] text-terminal-muted italic py-1">Nessun account MT5 connesso</div>
                ) : (
                  <div className="space-y-3 max-h-40 overflow-y-auto pr-1">
                    {riskAccounts.map((acc) => (
                      <div key={acc.account_id} className="flex flex-col gap-1.5 p-2 bg-terminal-bg/30 border border-terminal-border/20 rounded">
                        <div className="flex justify-between items-center text-[10px]">
                          <span className="font-bold text-slate-300">ID: {acc.account_id} ({acc.broker})</span>
                          <span className={`font-mono font-bold ${acc.current_drawdown_percent > acc.max_drawdown_percent ? "text-rose-400" : "text-emerald-400"}`}>
                            DD: {acc.current_drawdown_percent}%
                          </span>
                        </div>
                        <div className="flex gap-2 items-center">
                          <input
                            type="number"
                            step="0.1"
                            min="0.5"
                            max="50.0"
                            defaultValue={acc.max_drawdown_percent}
                            id={`limit-${acc.account_id}`}
                            className="w-20 bg-terminal-bg border border-terminal-border rounded px-2 py-1 text-[10px] text-white font-mono focus:border-terminal-accent focus:outline-none"
                          />
                          <span className="text-[10px] text-slate-400 font-bold font-mono">%</span>
                          <button
                            onClick={() => {
                              const el = document.getElementById(`limit-${acc.account_id}`) as HTMLInputElement;
                              if (el) saveAccountRisk(acc.account_id, Number(el.value));
                            }}
                            className="ml-auto bg-slate-800 hover:bg-terminal-accent hover:text-black px-2 py-1 text-[8px] font-bold uppercase rounded transition text-white"
                          >
                            Salva
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
            
            {/* Modal Footer */}
            <div className="p-3 border-t border-terminal-border bg-terminal-bg/50 flex justify-end gap-2">
              <button
                onClick={() => setShowRiskModal(false)}
                className="px-3 py-1.5 text-[10px] uppercase font-bold text-slate-400 hover:text-white rounded transition"
              >
                Annulla
              </button>
              <button
                onClick={saveRiskSettings}
                className="bg-terminal-accent text-black px-4 py-1.5 text-[10px] uppercase font-black rounded hover:bg-white transition"
              >
                Salva Limiti
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
