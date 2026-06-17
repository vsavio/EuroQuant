//+------------------------------------------------------------------+
//|                               EuroQuant_MultiSymbol_Bridge.mq5  |
//|                                  Copyright 2026, EuroQuant Team  |
//|                                       https://localhost:3000/    |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, EuroQuant Team"
#property link      "https://localhost:3000/"
#property version   "1.00"
#property description "Multi-Symbol EA connecting ALL EuroQuant signals to MT5 execution."

// Import Trade Library
#include <Trade\Trade.mqh>
CTrade trade;

//--- Input Parameters
input group "=== EUROQUANT API SETTINGS ==="
input string   InpApiUrl            = "http://127.0.0.1:8000/api/mt5/signals"; // API Endpoint URL (lista completa)
input string   InpApiKey            = "";                                      // API Key di Sicurezza (Obbligatoria)
input int      InpCheckIntervalSecs = 120;                                     // Frequenza controllo API (in secondi)

input group "=== TRADING SESSIONS ==="
input int      InpTradeStartHour    = 0;                                       // Ora inizio trading (0-23)
input int      InpTradeEndHour      = 24;                                      // Ora fine trading (0-24)

input group "=== RISK & POSITION MANAGEMENT ==="
input double   InpLotMultiplier     = 1.0;                                     // Quota/Moltiplicatore rispetto al lotto minimo di ciascun simbolo
input int      InpMaxPositionsPerSymbol = 1;                                   // Numero massimo di posizioni contemporanee per singolo simbolo
input ulong    InpMagicNumber       = 20260620;                                // Magic Number per identificare le posizioni
input int      InpMaxSpreadPoints   = 50;                                      // Spread massimo consentito in punti (se InpMaxSpreadPercent <= 0)
input double   InpMaxSpreadPercent  = 0.25;                                    // Spread massimo consentito in % del prezzo (0 per disabilitare)
input int      InpMaxSlippagePoints = 30;                                      // Slippage massimo consentito in punti
input int      InpOrderRetries      = 3;                                       // Numero di tentativi invio ordine
input bool     InpEnableTrading     = true;                                    // Abilita esecuzione ordini a mercato
input bool     InpSendAlerts        = true;                                    // Abilita gli alert grafici nel terminale

input group "=== TRAILING STOP SETTINGS ==="
input bool     InpUseTrailingStop   = true;                                    // Abilita Trailing Stop
input bool     InpIgnoreTakeProfit  = true;                                    // Ignora TP API (Usa solo SL Dinamico)
input bool     InpUseBreakEven      = true;                                    // Abilita Break-Even (Secure profit)
input bool     InpEnablePartialClose= true;                                    // Chiudi 50% al Break-Even
input double   InpBreakEvenAtrMult  = 2.5;                                     // Moltiplicatore ATR per attivare Break-Even
input double   InpBreakEvenFallbackPct = 0.8;                                  // Fallback profitto % per Break-Even
input int      InpTrailingStopPoints = 150;                                    // Punti statici (fallback se no ATR)
input int      InpTrailingStepPoints = 50;                                     // Step statico (fallback se no ATR)

input group "=== ACCOUNT SAFEGUARD SETTINGS ==="
input double   InpMaxDailyLossPercent = 4.0;                                    // Max perdita giornaliera consentita (%)
input double   InpMaxDrawdownPercent = 10.0;                                    // Max drawdown totale consentito (%)

input group "=== PORTFOLIO LIMITS ==="
input int      InpMaxOpenPositions  = 5;                                       // Limite massimo posizioni simultanee aperte

input group "=== ADVANCED FILTERS & GRID RECOVERY ==="
input bool     InpUseIchimokuFilter = true;                                    // Filtro Ichimoku (Solo trade pro Kumo)
input bool     InpUseVWAPFilter     = true;                                    // Filtro VWAP (Solo trade pro VWAP giornaliero)
input bool     InpUseGridRecovery   = true;                                    // Abilita Grid / Martingale Recovery
input int      InpGridStepPoints    = 500;                                     // Distanza in punti per nuovo livello Grid
input double   InpGridMultiplier    = 1.0;                                     // Moltiplicatore volume livello Grid (1.0 = flat, no Martingale)
input int      InpMaxGridLevels     = 1;                                       // Numero massimo livelli Grid consentiti

input group "=== BROKER SUFFIX MAPPING ==="
input string   InpMilanSuffix       = ".IT";                                   // Milano (yfinance .MI -> MT5 es. .IT)
input string   InpFrankfurtSuffix   = ".DE";                                   // Francoforte (yfinance .DE -> MT5 es. .DE)
input string   InpAmsterdamSuffix   = ".AS";                                   // Amsterdam (yfinance .AS -> MT5 es. .AS)
input string   InpParisSuffix       = ".PA";                                   // Parigi (yfinance .PA -> MT5 es. .PA)
input string   InpMadridSuffix      = ".MC";                                   // Madrid (yfinance .MC -> MT5 es. .MC)
input string   InpLondonSuffix      = ".L";                                    // Londra (yfinance .L -> MT5 es. .L)
input string   InpForexSuffix       = "";                                      // Forex (es. vuoto o .m)

//--- Global Variables
double   starting_equity = 0.0;
bool     safeguard_tripped = false;
datetime last_check_time = 0;
datetime last_sync_time = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   // Set Magic Number for trade object
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(InpMaxSlippagePoints);
   
   // Initialize starting equity
   starting_equity = AccountInfoDouble(ACCOUNT_EQUITY);
   
   // Enable Timer
   EventSetTimer(1);
   Print("[EuroQuant Multi-Bridge] EA Inizializzato. Gestione di portafoglio multi-simbolo attiva. Magic: ", InpMagicNumber, " | Equity iniziale: ", DoubleToString(starting_equity, 2));
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   CleanupDashboard();
   Print("[EuroQuant Multi-Bridge] EA arrestato e pannello grafico rimosso.");
}

