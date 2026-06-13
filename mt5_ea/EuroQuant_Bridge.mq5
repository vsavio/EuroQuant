//+------------------------------------------------------------------+
//|                                            EuroQuant_Bridge.mq5 |
//|                                  Copyright 2026, EuroQuant Team  |
//|                                       https://localhost:3000/    |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, EuroQuant Team"
#property link      "https://localhost:3000/"
#property version   "1.00"
#property description "Bridge EA connecting EuroQuant Quantitative Signals to MT5 execution."

// Import Trade Library
#include <Trade\Trade.mqh>
CTrade trade;

//--- Input Parameters
input group "=== EUROQUANT API SETTINGS ==="
input string   InpApiUrl            = "http://localhost:8000/api/mt5/signals"; // API Endpoint URL
input string   InpTickerName        = "";                                      // Ticker Name (lascia vuoto per il simbolo corrente)
input int      InpCheckIntervalSecs = 60;                                      // Frequenza controllo API (in secondi)

input group "=== RISK & POSITION MANAGEMENT ==="
enum ENUM_SIZING_MODE {
   SIZING_MIN_LOT_MULTIPLIER = 0, // Moltiplicatore del Lotto Minimo (Default)
   SIZING_RISK_PERCENT = 1,       // % Rischio sul Capitale per trade (Richiede Stop Loss)
   SIZING_MARGIN_PERCENT = 2      // % Margine sul Capitale per trade
};
input ENUM_SIZING_MODE InpSizingMode        = SIZING_MIN_LOT_MULTIPLIER;               // Modalità Calcolo Lotto
input double   InpLotMultiplier     = 1.0;                                     // Quota/Moltiplicatore rispetto al lotto minimo (se Modalità = Lotto Minimo)
input double   InpRiskPercent       = 1.0;                                     // % di Rischio sul Capitale per operazione (se Modalità = Risk %)
input double   InpMarginPercent     = 5.0;                                     // % di Margine sul Capitale per operazione (se Modalità = Margine %)
input bool     InpEnablePartialClose = true;                                   // Abilita Chiusura Parziale (TP1) & Break-Even
input double   InpPartialCloseAtrMultiplier = 1.5;                             // Moltiplicatore ATR per target TP1 (parziale)
input ulong    InpMagicNumber       = 20260610;                                // Magic Number per identificare le posizioni
input int      InpMaxSpreadPoints   = 50;                                      // Spread massimo consentito in punti (se InpMaxSpreadPercent <= 0)
input double   InpMaxSpreadPercent  = 0.25;                                    // Spread massimo consentito in % del prezzo (0 per disabilitare)
input int      InpMaxSlippagePoints = 30;                                      // Slippage massimo consentito in punti
input int      InpOrderRetries      = 3;                                       // Numero di tentativi invio ordine
input bool     InpEnableTrading     = true;                                    // Abilita esecuzione ordini a mercato
input bool     InpSendAlerts        = true;                                    // Abilita gli alert grafici nel terminale

input group "=== TRAILING STOP SETTINGS ==="
input bool     InpUseTrailingStop   = true;                                    // Abilita Trailing Stop
input int      InpTrailingStopPoints = 150;                                     // Punti per Trailing Stop
input int      InpTrailingStepPoints = 50;                                      // Step per Trailing Stop

input group "=== ACCOUNT SAFEGUARD SETTINGS ==="
input double   InpMaxDailyLossPercent = 2.0;                                    // Max perdita giornaliera consentita (%)
input double   InpMaxDrawdownPercent = 5.0;                                     // Max drawdown totale consentito (%)

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
string   last_signal = "";

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
   Print("[EuroQuant Bridge] Expert Advisor inizializzato correttamente. Magic Number: ", InpMagicNumber, " | Equity iniziale: ", DoubleToString(starting_equity, 2));
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   CleanupDashboard();
   Print("[EuroQuant Bridge] Expert Advisor arrestato e pannello grafico rimosso.");
}

//+------------------------------------------------------------------+
//| Expert timer function                                            |
//+------------------------------------------------------------------+
void OnTimer()
{
   datetime now = TimeCurrent();
   
   // Perform Safeguard Check
   CheckSafeguards();
   
   // Perform Trailing Stop Check
   if(InpUseTrailingStop && !safeguard_tripped)
   {
      ApplyTrailingStop();
   }
   
   // Fetch signals from API
   if(now - last_check_time >= InpCheckIntervalSecs && !safeguard_tripped)
   {
      last_check_time = now;
      FetchAndExecuteSignal();
   }
   
   // Update Graphic Dashboard Panel
   DrawDashboard();
}

