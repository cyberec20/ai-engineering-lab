//+------------------------------------------------------------------+
//| S6_MCP_PushEA.mq5                                                |
//| Pushes MT5 market data on each NEW BAR (default M1) to local API |
//| Uses WebRequest POST /mt5/push with header X-MT5-Token            |
//+------------------------------------------------------------------+
#property strict
#property description "Session6 MCP: Push new-bar snapshot to local server via WebRequest."
#property version   "1.01"

input string InpHost            = "127.0.0.1";
input int    InpPort            = 8100;
input string InpEndpointPath    = "/mt5/push";
input string InpToken           = "";          // Put MT5_SHARED_SECRET here (must match .env)
input ENUM_TIMEFRAMES InpTF     = PERIOD_M1;   // v1: M1
input bool   InpSendLastClosed  = true;        // Send OHLC of last CLOSED candle (shift=1)
input int    InpTimeoutMs       = 3000;
input bool   InpVerboseLogs     = true;

datetime g_lastBarTime = 0;

// Minimal JSON escape (only backslash and quote)
string JsonEscape(const string s)
{
   string out = s;
   // StringReplace modifies 'out' in-place and returns count (int)
   StringReplace(out, "\\", "\\\\");
   StringReplace(out, "\"", "\\\"");
   return out;
}

bool IsNewBar()
{
   datetime t0 = iTime(_Symbol, InpTF, 0);
   if(t0 <= 0) return false;

   if(g_lastBarTime == 0)
   {
      g_lastBarTime = t0;
      return false; // first tick initializes
   }

   if(t0 != g_lastBarTime)
   {
      g_lastBarTime = t0;
      return true;
   }
   return false;
}

bool HttpPostJson(const string url, const string jsonBody, const string token, int timeoutMs)
{
   char post[];
   int bodyLen = StringLen(jsonBody);
   ArrayResize(post, bodyLen);
   StringToCharArray(jsonBody, post, 0, bodyLen, CP_UTF8);

   string headers = "Content-Type: application/json\r\n";
   if(token != "")
      headers += "X-MT5-Token: " + token + "\r\n";

   char result[];
   string result_headers;

   ResetLastError();
   int status = WebRequest("POST", url, headers, timeoutMs, post, result, result_headers);
   int err = GetLastError();

   if(status == -1)
   {
      if(InpVerboseLogs)
      {
         // ErrorDescription() not available by default; keep it simple and compile-safe
         Print("S6_MCP_PushEA WebRequest failed. GetLastError()=", err,
               ". Check: Tools->Options->Expert Advisors->Allow WebRequest for listed URL.");
      }
      return false;
   }

   if(InpVerboseLogs)
   {
      string body = CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8);
      Print("S6_MCP_PushEA POST ", url, " -> HTTP ", status, " resp=", body);
   }

   return (status >= 200 && status < 300);
}

void OnInit()
{
   if(InpVerboseLogs)
      Print("S6_MCP_PushEA init. Symbol=", _Symbol,
            " TF=", EnumToString(InpTF),
            " Host=", InpHost,
            " Port=", InpPort,
            " Endpoint=", InpEndpointPath);

   g_lastBarTime = iTime(_Symbol, InpTF, 0);
}

void OnDeinit(const int reason)
{
   if(InpVerboseLogs)
      Print("S6_MCP_PushEA deinit. reason=", reason);
}

void OnTick()
{
   if(!IsNewBar()) return;

   int shift = InpSendLastClosed ? 1 : 0;

   double bid = 0.0, ask = 0.0;
   SymbolInfoDouble(_Symbol, SYMBOL_BID, bid);
   SymbolInfoDouble(_Symbol, SYMBOL_ASK, ask);

   double o = iOpen(_Symbol, InpTF, shift);
   double h = iHigh(_Symbol, InpTF, shift);
   double l = iLow(_Symbol, InpTF, shift);
   double c = iClose(_Symbol, InpTF, shift);

   datetime ts = iTime(_Symbol, InpTF, shift);
   if(ts <= 0) ts = TimeCurrent();

   string symbol = _Symbol;
   string tfStr  = EnumToString(InpTF); // "PERIOD_M1", etc.
   // Normalize timeframe string (remove "PERIOD_")
   if(StringFind(tfStr, "PERIOD_") == 0)
      tfStr = StringSubstr(tfStr, 7);

   string tsIso = TimeToString(ts, TIME_DATE|TIME_SECONDS);
   StringReplace(tsIso, ".", "-");
   int spacePos = StringFind(tsIso, " ");
   if(spacePos >= 0)
      tsIso = StringSubstr(tsIso, 0, spacePos) + "T" + StringSubstr(tsIso, spacePos + 1);
   tsIso += "Z";

   string url = "http://" + InpHost + ":" + (string)InpPort + InpEndpointPath;

   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

   string json =
      "{"
      "\"source\":\"mt5_ea\","
      "\"symbol\":\"" + JsonEscape(symbol) + "\","
      "\"timeframe\":\"" + JsonEscape(tfStr) + "\","
      "\"ts\":\"" + JsonEscape(tsIso) + "\","
      "\"bid\":" + DoubleToString(bid, digits) + ","
      "\"ask\":" + DoubleToString(ask, digits) + ","
      "\"ohlc\":{"
         "\"open\":"  + DoubleToString(o, digits) + ","
         "\"high\":"  + DoubleToString(h, digits) + ","
         "\"low\":"   + DoubleToString(l, digits) + ","
         "\"close\":" + DoubleToString(c, digits) +
      "}"
      "}";

   if(InpToken == "")
   {
      Print("S6_MCP_PushEA: InpToken is empty. Set it to MT5_SHARED_SECRET (same as .env).");
      return;
   }

   HttpPostJson(url, json, InpToken, InpTimeoutMs);
}