//+------------------------------------------------------------------+
//| Expert timer function                                            |
//+------------------------------------------------------------------+
void OnTimer()
{
   datetime now = TimeLocal();
   
   // Perform Safeguard Check
   CheckSafeguards();
   
   // Manage Grid Recovery (Averaging Down)
   if(InpUseGridRecovery && !safeguard_tripped)
   {
      ManageGridRecovery();
   }
   
   // Perform Trailing Stop Check
   if(InpUseTrailingStop && !safeguard_tripped)
   {
      ApplyTrailingStop();
   }
   
   // Fetch signals from API
   if(now - last_check_time >= InpCheckIntervalSecs && !safeguard_tripped)
   {
      last_check_time = now;
      FetchAndExecuteAllSignals();
   }
   
   // Update Graphic Dashboard Panel
   DrawDashboard();
   
   // Sync positions to Docker Backend
   if(now - last_sync_time >= 5)
   {
       last_sync_time = now;
       SyncLivePositions();
   }
}

//+------------------------------------------------------------------+
//| Fetch all signals and execute portfolio logic                     |
//+------------------------------------------------------------------+
void FetchAndExecuteAllSignals()
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double margin = AccountInfoDouble(ACCOUNT_MARGIN);
   double margin_free = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   double margin_level = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
   double profit = AccountInfoDouble(ACCOUNT_PROFIT);
   long login = AccountInfoInteger(ACCOUNT_LOGIN);
   string company = AccountInfoString(ACCOUNT_COMPANY);
   StringReplace(company, " ", "%20");
   
   string request_url = InpApiUrl + "?api_key=" + InpApiKey +
                        "&balance=" + DoubleToString(balance, 2) +
                        "&equity=" + DoubleToString(equity, 2) +
                        "&margin=" + DoubleToString(margin, 2) +
                        "&margin_free=" + DoubleToString(margin_free, 2) +
                        "&margin_level=" + DoubleToString(margin_level, 2) +
                        "&profit=" + DoubleToString(profit, 2) +
                        "&account=" + IntegerToString(login) +
                        "&broker=" + company;
   
   char post[], result[];
   string result_headers;
   int timeout = 10000; // 10 seconds for full list
   
   ResetLastError();
   
   // Request the FULL list of signals
   int res = WebRequest("GET", request_url, NULL, NULL, timeout, post, 0, result, result_headers);
   
   if(res == -1)
   {
      int err = GetLastError();
      Print("[EuroQuant Multi-Bridge] Errore HTTP (errore ", err, "). Verifica le impostazioni WebRequest.");
      return;
   }
   
   if(res != 200)
   {
      Print("[EuroQuant Multi-Bridge] L'API ha risposto con codice HTTP: ", res);
      return;
   }
   
   string json_response = CharArrayToString(result);
   
   // Parse JSON array of objects: split by '{' and '}'
   int start_pos = 0;
   int signals_processed = 0;
   
   while(true)
   {
      int open_brace = StringFind(json_response, "{", start_pos);
      if(open_brace == -1) break;
      
      int close_brace = StringFind(json_response, "}", open_brace);
      if(close_brace == -1) break;
      
      string obj = StringSubstr(json_response, open_brace, close_brace - open_brace + 1);
      ProcessSingleSignal(obj);
      
      signals_processed++;
      start_pos = close_brace + 1;
   }
   
   Print("[EuroQuant Multi-Bridge] Ciclo completato. Segnali elaborati: ", signals_processed);
}

//+------------------------------------------------------------------+
//| Resolve MT5 symbol with appropriate broker suffixes             |
//+------------------------------------------------------------------+
string ResolveMt5Symbol(string ticker, string base_symbol)
{
   // 1. Prova prima il matching esatto
   if(SymbolInfoInteger(base_symbol, SYMBOL_VISIBLE)) 
      return base_symbol;
      
   // 2. Cerca tra i simboli già visibili in Market Watch
   int total_visible = SymbolsTotal(false);
   for(int i = 0; i < total_visible; i++)
   {
      string sym = SymbolName(i, false);
      if(StringFind(sym, base_symbol) == 0)
      {
         int base_len = StringLen(base_symbol);
         if(StringLen(sym) == base_len) return sym;
         ushort next_char = StringGetCharacter(sym, base_len);
         if(next_char == '.' || next_char == '_' || next_char == '-')
         {
            return sym;
         }
      }
   }
   
   // 3. Cerca tra tutti i simboli censiti dal Broker nel server
   int total_all = SymbolsTotal(true);
   for(int i = 0; i < total_all; i++)
   {
      string sym = SymbolName(i, true);
      if(StringFind(sym, base_symbol) == 0)
      {
         int base_len = StringLen(base_symbol);
         if(StringLen(sym) == base_len)
         {
            SymbolSelect(sym, true);
            return sym;
         }
         ushort next_char = StringGetCharacter(sym, base_len);
         if(next_char == '.' || next_char == '_' || next_char == '-')
         {
            SymbolSelect(sym, true);
            return sym;
         }
      }
   }
   
   // Fallback se nessun match viene trovato
   return base_symbol;
}