//+------------------------------------------------------------------+
//| Fetch signals from EuroQuant API and execute trade logic          |
//+------------------------------------------------------------------+
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
//| Fetch signals from EuroQuant API and execute trade logic          |
//+------------------------------------------------------------------+
void FetchAndExecuteSignal()
{
   // Determine Ticker to request (clean the broker suffix if present)
   string ticker = InpTickerName;
   if(StringLen(ticker) == 0)
   {
      ticker = _Symbol;
      
      // Strip any of the active broker suffixes if present
      string suffixes[7] = {InpMilanSuffix, InpFrankfurtSuffix, InpAmsterdamSuffix, InpParisSuffix, InpMadridSuffix, InpLondonSuffix, InpForexSuffix};
      for(int i = 0; i < 7; i++)
      {
         if(StringLen(suffixes[i]) > 0)
         {
            int suffix_pos = StringFind(ticker, suffixes[i]);
            if(suffix_pos != -1)
            {
               ticker = StringSubstr(ticker, 0, suffix_pos);
               break;
            }
         }
      }
   }
   
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double margin = AccountInfoDouble(ACCOUNT_MARGIN);
   double margin_free = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   double margin_level = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
   double profit = AccountInfoDouble(ACCOUNT_PROFIT);
   long login = AccountInfoInteger(ACCOUNT_LOGIN);
   string company = AccountInfoString(ACCOUNT_COMPANY);
   StringReplace(company, " ", "%20");
   
   string request_url = InpApiUrl + "?ticker=" + ticker +
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
   int timeout = 5000; // 5 seconds
   
   ResetLastError();
   
   // Execute HTTP Request
   int res = WebRequest("GET", request_url, NULL, NULL, timeout, post, 0, result, result_headers);
   
   if(res == -1)
   {
      int err = GetLastError();
      Print("[EuroQuant Bridge] Errore di connessione HTTP (errore ", err, "). Assicurati di aver abilitato l'URL nelle impostazioni di MT5 (Strumenti -> Opzioni -> Consiglieri Esperti).");
      return;
   }
   
   if(res != 200)
   {
      Print("[EuroQuant Bridge] L'API ha risposto con codice HTTP: ", res);
      return;
   }
   
   // Convert result to string
   string json_response = CharArrayToString(result);
   
   // Parse JSON response
   string action = GetJsonValue(json_response, "action");
   string entry_price_str = GetJsonValue(json_response, "entry_price");
   string stop_loss_str = GetJsonValue(json_response, "stop_loss");
   string take_profit_str = GetJsonValue(json_response, "take_profit");
   string reason = GetJsonValue(json_response, "reason");
   string vol_str = GetJsonValue(json_response, "volatility_lot_sizing");
   
   double entry_price = StringToDouble(entry_price_str);
   double stop_loss = StringToDouble(stop_loss_str);
   double take_profit = StringToDouble(take_profit_str);
   double volatility_lot_sizing = (StringLen(vol_str) > 0) ? StringToDouble(vol_str) : 1.0;
   
   // Normalize Action
   StringToUpper(action);
   
   if(StringLen(action) == 0)
   {
      Print("[EuroQuant Bridge] Impossibile decodificare il segnale. Risposta JSON: ", json_response);
      return;
   }
   
   // Resolve dynamic trade symbol with appropriate broker suffixes
   string api_symbol = GetJsonValue(json_response, "mt5_symbol");
   if(StringLen(api_symbol) == 0)
   {
      api_symbol = ticker;
   }
   
   string api_ticker = GetJsonValue(json_response, "ticker");
   if(StringLen(api_ticker) == 0)
   {
      api_ticker = ticker;
   }
   
   string trade_symbol = ResolveMt5Symbol(api_ticker, api_symbol);
   
   int digits = (int)SymbolInfoInteger(trade_symbol, SYMBOL_DIGITS);
   
   // Log status
   Print("[EuroQuant Bridge] Segnale ricevuto per ", trade_symbol, ": ", action, 
         " | Price: ", DoubleToString(entry_price, digits),
         " | SL: ", DoubleToString(stop_loss, digits),
         " | TP: ", DoubleToString(take_profit, digits),
         " | Vol Sizing: ", DoubleToString(volatility_lot_sizing, 2));
         
   if(action != last_signal)
   {
      if(InpSendAlerts)
      {
         Alert("[EuroQuant Bridge] Nuovo segnale per ", trade_symbol, ": ", action, " | Motivo: ", reason);
      }
      last_signal = action;
   }
   
   if(!InpEnableTrading)
   {
      return;
   }
   
    // Check Spread
    int spread = (int)SymbolInfoInteger(trade_symbol, SYMBOL_SPREAD);
    double ask_price = SymbolInfoDouble(trade_symbol, SYMBOL_ASK);
    double point_val = SymbolInfoDouble(trade_symbol, SYMBOL_POINT);
    double spread_val = spread * point_val;
    double spread_pct = (ask_price > 0) ? (spread_val / ask_price) * 100.0 : 0.0;
    
    if(InpMaxSpreadPercent > 0)
    {
       if(spread_pct > InpMaxSpreadPercent)
       {
          Print("[EuroQuant Bridge] Spread su ", trade_symbol, " troppo alto (", DoubleToString(spread_pct, 3), "% > limit ", DoubleToString(InpMaxSpreadPercent, 3), "%). Operazione annullata.");
          return;
       }
    }
    else
    {
       if(spread > InpMaxSpreadPoints)
       {
          Print("[EuroQuant Bridge] Spread su ", trade_symbol, " troppo alto (", spread, " punti > limit ", InpMaxSpreadPoints, " punti). Operazione annullata.");
          return;
       }
    }
   
   // Manage Positions
   ManagePositions(trade_symbol, action, stop_loss, take_profit, volatility_lot_sizing);
}

