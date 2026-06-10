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
input string   InpApiUrl            = "http://localhost:8000/api/mt5/signals"; // API Endpoint URL (lista completa)
input int      InpCheckIntervalSecs = 120;                                     // Frequenza controllo API (in secondi)

input group "=== RISK & POSITION MANAGEMENT ==="
input double   InpLotMultiplier     = 1.0;                                     // Quota/Moltiplicatore rispetto al lotto minimo di ciascun simbolo
input ulong    InpMagicNumber       = 20260620;                                // Magic Number per identificare le posizioni
input int      InpMaxSpreadPoints   = 50;                                      // Spread massimo consentito in punti
input bool     InpEnableTrading     = true;                                    // Abilita esecuzione ordini a mercato
input bool     InpSendAlerts        = true;                                    // Abilita gli alert grafici nel terminale

input group "=== TRAILING STOP SETTINGS ==="
input bool     InpUseTrailingStop   = true;                                    // Abilita Trailing Stop
input int      InpTrailingStopPoints = 150;                                     // Punti per Trailing Stop
input int      InpTrailingStepPoints = 50;                                      // Step per Trailing Stop

input group "=== ACCOUNT SAFEGUARD SETTINGS ==="
input double   InpMaxDailyLossPercent = 2.0;                                    // Max perdita giornaliera consentita (%)
input double   InpMaxDrawdownPercent = 5.0;                                     // Max drawdown totale consentito (%)

input group "=== PORTFOLIO LIMITS ==="
input int      InpMaxOpenPositions  = 5;                                       // Limite massimo posizioni simultanee aperte

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

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   // Set Magic Number for trade object
   trade.SetExpertMagicNumber(InpMagicNumber);
   
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
      FetchAndExecuteAllSignals();
   }
   
   // Update Graphic Dashboard Panel
   DrawDashboard();
}

//+------------------------------------------------------------------+
//| Fetch all signals and execute portfolio logic                     |
//+------------------------------------------------------------------+
void FetchAndExecuteAllSignals()
{
   char post[], result[];
   string result_headers;
   int timeout = 10000; // 10 seconds for full list
   
   ResetLastError();
   
   // Request the FULL list of signals (no ticker query parameter)
   int res = WebRequest("GET", InpApiUrl, NULL, NULL, timeout, post, 0, result, result_headers);
   
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
   string ticker = GetJsonValue(json_obj, "ticker");
   string raw_symbol = GetJsonValue(json_obj, "mt5_symbol");
   string symbol = ResolveMt5Symbol(ticker, raw_symbol);

   string action = GetJsonValue(json_obj, "action");
   string entry_price_str = GetJsonValue(json_obj, "entry_price");
   string stop_loss_str = GetJsonValue(json_obj, "stop_loss");
   string take_profit_str = GetJsonValue(json_obj, "take_profit");
   string reason = GetJsonValue(json_obj, "reason");
   
   double entry_price = StringToDouble(entry_price_str);
   double stop_loss = StringToDouble(stop_loss_str);
   double take_profit = StringToDouble(take_profit_str);
   
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
      if((action == "BUY" && !has_buy) || (action == "SELL" && !has_sell))
      {
         Print("[EuroQuant Multi-Bridge] Limite massimo posizioni simultanee raggiunto (", InpMaxOpenPositions, "). Ordine per ", symbol, " ignorato.");
         return;
      }
   }
   
   // Check Spread
   int spread = (int)SymbolInfoInteger(symbol, SYMBOL_SPREAD);
   if(spread > InpMaxSpreadPoints)
   {
      Print("[EuroQuant Multi-Bridge] Spread su ", symbol, " troppo alto (", spread, " punti). Ordine saltato.");
      return;
   }
   
   // Calculate lot size dynamically for this specific symbol
   double min_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double lot_step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   
   if(min_lot <= 0)
   {
      return; // Skip if volume limits can't be fetched
   }
   
   double trade_lot = min_lot * InpLotMultiplier;
   if(lot_step > 0)
   {
      trade_lot = MathRound(trade_lot / lot_step) * lot_step;
   }
   if(trade_lot < min_lot) trade_lot = min_lot;
   if(trade_lot > max_lot) trade_lot = max_lot;
   
   // Place Orders
   if(action == "BUY" && !has_buy)
   {
      double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
      if(ask <= 0) return;
      
      // Safety SL/TP bounds checks
      if(stop_loss >= ask) stop_loss = ask - 100 * point;
      if(take_profit <= ask && take_profit > 0) take_profit = ask + 200 * point;
      
      trade.Buy(trade_lot, symbol, ask, stop_loss, take_profit, "EQ Multi-Symbol BUY");
      Print("[EuroQuant Multi-Bridge] BUY ", symbol, " | Lotti: ", DoubleToString(trade_lot, 2));
      if(InpSendAlerts)
      {
         Alert("[EuroQuant Multi-Bridge] Nuova operazione BUY su ", symbol, " (Volume: ", DoubleToString(trade_lot, 2), ")");
      }
   }
   else if(action == "SELL" && !has_sell)
   {
      double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
      if(bid <= 0) return;
      
      // Safety SL/TP bounds checks
      if(stop_loss <= bid && stop_loss > 0) stop_loss = bid + 100 * point;
      if(take_profit >= bid) take_profit = bid - 200 * point;
      
      trade.Sell(trade_lot, symbol, bid, stop_loss, take_profit, "EQ Multi-Symbol SELL");
      Print("[EuroQuant Multi-Bridge] SELL ", symbol, " | Lotti: ", DoubleToString(trade_lot, 2));
      if(InpSendAlerts)
      {
         Alert("[EuroQuant Multi-Bridge] Nuova operazione SELL su ", symbol, " (Volume: ", DoubleToString(trade_lot, 2), ")");
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
   
   DrawRow(prefix + "R1", "EUROQUANT PORTFOLIO-BRIDGE", x_start + 15, y_start + 10, C'255, 120, 0', 9, true);
   
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
   
   int pos_count = GetTotalOpenPositions();
   DrawRow(prefix + "R5", "Posizioni EA: " + IntegerToString(pos_count) + " / " + IntegerToString(InpMaxOpenPositions), x_start + 15, y_start + 90, C'200, 200, 200', 8, false);
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