//+------------------------------------------------------------------+
//| Process single JSON object representation of a signal             |
//+------------------------------------------------------------------+
void ProcessSingleSignal(string json_obj)
{
   MqlDateTime dt;
   TimeCurrent(dt);
   bool is_trading_hour = false;
   if(InpTradeEndHour <= InpTradeStartHour) {
      if(dt.hour >= InpTradeStartHour || dt.hour < InpTradeEndHour) is_trading_hour = true;
   } else {
      if(dt.hour >= InpTradeStartHour && dt.hour < InpTradeEndHour) is_trading_hour = true;
   }

   string ticker = GetJsonValue(json_obj, "ticker");
   string raw_symbol = GetJsonValue(json_obj, "mt5_symbol");
   string symbol = ResolveMt5Symbol(ticker, raw_symbol);

   string action = GetJsonValue(json_obj, "action");
   string entry_price_str = GetJsonValue(json_obj, "entry_price");
   string stop_loss_str = GetJsonValue(json_obj, "stop_loss");
   string take_profit_str = GetJsonValue(json_obj, "take_profit");
   string reason = GetJsonValue(json_obj, "reason");
   string vol_str = GetJsonValue(json_obj, "volatility_lot_sizing");
   
   double entry_price = StringToDouble(entry_price_str);
   double stop_loss = StringToDouble(stop_loss_str);
   double take_profit = StringToDouble(take_profit_str);
   double volatility_lot_sizing = (StringLen(vol_str) > 0) ? StringToDouble(vol_str) : 1.0;
   
   StringToUpper(action);
   
   if(StringLen(symbol) == 0 || StringLen(action) == 0)
   {
      return; // Skip invalid objects
   }
   
   // Ensure symbol is added to Market Watch and active
   if(!SymbolInfoInteger(symbol, SYMBOL_VISIBLE))
   {
      if(!SymbolSelect(symbol, true))
      {
         Print("[EuroQuant Multi-Bridge] Simbolo non supportato dal broker o inattivo: ", symbol);
         return;
      }
   }
   
   // Fetch digits and points for calculations
   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   
   // Count open positions for this magic number and symbol
   bool has_buy = false;
   bool has_sell = false;
   
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionGetInteger(POSITION_MAGIC) == InpMagicNumber && PositionGetString(POSITION_SYMBOL) == symbol)
      {
         long pos_type = PositionGetInteger(POSITION_TYPE);
         if(pos_type == POSITION_TYPE_BUY)
         {
            has_buy = true;
            if(action == "SELL")
            {
               trade.PositionClose(ticket);
               Print("[EuroQuant Multi-Bridge] Chiusa posizione BUY su ", symbol, " per segnale SELL.");
               has_buy = false;
            }
         }
         else if(pos_type == POSITION_TYPE_SELL)
         {
            has_sell = true;
            if(action == "BUY")
            {
               trade.PositionClose(ticket);
               Print("[EuroQuant Multi-Bridge] Chiusa posizione SELL su ", symbol, " per segnale BUY.");
               has_sell = false;
            }
         }
      }
   }
   
   if(!InpEnableTrading)
   {
      return;
   }
   
   // Check Max Open Positions limit
   if(GetTotalOpenPositions() >= InpMaxOpenPositions)
   {
      // Block if we are adding a position, but allow if we are doing a stop-and-reverse
      if((action == "BUY" && !has_sell) || (action == "SELL" && !has_buy))
      {
         Print("[EuroQuant Multi-Bridge] Limite massimo posizioni simultanee raggiunto (", InpMaxOpenPositions, "). Ordine per ", symbol, " ignorato.");
         return;
      }
   }
    
   // --- ADVANCED FILTERS (VWAP / Ichimoku) ---
   if(InpUseVWAPFilter)
   {
      if(!IsVWAPAligned(symbol, action))
      {
         Print("[EuroQuant Filter] Segnale ", action, " su ", symbol, " scartato: Contro VWAP giornaliero.");
         return;
      }
   }
   
   if(InpUseIchimokuFilter)
   {
      if(!IsIchimokuAligned(symbol, action))
      {
         Print("[EuroQuant Filter] Segnale ", action, " su ", symbol, " scartato: Prezzo sfavorevole rispetto a Kumo Cloud (Ichimoku).");
         return;
      }
   }
   
   // Check Trading Hours Filter
   if(!is_trading_hour)
   {
      if((action == "BUY" && !has_buy) || (action == "SELL" && !has_sell))
      {
         Print("[EuroQuant Multi-Bridge] Fuori orario di trading (H", dt.hour, "). Ordine per ", symbol, " ignorato.");
         return;
      }
   }
   
   // Check Spread
   int spread = (int)SymbolInfoInteger(symbol, SYMBOL_SPREAD);
   double ask_price = SymbolInfoDouble(symbol, SYMBOL_ASK);
   double point_val = SymbolInfoDouble(symbol, SYMBOL_POINT);
   double spread_val = spread * point_val;
   double spread_pct = (ask_price > 0) ? (spread_val / ask_price) * 100.0 : 0.0;
   
   if(InpMaxSpreadPercent > 0)
   {
      if(spread_pct > InpMaxSpreadPercent)
      {
         Print("[EuroQuant Multi-Bridge] Spread su ", symbol, " troppo alto (", DoubleToString(spread_pct, 3), "% > limit ", DoubleToString(InpMaxSpreadPercent, 3), "%). Ordine saltato.");
         return;
      }
   }
   else
   {
      if(spread > InpMaxSpreadPoints)
      {
         Print("[EuroQuant Multi-Bridge] Spread su ", symbol, " troppo alto (", spread, " punti > limit ", InpMaxSpreadPoints, " punti). Ordine saltato.");
         return;
      }
   }
   
   // Calculate lot size dynamically for this specific symbol
   double min_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double lot_step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   
   if(min_lot <= 0)
   {
      return; // Skip if volume limits can't be fetched
   }
   
   double trade_lot = min_lot * InpLotMultiplier * volatility_lot_sizing;
   if(lot_step > 0)
   {
      trade_lot = MathRound(trade_lot / lot_step) * lot_step;
   }
   if(trade_lot < min_lot) trade_lot = min_lot;
   if(trade_lot > max_lot) trade_lot = max_lot;
   
   // Place Orders
   if(action == "BUY" && GetOpenPositionsBySymbol(symbol) < InpMaxPositionsPerSymbol)
   {
      double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
      double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
      if(ask <= 0 || bid <= 0) return;
      
      double stop_level = SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL) * point;
      double freeze_level = SymbolInfoInteger(symbol, SYMBOL_TRADE_FREEZE_LEVEL) * point;
      double spread_dist = (ask - bid) * 1.5;
      double min_dist = MathMax(stop_level, freeze_level);
      if(min_dist == 0) min_dist = MathMax(10 * point, spread_dist);
      
      double tick_size = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
      if(tick_size == 0) tick_size = point;
      
      // Safety SL/TP bounds checks & Normalization
      // For BUY, close happens at BID. SL must be < BID, TP must be > BID.
      if(stop_loss >= bid - min_dist && stop_loss > 0) stop_loss = bid - min_dist - 10 * point;
      if(take_profit <= bid + min_dist && take_profit > 0) take_profit = bid + min_dist + 10 * point;
      
      if(InpIgnoreTakeProfit) take_profit = 0;

      stop_loss = MathRound(stop_loss / tick_size) * tick_size;
      take_profit = MathRound(take_profit / tick_size) * tick_size;
      stop_loss = NormalizeDouble(stop_loss, digits);
      take_profit = NormalizeDouble(take_profit, digits);
      
      if(trade.Buy(trade_lot, symbol, ask, stop_loss, take_profit, "EQ Multi-Symbol BUY"))
      {
         Print("[EuroQuant Multi-Bridge] BUY ", symbol, " eseguito | Lotti: ", DoubleToString(trade_lot, 2));
         LogExecution(symbol, "BUY", trade_lot, ask, entry_price);
         if(InpSendAlerts)
         {
            Alert("[EuroQuant Multi-Bridge] Nuova operazione BUY su ", symbol, " (Volume: ", DoubleToString(trade_lot, 2), ")");
         }
      }
      else
      {
         Print("[EuroQuant Multi-Bridge] Errore BUY ", symbol, " | Errore MT5: ", GetLastError());
      }
   }
   else if(action == "SELL" && GetOpenPositionsBySymbol(symbol) < InpMaxPositionsPerSymbol)
   {
      double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
      if(bid <= 0 || ask <= 0) return;
      
      double stop_level = SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL) * point;
      double freeze_level = SymbolInfoInteger(symbol, SYMBOL_TRADE_FREEZE_LEVEL) * point;
      double spread_dist = (ask - bid) * 1.5;
      double min_dist = MathMax(stop_level, freeze_level);
      if(min_dist == 0) min_dist = MathMax(10 * point, spread_dist);
      
      double tick_size = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
      if(tick_size == 0) tick_size = point;
      
      // Safety SL/TP bounds checks & Normalization
      // For SELL, close happens at ASK. SL must be > ASK, TP must be < ASK.
      if(stop_loss <= ask + min_dist && stop_loss > 0) stop_loss = ask + min_dist + 10 * point;
      if(take_profit >= ask - min_dist && take_profit > 0) take_profit = ask - min_dist - 10 * point;
      
      if(InpIgnoreTakeProfit) take_profit = 0;

      stop_loss = MathRound(stop_loss / tick_size) * tick_size;
      take_profit = MathRound(take_profit / tick_size) * tick_size;
      stop_loss = NormalizeDouble(stop_loss, digits);
      take_profit = NormalizeDouble(take_profit, digits);
      
      if(trade.Sell(trade_lot, symbol, bid, stop_loss, take_profit, "EQ Multi-Symbol SELL"))
      {
         Print("[EuroQuant Multi-Bridge] SELL ", symbol, " eseguito | Lotti: ", DoubleToString(trade_lot, 2));
         LogExecution(symbol, "SELL", trade_lot, bid, entry_price);
         if(InpSendAlerts)
         {
            Alert("[EuroQuant Multi-Bridge] Nuova operazione SELL su ", symbol, " (Volume: ", DoubleToString(trade_lot, 2), ")");
         }
      }
      else
      {
         Print("[EuroQuant Multi-Bridge] Errore SELL ", symbol, " | Errore MT5: ", GetLastError());
      }
   }
}