//+------------------------------------------------------------------+
//| Manage existing positions and enter new trades based on signal   |
//+------------------------------------------------------------------+
void ManagePositions(string trade_symbol, string action, double sl, double tp, double volatility_lot_sizing)
{
   bool has_buy = false;
   bool has_sell = false;
   
   // Count current positions open with this magic number
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionGetInteger(POSITION_MAGIC) == InpMagicNumber && PositionGetString(POSITION_SYMBOL) == trade_symbol)
      {
         long pos_type = PositionGetInteger(POSITION_TYPE);
         if(pos_type == POSITION_TYPE_BUY)
         {
            has_buy = true;
            // Close BUY position if signal is SELL or CLOSE_ALL
            if(action == "SELL" || action == "CLOSE_ALL")
            {
               trade.PositionClose(ticket);
               Print("[EuroQuant Bridge] Chiusa posizione BUY precedente su ", trade_symbol, " su segnale ", action, ".");
               has_buy = false;
            }
            else if(InpEnablePartialClose)
            {
               double pos_open = PositionGetDouble(POSITION_PRICE_OPEN);
               double pos_sl = PositionGetDouble(POSITION_PRICE_SL);
               double pos_vol = PositionGetDouble(POSITION_VOLUME);
               double current_bid = SymbolInfoDouble(trade_symbol, SYMBOL_BID);
               double sl_dist = (pos_sl > 0) ? MathAbs(pos_open - pos_sl) : MathAbs(pos_open - sl);
               
               if(sl_dist > 0 && pos_sl < pos_open)
               {
                  double tp1_price = pos_open + InpPartialCloseAtrMultiplier * sl_dist;
                  if(current_bid >= tp1_price)
                  {
                     double min_lot = SymbolInfoDouble(trade_symbol, SYMBOL_VOLUME_MIN);
                     double lot_step = SymbolInfoDouble(trade_symbol, SYMBOL_VOLUME_STEP);
                     double close_vol = pos_vol / 2.0;
                     if(lot_step > 0)
                        close_vol = MathRound(close_vol / lot_step) * lot_step;
                     if(close_vol < min_lot) close_vol = min_lot;
                     
                     if(close_vol < pos_vol)
                     {
                        if(trade.PositionClose(ticket, close_vol))
                        {
                           Print("[EuroQuant Bridge] TP1 Raggiunto su BUY ", trade_symbol, ". Chiusura parziale di ", DoubleToString(close_vol, 2), " lotti.");
                           double current_tp = PositionGetDouble(POSITION_TP);
                           trade.PositionModify(ticket, pos_open, current_tp);
                        }
                     }
                  }
               }
            }
         }
         else if(pos_type == POSITION_TYPE_SELL)
         {
            has_sell = true;
            // Close SELL position if signal is BUY or CLOSE_ALL
            if(action == "BUY" || action == "CLOSE_ALL")
            {
               trade.PositionClose(ticket);
               Print("[EuroQuant Bridge] Chiusa posizione SELL precedente su ", trade_symbol, " su segnale ", action, ".");
               has_sell = false;
            }
            else if(InpEnablePartialClose)
            {
               double pos_open = PositionGetDouble(POSITION_PRICE_OPEN);
               double pos_sl = PositionGetDouble(POSITION_PRICE_SL);
               double pos_vol = PositionGetDouble(POSITION_VOLUME);
               double current_ask = SymbolInfoDouble(trade_symbol, SYMBOL_ASK);
               double sl_dist = (pos_sl > 0) ? MathAbs(pos_open - pos_sl) : MathAbs(pos_open - sl);
               
               if(sl_dist > 0 && (pos_sl > pos_open || pos_sl == 0))
               {
                  double tp1_price = pos_open - InpPartialCloseAtrMultiplier * sl_dist;
                  if(current_ask <= tp1_price)
                  {
                     double min_lot = SymbolInfoDouble(trade_symbol, SYMBOL_VOLUME_MIN);
                     double lot_step = SymbolInfoDouble(trade_symbol, SYMBOL_VOLUME_STEP);
                     double close_vol = pos_vol / 2.0;
                     if(lot_step > 0)
                        close_vol = MathRound(close_vol / lot_step) * lot_step;
                     if(close_vol < min_lot) close_vol = min_lot;
                     
                     if(close_vol < pos_vol)
                     {
                        if(trade.PositionClose(ticket, close_vol))
                        {
                           Print("[EuroQuant Bridge] TP1 Raggiunto su SELL ", trade_symbol, ". Chiusura parziale di ", DoubleToString(close_vol, 2), " lotti.");
                           double current_tp = PositionGetDouble(POSITION_TP);
                           trade.PositionModify(ticket, pos_open, current_tp);
                        }
                     }
                  }
               }
            }
         }
      }
   }
   
   if(action == "CLOSE_ALL" || action == "HOLD" || action == "NEUTRAL" || action == "NONE")
   {
      return;
   }

   
    // Calculate lot size dynamically based on selected sizing mode
    double min_lot = SymbolInfoDouble(trade_symbol, SYMBOL_VOLUME_MIN);
    double max_lot = SymbolInfoDouble(trade_symbol, SYMBOL_VOLUME_MAX);
    double lot_step = SymbolInfoDouble(trade_symbol, SYMBOL_VOLUME_STEP);
    
    if(min_lot <= 0) return;
    
    double trade_lot = min_lot;
    
    if(InpSizingMode == SIZING_MIN_LOT_MULTIPLIER)
    {
       trade_lot = min_lot * InpLotMultiplier * volatility_lot_sizing;
    }
    else if(InpSizingMode == SIZING_RISK_PERCENT)
    {
       double balance = AccountInfoDouble(ACCOUNT_BALANCE);
       double risk_amount = balance * (InpRiskPercent / 100.0);
       double sl_distance = MathAbs(((action == "BUY") ? SymbolInfoDouble(trade_symbol, SYMBOL_ASK) : SymbolInfoDouble(trade_symbol, SYMBOL_BID)) - sl);
       
       if(sl_distance > 0)
       {
          double tick_value = SymbolInfoDouble(trade_symbol, SYMBOL_TRADE_TICK_VALUE);
          double tick_size = SymbolInfoDouble(trade_symbol, SYMBOL_TRADE_TICK_SIZE);
          if(tick_size > 0 && tick_value > 0)
          {
             double sl_distance_ticks = sl_distance / tick_size;
             trade_lot = (risk_amount / (sl_distance_ticks * tick_value)) * volatility_lot_sizing;
          }
       }
       else
       {
          trade_lot = min_lot * InpLotMultiplier * volatility_lot_sizing;
       }
    }
    else if(InpSizingMode == SIZING_MARGIN_PERCENT)
    {
       double balance = AccountInfoDouble(ACCOUNT_BALANCE);
       double target_margin = balance * (InpMarginPercent / 100.0);
       double margin_one_lot = 0.0;
       
       ENUM_ORDER_TYPE order_type = (action == "BUY") ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
       double check_price = (action == "BUY") ? SymbolInfoDouble(trade_symbol, SYMBOL_ASK) : SymbolInfoDouble(trade_symbol, SYMBOL_BID);
       
       if(check_price > 0 && OrderCalcMargin(order_type, trade_symbol, 1.0, check_price, margin_one_lot) && margin_one_lot > 0)
       {
          trade_lot = (target_margin / margin_one_lot) * volatility_lot_sizing;
       }
       else
       {
          trade_lot = min_lot * InpLotMultiplier * volatility_lot_sizing;
       }
    }
    
    // Normalize to broker volume step
    if(lot_step > 0)
    {
       trade_lot = MathRound(trade_lot / lot_step) * lot_step;
    }
    
    // Apply bounds checks
    if(trade_lot < min_lot) trade_lot = min_lot;
    if(trade_lot > max_lot) trade_lot = max_lot;
   
   double point = SymbolInfoDouble(trade_symbol, SYMBOL_POINT);
   
    // Place Orders
    if(action == "BUY" && !has_buy)
    {
       double ask = SymbolInfoDouble(trade_symbol, SYMBOL_ASK);
       
       // Safety SL/TP bounds checks
       if(sl >= ask) sl = ask - 100 * point;
       if(tp <= ask && tp > 0) tp = ask + 200 * point;
       
       bool order_placed = false;
       for(int retry = 0; retry < InpOrderRetries; retry++)
       {
          ResetLastError();
          if(trade.Buy(trade_lot, trade_symbol, ask, sl, tp, "EuroQuant Buy Signal"))
          {
             uint retcode = trade.ResultRetcode();
             if(retcode == TRADE_RETCODE_DONE || retcode == TRADE_RETCODE_PLACED)
             {
                order_placed = true;
                break;
             }
             Print("[EuroQuant Bridge] Tentativo BUY fallito. Retcode: ", retcode, ". Riprovo...");
          }
          else
          {
             Print("[EuroQuant Bridge] Chiamata Buy fallita. Errore: ", GetLastError(), ". Riprovo...");
          }
          Sleep(500);
          ask = SymbolInfoDouble(trade_symbol, SYMBOL_ASK);
       }
       
       if(order_placed)
       {
          Print("[EuroQuant Bridge] Inviato ordine BUY a mercato su ", trade_symbol, ". Volume calcolato: ", DoubleToString(trade_lot, 2), " (Lotto Minimo: ", DoubleToString(min_lot, 2), ")");
       }
       else
       {
          Print("[EuroQuant Bridge] Impossibile inserire ordine BUY su ", trade_symbol, " dopo ", InpOrderRetries, " tentativi.");
       }
    }
    else if(action == "SELL" && !has_sell)
    {
       double bid = SymbolInfoDouble(trade_symbol, SYMBOL_BID);
       
       // Safety SL/TP bounds checks
       if(sl <= bid && sl > 0) sl = bid + 100 * point;
       if(tp >= bid) tp = bid - 200 * point;
       
       bool order_placed = false;
       for(int retry = 0; retry < InpOrderRetries; retry++)
       {
          ResetLastError();
          if(trade.Sell(trade_lot, trade_symbol, bid, sl, tp, "EuroQuant Sell Signal"))
          {
             uint retcode = trade.ResultRetcode();
             if(retcode == TRADE_RETCODE_DONE || retcode == TRADE_RETCODE_PLACED)
             {
                order_placed = true;
                break;
             }
             Print("[EuroQuant Bridge] Tentativo SELL fallito. Retcode: ", retcode, ". Riprovo...");
          }
          else
          {
             Print("[EuroQuant Bridge] Chiamata Sell fallita. Errore: ", GetLastError(), ". Riprovo...");
          }
          Sleep(500);
          bid = SymbolInfoDouble(trade_symbol, SYMBOL_BID);
       }
       
       if(order_placed)
       {
          Print("[EuroQuant Bridge] Inviato ordine SELL a mercato su ", trade_symbol, ". Volume calcolato: ", DoubleToString(trade_lot, 2), " (Lotto Minimo: ", DoubleToString(min_lot, 2), ")");
       }
       else
       {
          Print("[EuroQuant Bridge] Impossibile inserire ordine SELL su ", trade_symbol, " dopo ", InpOrderRetries, " tentativi.");
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
   
   // Skip spaces, colons, and opening quotes
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
         // End on matching quote, ignoring escaped quotes
         if(c == '"' && StringGetCharacter(json, val_end - 1) != '\\')
         {
            break;
         }
      }
      else
      {
         // End on JSON delimiter
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
//| Safeguard verification logic                                     |
//+------------------------------------------------------------------+
void CheckSafeguards()
{
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
         
         if(pos_type == POSITION_TYPE_BUY)
         {
            double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
            double stop_level = SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL) * point;
            
            if(bid - pos_open > InpTrailingStopPoints * point)
            {
               double new_sl = bid - InpTrailingStopPoints * point;
               double tick_size = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
               if(tick_size > 0) new_sl = MathRound(new_sl / tick_size) * tick_size;
               
               if(new_sl > pos_sl + InpTrailingStepPoints * point || pos_sl == 0)
               {
                  if(bid - new_sl > stop_level)
                  {
                     trade.PositionModify(ticket, new_sl, PositionGetDouble(POSITION_TP));
                     Print("[EuroQuant Trailing] Modificato SL BUY per ticket ", ticket, " a ", DoubleToString(new_sl, digits));
                  }
               }
            }
         }
         else if(pos_type == POSITION_TYPE_SELL)
         {
            double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
            double stop_level = SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL) * point;
            
            if(pos_open - ask > InpTrailingStopPoints * point)
            {
               double new_sl = ask + InpTrailingStopPoints * point;
               double tick_size = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
               if(tick_size > 0) new_sl = MathRound(new_sl / tick_size) * tick_size;
               
               if(new_sl < pos_sl - InpTrailingStepPoints * point || pos_sl == 0)
               {
                  if(new_sl - ask > stop_level)
                  {
                     trade.PositionModify(ticket, new_sl, PositionGetDouble(POSITION_TP));
                     Print("[EuroQuant Trailing] Modificato SL SELL per ticket ", ticket, " a ", DoubleToString(new_sl, digits));
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
      ObjectSetInteger(0, bg_name, OBJPROP_YSIZE, 160);
      ObjectSetInteger(0, bg_name, OBJPROP_BGCOLOR, C'20, 24, 33'); 
      ObjectSetInteger(0, bg_name, OBJPROP_BORDER_COLOR, C'47, 54, 70'); 
      ObjectSetInteger(0, bg_name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, bg_name, OBJPROP_BACK, false);
      ObjectSetInteger(0, bg_name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, bg_name, OBJPROP_HIDDEN, true);
   }
   
   DrawRow(prefix + "R1", "EUROQUANT SINGLE-BRIDGE", x_start + 15, y_start + 10, C'255, 120, 0', 9, true);
   
   string status_str = "Status: ACTIVE (OK)";
   color status_col = C'0, 230, 118';
   if(safeguard_tripped)
   {
      status_str = "Status: SAFEGUARD TRIPPED";
      status_col = C'255, 23, 68';
   }
   DrawRow(prefix + "R2", status_str, x_start + 15, y_start + 30, status_col, 8, true);
   
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double pnl = equity - starting_equity;
   string pnl_text = "PnL Giornaliero: " + DoubleToString(pnl, 2) + " " + AccountInfoString(ACCOUNT_CURRENCY);
   color pnl_col = (pnl >= 0) ? C'0, 230, 118' : C'255, 23, 68';
   DrawRow(prefix + "R3", pnl_text, x_start + 15, y_start + 50, pnl_col, 8, false);
   
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double drawdown_pct = (balance > 0) ? ((balance - equity) / balance) * 100.0 : 0.0;
   if(drawdown_pct < 0) drawdown_pct = 0.0;
   string dd_text = "Drawdown: " + DoubleToString(drawdown_pct, 2) + "% (Max: " + DoubleToString(InpMaxDrawdownPercent, 2) + "%)";
   DrawRow(prefix + "R4", dd_text, x_start + 15, y_start + 70, C'200, 200, 200', 8, false);
   
   int pos_count = 0;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(PositionGetSymbol(i) != "" && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
      {
         pos_count++;
      }
   }
   DrawRow(prefix + "R5", "Posizioni EA: " + IntegerToString(pos_count), x_start + 15, y_start + 90, C'200, 200, 200', 8, false);
   DrawRow(prefix + "R6", "Magic: " + IntegerToString(InpMagicNumber) + " | Check: " + IntegerToString(InpCheckIntervalSecs) + "s", x_start + 15, y_start + 110, C'140, 150, 170', 7, false);
   DrawRow(prefix + "R7", "Zulu Time: " + TimeToString(TimeGMT(), TIME_SECONDS) + " Z", x_start + 15, y_start + 130, C'110, 120, 140', 7, false);
   
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
