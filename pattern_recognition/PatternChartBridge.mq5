#property strict
#property version "1.0"

input string CommandFile = "AI_Trader_patterns.txt";
input bool ClearPrevious = true;
input int RefreshSeconds = 2;
string Prefix = "AI_TRADER_PATTERN_";

int OnInit(){ EventSetTimer(RefreshSeconds); DrawPatterns(); return(INIT_SUCCEEDED); }
void OnDeinit(const int reason){ EventKillTimer(); }
void OnTimer(){ DrawPatterns(); }

void DeleteObjects(){
  for(int i=ObjectsTotal(0)-1;i>=0;--i){ string n=ObjectName(0,i); if(StringFind(n,Prefix)==0) ObjectDelete(0,n); }
}

void DrawPatterns(){
  int h=FileOpen(CommandFile,FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON);
  if(h==INVALID_HANDLE) return;
  if(ClearPrevious) DeleteObjects();
  int seq=0;
  while(!FileIsEnding(h)){
    string line=FileReadString(h); if(StringLen(line)<8) continue;
    string parts[]; int n=StringSplit(line,'|',parts);
    if(n>=7 && parts[0]=="LINE"){
      string name=Prefix+parts[1]+"_"+IntegerToString(seq++);
      datetime t1=StringToTime(parts[2]); double p1=StringToDouble(parts[3]);
      datetime t2=StringToTime(parts[4]); double p2=StringToDouble(parts[5]);
      color clr=(color)StringToInteger(parts[6]);
      if(ObjectCreate(0,name,OBJ_TREND,0,t1,p1,t2,p2)){
        ObjectSetInteger(0,name,OBJPROP_COLOR,clr);
        ObjectSetInteger(0,name,OBJPROP_RAY_RIGHT,false);
        ObjectSetInteger(0,name,OBJPROP_WIDTH,2);
      }
    }
  }
  FileClose(h); ChartRedraw();
}