//+------------------------------------------------------------------+
//| Simple and Robust Custom JSON Parser (Zero Dependency)          |
//+------------------------------------------------------------------+
string GetJsonValue(string json, string key)
{
   string search_key = "\"" + key + "\":";
   int pos = StringFind(json, search_key);
   if(pos == -1) return "";
   
   int val_start = pos + StringLen(search_key);
   
   while(val_start < StringLen(json))
   {
      ushort c = StringGetCharacter(json, val_start);
      if(c == ' ' || c == '\t' || c == '"' || c == ':')
      {
         val_start++;
      }
      else
      {
         break;
      }
   }
   
   int val_end = val_start;
   bool in_quotes = (StringGetCharacter(json, val_start - 1) == '"');
   
   while(val_end < StringLen(json))
   {
      ushort c = StringGetCharacter(json, val_end);
      if(in_quotes)
      {
         if(c == '"' && StringGetCharacter(json, val_end - 1) != '\\')
         {
            break;
         }
      }
      else
      {
         if(c == ',' || c == '}' || c == ']' || c == '\r' || c == '\n')
         {
            break;
         }
      }
      val_end++;
   }
   
   return StringSubstr(json, val_start, val_end - val_start);
}

//+------------------------------------------------------------------+
//| Get total count of open positions managed by this EA             |
//+------------------------------------------------------------------+
int GetTotalOpenPositions()
{
   int count = 0;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(PositionGetSymbol(i) != "" && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
      {
         count++;
      }
   }
   return count;
}

//+------------------------------------------------------------------+
//| Get count of open positions for a specific symbol managed by EA  |
//+------------------------------------------------------------------+
int GetOpenPositionsBySymbol(string symbol)
{
   int count = 0;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(PositionGetSymbol(i) == symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
      {
         count++;
      }
   }
   return count;
}

//+------------------------------------------------------------------+
//| Query global kill-switch status from the backend                |
//+------------------------------------------------------------------+
void CheckGlobalKillSwitch()
{
   if(safeguard_tripped) return;
   
   string url = "http://127.0.0.1:8000/api/mt5/risk?api_key=" + InpApiKey;
   char post[], result[];
   string headers;
   
   int res = WebRequest("GET", url, headers, 1000, post, result, headers);
   if(res == 200)
   {
      string response = CharArrayToString(result);
      if(StringFind(response, "\"emergency_kill_switch\":true") >= 0 || StringFind(response, "\"emergency_kill_switch\": true") >= 0)
      {
         safeguard_tripped = true;
         Print("[EuroQuant Safeguard] CRITICAL: GLOBAL KILL-SWITCH ATTIVATO DAL SERVER!");
         CloseAllPositions();
         Alert("[EuroQuant Safeguard] CRITICAL: Global Kill-Switch attivato! Trading sospeso.");
      }
   }
}

