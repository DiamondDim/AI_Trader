#property strict
#property script_show_inputs

input string PatternFile = "AI_Trader_patterns.json";
input color BullishColor = clrLimeGreen;
input color BearishColor = clrTomato;
input color NeutralColor = clrGold;
input bool ClearPrevious = true;

string Prefix = "AI_TRADER_PATTERN_";

int OnInit()
{
   if(ClearPrevious) DeleteObjects();
   EventSetTimer(2);
   DrawPatterns();
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}

void OnTimer()
{
   DrawPatterns();
}

void DeleteObjects()
{
   for(int i=ObjectsTotal(0)-1; i>=0; --i)
   {
      string n=ObjectName(0,i);
      if(StringFind(n,Prefix)==0) ObjectDelete(0,n);
   }
}

// The bridge intentionally uses a simple line-oriented JSON parser contract.
// Python writes one JSON object per line to the common Files directory.
void DrawPatterns()
{
   int h=FileOpen(PatternFile,FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(h==INVALID_HANDLE) return;
   if(ClearPrevious) DeleteObjects();
   while(!FileIsEnding(h))
   {
      string line=FileReadString(h);
      if(StringLen(line)<10) continue;
      // Full JSON parsing is delegated to the companion indicator/EA parser.
      // This script accepts exported object commands in the format:
      // LINE|name|time1|price1|time2|price2|color
      string parts[]; int n=StringSplit(line,'|',parts);
      if(n>=7 && parts[0]=="LINE")
      {
         string name=Prefix+parts[1];
         datetime t1=StringToTime(parts[2]); double p1=StringToDouble(parts[3]);
         datetime t2=StringToTime(parts[4]); double p2=StringToDouble(parts[5]);
         color clr=(color)StringToInteger(parts[6]);
         ObjectCreate(0,name,OBJ_TREND,0,t1,p1,t2,p2);
         ObjectSetInteger(0,name,OBJPROP_COLOR,clr);
         ObjectSetInteger(0,name,OBJPROP_RAY_RIGHT,false);
         ObjectSetInteger(0,name,OBJPROP_WIDTH,2);
      }
   }
   FileClose(h);
   ChartRedraw();
}
