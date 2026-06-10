"use client";

import React, { useState, useEffect } from "react";
import { 
  TrendingUp, TrendingDown, RefreshCw, AlertTriangle, 
  Search, ShieldAlert, Award, FileText, Globe, Cpu, X,
  Activity, ArrowUpRight, Newspaper, Play
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

interface MarketSummary {
  indices: IndexSummary[];
  v2tx: VolatilitySummary;
  forex: ForexSummary[];
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

export default function TerminalDashboard() {
  // States
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
  const [activeOverrides, setActiveOverrides] = useState<Record<string, any>>({});
  const [signalHistory, setSignalHistory] = useState<any[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [showBollinger, setShowBollinger] = useState(false);
  const [forexScreener, setForexScreener] = useState<ScreenerRow[]>([]);
  const [mt5Clients, setMt5Clients] = useState<any[]>([]);
  const [screenerTab, setScreenerTab] = useState<"stocks" | "forex">("stocks");
  const [brokerAccounts, setBrokerAccounts] = useState<BrokerAccount[]>([]);

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
    } catch (error) {
      console.error("Error fetching dashboard data:", error);
    }
  };

  useEffect(() => {
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
  }, []);

  // Fetch stock details when ticker is selected
  useEffect(() => {
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

    fetchStockDetail();
    fetchSignalHistory();
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

        {/* Sync Trigger */}
        <button
          onClick={triggerSync}
          disabled={syncing}
          className={`px-4 py-2 text-xs font-bold uppercase rounded border transition flex items-center gap-2 ${
            syncing 
              ? "bg-terminal-card border-terminal-border text-terminal-muted cursor-not-allowed" 
              : "bg-terminal-accent/10 border-terminal-accent text-terminal-accent hover:bg-terminal-accent hover:text-black shadow-[0_0_8px_rgba(255,153,0,0.2)]"
          }`}
        >
          <RefreshCw className={`h-4 w-4 ${syncing ? "animate-spin" : ""}`} />
          {syncing ? "WORKER RUNNING..." : "RUN SYNC ENGINE"}
        </button>
      </header>

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
        <div className="bg-terminal-card border border-terminal-border p-2 mb-4 rounded flex items-center overflow-x-auto whitespace-nowrap text-xs gap-6 scrollbar-none">
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

      {/* Main Grid: Heatmap, Screener & News */}
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
                       country === "United Kingdom" ? "🇬🇧 UK" : country}
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
                      <td colSpan={8} className="py-8 text-center text-terminal-muted">
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
        </div>
      </div>

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

                    <div className="grid grid-cols-4 gap-2 text-center text-[10px]">
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
                        <span className="text-[8px] text-terminal-muted block uppercase">Stop Loss (SL)</span>
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
                      <button
                        onClick={runBacktest}
                        disabled={backtestLoading}
                        className="bg-terminal-accent text-black px-3 py-1 text-[9px] font-black uppercase rounded hover:bg-white transition disabled:opacity-50"
                      >
                        {backtestLoading ? "Simulazione..." : "Esegui Backtest"}
                      </button>
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
    </div>
  );
}