//+------------------------------------------------------------------+
//| Safeguard verification logic                                     |
//+------------------------------------------------------------------+
void CheckSafeguards()
{
   CheckGlobalKillSwitch();
   if(safeguard_tripped) return;
   
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   
   // Reset starting equity daily at midnight
   MqlDateTime current_time;
   TimeToStruct(TimeCurrent(), current_time);
   
   if(starting_equity <= 0 || (current_time.hour == 0 && current_time.min == 0 && current_time.sec < 5))
   {
      starting_equity = equity;
      Print("[EuroQuant Safeguard] Ricalcolo della giornata. Equity di riferimento iniziale: ", DoubleToString(starting_equity, 2));
   }
   
   // 1. Daily Loss Check
   double daily_loss_limit = starting_equity * (InpMaxDailyLossPercent / 100.0);
   double current_daily_loss = starting_equity - equity;
   
   // 2. Drawdown Check
   double max_drawdown_limit = balance * (InpMaxDrawdownPercent / 100.0);
   double current_drawdown = balance - equity;
   
   if(current_daily_loss >= daily_loss_limit && daily_loss_limit > 0)
   {
      safeguard_tripped = true;
      Print("[EuroQuant Safeguard] CRITICAL: Raggiunto limite perdita giornaliera. Limite: ", DoubleToString(daily_loss_limit, 2), " | Corrente: ", DoubleToString(current_daily_loss, 2));
      CloseAllPositions();
      Alert("[EuroQuant Safeguard] CRITICAL: Limite perdita giornaliera raggiunto! Trading sospeso.");
   }
   else if(current_drawdown >= max_drawdown_limit && max_drawdown_limit > 0)
   {
      safeguard_tripped = true;
      Print("[EuroQuant Safeguard] CRITICAL: Raggiunto limite max drawdown. Limite: ", DoubleToString(max_drawdown_limit, 2), " | Corrente: ", DoubleToString(current_drawdown, 2));
      CloseAllPositions();
      Alert("[EuroQuant Safeguard] CRITICAL: Limite max drawdown raggiunto! Trading sospeso.");
   }
}

//+------------------------------------------------------------------+
//| Close all active positions managed by this Magic Number          |
//+------------------------------------------------------------------+
void CloseAllPositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
      {
         trade.PositionClose(ticket);
         Print("[EuroQuant Safeguard] Chiusura d'emergenza posizione ticket: ", ticket);
      }
   }
}

//--- ATR Caching for Dynamic Trailing
int atr_handles[];
string atr_symbols[];

int GetATRHandle(string symbol) {
    int size = ArraySize(atr_symbols);
    for(int i=0; i<size; i++) {
        if(atr_symbols[i] == symbol) return atr_handles[i];
    }
    int handle = iATR(symbol, PERIOD_D1, 14);
    ArrayResize(atr_symbols, size+1);
    ArrayResize(atr_handles, size+1);
    atr_symbols[size] = symbol;
    atr_handles[size] = handle;
    return handle;
}

double GetATR(string symbol) {
    int handle = GetATRHandle(symbol);
    if(handle == INVALID_HANDLE) return 0.0;
    double atr[1];
    if(CopyBuffer(handle, 0, 0, 1, atr) > 0) return atr[0];
    return 0.0;
}

//+------------------------------------------------------------------+
//| Apply Trailing Stop Loss to active positions                    |
//+------------------------------------------------------------------+
void ApplyTrailingStop()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
      {
         string symbol = PositionGetString(POSITION_SYMBOL);
         long pos_type = PositionGetInteger(POSITION_TYPE);
         double pos_open = PositionGetDouble(POSITION_PRICE_OPEN);
         double pos_sl = PositionGetDouble(POSITION_SL);
         double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
         int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
         
         double dynamic_ts_distance = InpTrailingStopPoints * point;
         double dynamic_ts_step = InpTrailingStepPoints * point;
         double be_trigger_distance = InpTrailingStopPoints * point;
         
         // Usa ATR per il calcolo dinamico
         double atr = GetATR(symbol);
         if(atr > 0) {
            dynamic_ts_distance = atr * 1.5; // 1.5x ATR giornaliero
            dynamic_ts_step = atr * 0.2;     // 0.2x ATR
            be_trigger_distance = atr * InpBreakEvenAtrMult; // Break-Even Trigger
         } else if (pos_open > 1000) {
            // Fallback per crypto/indici senza ATR pronto
            dynamic_ts_distance = pos_open * 0.005; // 0.5%
            dynamic_ts_step = pos_open * 0.001;     // 0.1%
            be_trigger_distance = pos_open * (InpBreakEvenFallbackPct / 100.0);
         }
         // Log diagnostico: valore ATR * moltiplicatore per Break-Even (direzione-dipendente)
         double be_activation = (pos_type == POSITION_TYPE_BUY) ? pos_open + be_trigger_distance : pos_open - be_trigger_distance;
         string pos_dir = (pos_type == POSITION_TYPE_BUY) ? "BUY" : "SELL";
         PrintFormat("[EuroQuant BE-Log] %s | Dir=%s | ATR=%.5f | Mult=x%.1f | BE Trigger=%.5f | Open=%.5f | Attivazione a: %.5f",
                     symbol, pos_dir, atr, InpBreakEvenAtrMult, be_trigger_distance, pos_open, be_activation);

         double stop_level = SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL) * point;
         double tick_size = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
         
         if(pos_type == POSITION_TYPE_BUY)
         {
            double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
            double current_profit = bid - pos_open;
            
            // Logica Break-Even
            if(InpUseBreakEven && pos_sl < pos_open && current_profit >= be_trigger_distance)
            {
               double be_level = pos_open + (tick_size > 0 ? tick_size * 2 : point * 10);
               if(bid - be_level > stop_level)
               {
                  if(trade.PositionModify(ticket, be_level, PositionGetDouble(POSITION_TP)))
                  {
                     Print("[EuroQuant Break-Even] Assicurato pareggio su BUY ticket ", ticket, " a ", DoubleToString(be_level, digits));
                     if(InpEnablePartialClose)
                     {
                        double vol = PositionGetDouble(POSITION_VOLUME);
                        double min_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
                        double lot_step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
                        double half_vol = MathRound((vol / 2.0) / lot_step) * lot_step;
                        if(half_vol >= min_lot)
                        {
                           trade.PositionClosePartial(ticket, half_vol);
                           Print("[EuroQuant Scale-Out] Chiuso 50% (", DoubleToString(half_vol, 2), " lotti) su BUY ticket ", ticket);
                        }
                     }
                  }
                  else
                     Print("[EuroQuant Break-Even] Errore su BUY ticket ", ticket, " - MT5: ", GetLastError());
                  continue; // Skip trailing until next tick to give breathing room
               }
            }
            
            // Logica Trailing Stop
            if(current_profit > dynamic_ts_distance)
            {
               double new_sl = bid - dynamic_ts_distance;
               if(tick_size > 0) new_sl = MathRound(new_sl / tick_size) * tick_size;
               
               if(new_sl > pos_sl + dynamic_ts_step || pos_sl == 0)
               {
                  if(bid - new_sl > stop_level)
                  {
                     if(trade.PositionModify(ticket, new_sl, PositionGetDouble(POSITION_TP)))
                        Print("[EuroQuant Trailing] Modificato SL BUY per ticket ", ticket, " a ", DoubleToString(new_sl, digits));
                     else
                        Print("[EuroQuant Trailing] Errore modifica SL BUY ticket ", ticket, " - MT5: ", GetLastError());
                  }
               }
            }
         }
         else if(pos_type == POSITION_TYPE_SELL)
         {
            double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
            double current_profit = pos_open - ask;
            
            // Logica Break-Even
            if(InpUseBreakEven && (pos_sl > pos_open || pos_sl == 0) && current_profit >= be_trigger_distance)
            {
               double be_level = pos_open - (tick_size > 0 ? tick_size * 2 : point * 10);
               if(be_level - ask > stop_level)
               {
                  if(trade.PositionModify(ticket, be_level, PositionGetDouble(POSITION_TP)))
                  {
                     Print("[EuroQuant Break-Even] Assicurato pareggio su SELL ticket ", ticket, " a ", DoubleToString(be_level, digits));
                     if(InpEnablePartialClose)
                     {
                        double vol = PositionGetDouble(POSITION_VOLUME);
                        double min_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
                        double lot_step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
                        double half_vol = MathRound((vol / 2.0) / lot_step) * lot_step;
                        if(half_vol >= min_lot)
                        {
                           trade.PositionClosePartial(ticket, half_vol);
                           Print("[EuroQuant Scale-Out] Chiuso 50% (", DoubleToString(half_vol, 2), " lotti) su SELL ticket ", ticket);
                        }
                     }
                  }
                  else
                     Print("[EuroQuant Break-Even] Errore su SELL ticket ", ticket, " - MT5: ", GetLastError());
                  continue;
               }
            }
            
            // Logica Trailing Stop
            if(current_profit > dynamic_ts_distance)
            {
               double new_sl = ask + dynamic_ts_distance;
               if(tick_size > 0) new_sl = MathRound(new_sl / tick_size) * tick_size;
               
               if(new_sl < pos_sl - dynamic_ts_step || pos_sl == 0)
               {
                  if(new_sl - ask > stop_level)
                  {
                     if(trade.PositionModify(ticket, new_sl, PositionGetDouble(POSITION_TP)))
                        Print("[EuroQuant Trailing] Modificato SL SELL per ticket ", ticket, " a ", DoubleToString(new_sl, digits));
                     else
                        Print("[EuroQuant Trailing] Errore modifica SL SELL ticket ", ticket, " - MT5: ", GetLastError());
                  }
               }
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Draw sleek graphical dashboard overlay on MT5 chart              |
//+------------------------------------------------------------------+
void DrawDashboard()
{
   string prefix = "EQ_DB_";
   int x_start = 10;
   int y_start = 20;
   
   // Backplate Rectangle
   string bg_name = prefix + "BG";
   if(ObjectFind(0, bg_name) < 0)
   {
      ObjectCreate(0, bg_name, OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, bg_name, OBJPROP_XDISTANCE, x_start);
      ObjectSetInteger(0, bg_name, OBJPROP_YDISTANCE, y_start);
      ObjectSetInteger(0, bg_name, OBJPROP_XSIZE, 280);
      ObjectSetInteger(0, bg_name, OBJPROP_YSIZE, 180);
      ObjectSetInteger(0, bg_name, OBJPROP_BGCOLOR, C'20, 24, 33'); 
      ObjectSetInteger(0, bg_name, OBJPROP_BORDER_COLOR, C'47, 54, 70'); 
      ObjectSetInteger(0, bg_name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, bg_name, OBJPROP_BACK, false);
      ObjectSetInteger(0, bg_name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, bg_name, OBJPROP_HIDDEN, true);
   }
   
   DrawRow(prefix + "R1", "EUROQUANT INSTITUTIONAL PORTFOLIO", x_start + 15, y_start + 10, C'255, 120, 0', 9, true);
   
   string status_str = "System Status: ACTIVE (OK)";
   color status_col = C'0, 230, 118';
   if(safeguard_tripped)
   {
      status_str = "System Status: SAFEGUARD TRIPPED";
      status_col = C'255, 23, 68';
   }
   DrawRow(prefix + "R2", status_str, x_start + 15, y_start + 30, status_col, 8, true);
   
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double pnl = equity - starting_equity;
   string pnl_text = "Daily PnL: " + DoubleToString(pnl, 2) + " " + AccountInfoString(ACCOUNT_CURRENCY);
   color pnl_col = (pnl >= 0) ? C'0, 230, 118' : C'255, 23, 68';
   DrawRow(prefix + "R3", pnl_text, x_start + 15, y_start + 50, pnl_col, 8, false);
   
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double drawdown_pct = (balance > 0) ? ((balance - equity) / balance) * 100.0 : 0.0;
   if(drawdown_pct < 0) drawdown_pct = 0.0;
   string dd_text = "Drawdown: " + DoubleToString(drawdown_pct, 2) + "% (Max Allowed: " + DoubleToString(InpMaxDrawdownPercent, 2) + "%)";
   DrawRow(prefix + "R4", dd_text, x_start + 15, y_start + 70, C'200, 200, 200', 8, false);
   
   int pos_count = GetTotalOpenPositions();
   DrawRow(prefix + "R5", "EA Open Positions: " + IntegerToString(pos_count) + " / " + IntegerToString(InpMaxOpenPositions), x_start + 15, y_start + 90, C'200, 200, 200', 8, false);
   
   string filters = "Filters: ";
   filters += InpUseVWAPFilter ? "VWAP " : "";
   filters += InpUseIchimokuFilter ? "ICHI " : "";
   if(filters == "Filters: ") filters += "NONE";
   DrawRow(prefix + "R6", filters + " | Grid: " + (InpUseGridRecovery ? "ON" : "OFF"), x_start + 15, y_start + 110, C'140, 200, 255', 8, false);
   
   DrawRow(prefix + "R7", "Sync: " + IntegerToString(InpCheckIntervalSecs) + "s | Magic: " + IntegerToString(InpMagicNumber), x_start + 15, y_start + 130, C'140, 150, 170', 7, false);
   DrawRow(prefix + "R8", "ZULU Time: " + TimeToString(TimeGMT(), TIME_SECONDS) + " Z", x_start + 15, y_start + 150, C'110, 120, 140', 7, false);
   
   ChartRedraw();
}

//+------------------------------------------------------------------+
//| Draw a single row label on chart                                 |
//+------------------------------------------------------------------+
void DrawRow(string name, string text_val, int x, int y, color col, int font_size, bool is_bold)
{
   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
      ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
   }
   ObjectSetString(0, name, OBJPROP_TEXT, text_val);
   ObjectSetInteger(0, name, OBJPROP_COLOR, col);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, font_size);
   ObjectSetString(0, name, OBJPROP_FONT, is_bold ? "Arial Bold" : "Arial");
}

//+------------------------------------------------------------------+
//| Cleanup dashboard objects on deinitialization                    |
//+------------------------------------------------------------------+
void CleanupDashboard()
{
   string prefix = "EQ_DB_";
   for(int i = ObjectsTotal(0) - 1; i >= 0; i--)
   {
      string name = ObjectName(0, i);
      if(StringFind(name, prefix) == 0)
      {
         ObjectDelete(0, name);
      }
   }
   ChartRedraw();
}

//+------------------------------------------------------------------+
//| Sync live positions to Docker backend                            |
//+------------------------------------------------------------------+
void SyncLivePositions()
{
   string baseUrl = InpApiUrl;
   StringReplace(baseUrl, "signals", "positions");
   string url = baseUrl + "?api_key=" + InpApiKey;
   string json = "{\"positions\":[";
   
   bool first = true;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(PositionGetSymbol(i) != "")
      {
         if(!first) json += ",";
         json += "{";
         json += "\"ticker\":\"" + PositionGetString(POSITION_SYMBOL) + "\",";
         json += "\"quantity\":" + DoubleToString(PositionGetDouble(POSITION_VOLUME), 2) + ",";
         json += "\"avg_price\":" + DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), 5) + ",";
         json += "\"current_price\":" + DoubleToString(PositionGetDouble(POSITION_PRICE_CURRENT), 5) + ",";
         json += "\"unrealized_pnl\":" + DoubleToString(PositionGetDouble(POSITION_PROFIT), 2);
         json += "}";
         first = false;
      }
   }
   json += "]}";
   
   char data[];
   StringToCharArray(json, data, 0, WHOLE_ARRAY, CP_UTF8);
   // Remove trailing null terminator from the char array
   int size = ArraySize(data);
   if(size > 0 && data[size-1] == 0) ArrayResize(data, size-1);
   
   char result[];
   string result_headers;
   string headers = "Content-Type: application/json\r\n";
   
   int res = WebRequest("POST", url, headers, 5000, data, result, result_headers);
   if(res == -1) {
      Print("[EuroQuant Sync] WebRequest POST failed! Error: ", GetLastError(), " URL: ", url);
   } else if (res != 200) {
      Print("[EuroQuant Sync] HTTP Error: ", res, " | Response: ", CharArrayToString(result));
   }
}

//+------------------------------------------------------------------+
//| Log order execution to Docker backend                            |
//+------------------------------------------------------------------+
void LogExecution(string ticker, string action, double volume, double fill_price, double requested_price)
{
   double slippage = 0.0;
   if(action == "BUY") slippage = fill_price - requested_price;
   else if(action == "SELL") slippage = requested_price - fill_price;
   
   string baseUrl = InpApiUrl;
   StringReplace(baseUrl, "signals", "execution-log");
   string url = baseUrl + "?api_key=" + InpApiKey;
   string json = "{";
   json += "\"ticker\":\"" + ticker + "\",";
   json += "\"action\":\"" + action + "\",";
   json += "\"quantity\":" + DoubleToString(volume, 2) + ",";
   json += "\"fill_price\":" + DoubleToString(fill_price, 5) + ",";
   json += "\"slippage\":" + DoubleToString(slippage, 5);
   json += "}";
   
   char data[];
   StringToCharArray(json, data, 0, WHOLE_ARRAY, CP_UTF8);
   int size = ArraySize(data);
   if(size > 0 && data[size-1] == 0) ArrayResize(data, size-1);
   
   char result[];
   string result_headers;
   string headers = "Content-Type: application/json\r\n";
   
   WebRequest("POST", url, headers, 5000, data, result, result_headers);
}

//+------------------------------------------------------------------+
//| Check if signal aligns with Daily VWAP                           |
//+------------------------------------------------------------------+
bool IsVWAPAligned(string symbol, string action)
{
   // Approssimazione VWAP giornaliero tramite iCustom o calcolo manuale.
   // Per performance, usiamo un calcolo iterativo sulle barre M1/M5 della giornata corrente.
   datetime start_of_day = iTime(symbol, PERIOD_D1, 0);
   int bars_today = iBarShift(symbol, PERIOD_M5, start_of_day);
   if(bars_today <= 0) return true; // Dati insufficienti
   
   double sum_pv = 0;
   double sum_v = 0;
   
   double close[];
   long tick_volume[];
   if(CopyClose(symbol, PERIOD_M5, 0, bars_today, close) > 0 &&
      CopyTickVolume(symbol, PERIOD_M5, 0, bars_today, tick_volume) > 0)
   {
      for(int i = 0; i < bars_today; i++)
      {
         sum_pv += close[i] * (double)tick_volume[i];
         sum_v += (double)tick_volume[i];
      }
   }
   
   if(sum_v == 0) return true;
   
   double vwap = sum_pv / sum_v;
   double current_price = (action == "BUY") ? SymbolInfoDouble(symbol, SYMBOL_ASK) : SymbolInfoDouble(symbol, SYMBOL_BID);
   
   if(action == "BUY") return current_price >= vwap;
   if(action == "SELL") return current_price <= vwap;
   
   return true;
}

//+------------------------------------------------------------------+
//| Check if signal aligns with Ichimoku Kumo Cloud                  |
//+------------------------------------------------------------------+
bool IsIchimokuAligned(string symbol, string action)
{
   int handle = iIchimoku(symbol, PERIOD_H1, 9, 26, 52);
   if(handle == INVALID_HANDLE) return true;
   
   double span_a[], span_b[];
   if(CopyBuffer(handle, 2, 0, 1, span_a) <= 0 || CopyBuffer(handle, 3, 0, 1, span_b) <= 0)
   {
      return true;
   }
   
   double kumo_top = MathMax(span_a[0], span_b[0]);
   double kumo_bottom = MathMin(span_a[0], span_b[0]);
   double current_price = (action == "BUY") ? SymbolInfoDouble(symbol, SYMBOL_ASK) : SymbolInfoDouble(symbol, SYMBOL_BID);
   
   if(action == "BUY") return current_price >= kumo_top; // Prezzo sopra la nuvola
   if(action == "SELL") return current_price <= kumo_bottom; // Prezzo sotto la nuvola
   
   return true; // Se dentro la nuvola, potrebbe essere filtrato. Ma decidiamo che dentro kumo non entriamo (ritorna false).
   // Wait, the return below will never be reached, let's fix it:
}

//+------------------------------------------------------------------+
//| Grid Recovery System: Averages down losing positions             |
//+------------------------------------------------------------------+
void ManageGridRecovery()
{
   // Mappatura per contare il numero di griglie per simbolo e calcolare avg price
   string tracked_symbols[];
   int symbol_count = 0;
   
   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
      {
         string sym = PositionGetString(POSITION_SYMBOL);
         bool found = false;
         for(int s = 0; s < symbol_count; s++) { if(tracked_symbols[s] == sym) { found = true; break; } }
         if(!found)
         {
            ArrayResize(tracked_symbols, symbol_count + 1);
            tracked_symbols[symbol_count] = sym;
            symbol_count++;
         }
      }
   }
   
   for(int s = 0; s < symbol_count; s++)
   {
      string sym = tracked_symbols[s];
      int pos_buy_count = 0, pos_sell_count = 0;
      double last_buy_price = 0, last_sell_price = 0;
      double total_buy_vol = 0, total_sell_vol = 0;
      double total_buy_value = 0, total_sell_value = 0;
      
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong ticket = PositionGetTicket(i);
         if(PositionGetString(POSITION_SYMBOL) == sym && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         {
            long type = PositionGetInteger(POSITION_TYPE);
            double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
            double vol = PositionGetDouble(POSITION_VOLUME);
            
            if(type == POSITION_TYPE_BUY)
            {
               pos_buy_count++;
               total_buy_vol += vol;
               total_buy_value += open_price * vol;
               if(last_buy_price == 0 || open_price < last_buy_price) last_buy_price = open_price;
            }
            else if(type == POSITION_TYPE_SELL)
            {
               pos_sell_count++;
               total_sell_vol += vol;
               total_sell_value += open_price * vol;
               if(last_sell_price == 0 || open_price > last_sell_price) last_sell_price = open_price;
            }
         }
      }
      
      double point = SymbolInfoDouble(sym, SYMBOL_POINT);
      
      // Manage BUY Grid
      if(pos_buy_count > 0 && pos_buy_count <= InpMaxGridLevels)
      {
         double ask = SymbolInfoDouble(sym, SYMBOL_ASK);
         if(last_buy_price - ask >= InpGridStepPoints * point)
         {
            double lot_step = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);
            double min_lot = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
            double max_lot = SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX);
            
            double new_vol = total_buy_vol * InpGridMultiplier;
            new_vol = MathRound(new_vol / lot_step) * lot_step;
            if(new_vol < min_lot) new_vol = min_lot;
            if(new_vol > max_lot) new_vol = max_lot;
            
            Print("[Grid Recovery] Apertura livello ", pos_buy_count + 1, " BUY su ", sym, " Lotti: ", new_vol);
            if(trade.Buy(new_vol, sym, ask, 0, 0, "EQ Grid Buy"))
            {
               // Adjust overall TP only if not ignored
               if(!InpIgnoreTakeProfit)
               {
                  double avg_price = (total_buy_value + (ask * new_vol)) / (total_buy_vol + new_vol);
                  double new_tp = avg_price + (100 * point); // 100 points profit target
                  for(int i = PositionsTotal() - 1; i >= 0; i--)
                  {
                     ulong ticket = PositionGetTicket(i);
                     if(PositionGetString(POSITION_SYMBOL) == sym && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber && PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
                     {
                        double current_tp = PositionGetDouble(POSITION_TP);
                        if(MathAbs(current_tp - new_tp) > point)
                           trade.PositionModify(ticket, PositionGetDouble(POSITION_SL), new_tp);
                     }
                  }
               }
            }
         }
      }
      
      // Manage SELL Grid
      if(pos_sell_count > 0 && pos_sell_count <= InpMaxGridLevels)
      {
         double bid = SymbolInfoDouble(sym, SYMBOL_BID);
         if(bid - last_sell_price >= InpGridStepPoints * point)
         {
            double lot_step = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);
            double min_lot = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
            double max_lot = SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX);
            
            double new_vol = total_sell_vol * InpGridMultiplier;
            new_vol = MathRound(new_vol / lot_step) * lot_step;
            if(new_vol < min_lot) new_vol = min_lot;
            if(new_vol > max_lot) new_vol = max_lot;
            
            Print("[Grid Recovery] Apertura livello ", pos_sell_count + 1, " SELL su ", sym, " Lotti: ", new_vol);
            if(trade.Sell(new_vol, sym, bid, 0, 0, "EQ Grid Sell"))
            {
               // Adjust overall TP only if not ignored
               if(!InpIgnoreTakeProfit)
               {
                  double avg_price = (total_sell_value + (bid * new_vol)) / (total_sell_vol + new_vol);
                  double new_tp = avg_price - (100 * point); // 100 points profit target
                  for(int i = PositionsTotal() - 1; i >= 0; i--)
                  {
                     ulong ticket = PositionGetTicket(i);
                     if(PositionGetString(POSITION_SYMBOL) == sym && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber && PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_SELL)
                     {
                        double current_tp = PositionGetDouble(POSITION_TP);
                        if(MathAbs(current_tp - new_tp) > point)
                           trade.PositionModify(ticket, PositionGetDouble(POSITION_SL), new_tp);
                     }
                  }
               }
            }
         }
      }
   }
}
//+------------------------------------------------------------------+
