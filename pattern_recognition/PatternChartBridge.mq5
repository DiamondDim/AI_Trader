#property strict
#property version "1.1"

input string CommandFile = "AI_Trader_patterns.txt";
input bool ClearPrevious = true;
input int RefreshSeconds = 2;
string Prefix = "AI_TRADER_PATTERN_";

int OnInit(){
  EventSetTimer(MathMax(1, RefreshSeconds));
  DrawPatterns();
  return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason){ EventKillTimer(); }
void OnTimer(){ DrawPatterns(); }

void DeleteObjects(){
  for(int i=ObjectsTotal(0)-1;i>=0;--i){
    string n=ObjectName(0,i);
    if(StringFind(n,Prefix)==0) ObjectDelete(0,n);
  }
}

ENUM_LINE_STYLE ParseStyle(string value){
  if(value=="STYLE_DASH") return STYLE_DASH;
  if(value=="STYLE_DOT") return STYLE_DOT;
  if(value=="STYLE_DASHDOT") return STYLE_DASHDOT;
  if(value=="STYLE_DASHDOTDOT") return STYLE_DASHDOTDOT;
  return STYLE_SOLID;
}

void DrawLine(string parts[], int n, int seq){
  if(n<7) return;
  string name=Prefix+parts[1]+"_"+IntegerToString(seq);
  datetime t1=StringToTime(parts[2]); double p1=StringToDouble(parts[3]);
  datetime t2=StringToTime(parts[4]); double p2=StringToDouble(parts[5]);
  color clr=(color)StringToInteger(parts[6]);
  int width=(n>=8 ? (int)StringToInteger(parts[7]) : 1);
  ENUM_LINE_STYLE style=(n>=9 ? ParseStyle(parts[8]) : STYLE_SOLID);
  bool ray=(n>=10 && StringToLower(parts[9])=="true");

  if(ObjectCreate(0,name,OBJ_TREND,0,t1,p1,t2,p2)){
    ObjectSetInteger(0,name,OBJPROP_COLOR,clr);
    ObjectSetInteger(0,name,OBJPROP_STYLE,style);
    ObjectSetInteger(0,name,OBJPROP_WIDTH,MathMax(1,MathMin(width,5)));
    ObjectSetInteger(0,name,OBJPROP_RAY_RIGHT,ray);
    ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
    ObjectSetInteger(0,name,OBJPROP_HIDDEN,true);
  }
}

void DrawHLine(string parts[], int n, int seq){
  if(n<4) return;
  string name=Prefix+parts[1]+"_"+IntegerToString(seq);
  double price=StringToDouble(parts[2]);
  color clr=(color)StringToInteger(parts[3]);
  int width=(n>=5 ? (int)StringToInteger(parts[4]) : 1);
  ENUM_LINE_STYLE style=(n>=6 ? ParseStyle(parts[5]) : STYLE_SOLID);
  bool ray=(n>=7 && StringToLower(parts[6])=="true");

  if(ObjectCreate(0,name,OBJ_HLINE,0,0,price)){
    ObjectSetInteger(0,name,OBJPROP_COLOR,clr);
    ObjectSetInteger(0,name,OBJPROP_STYLE,style);
    ObjectSetInteger(0,name,OBJPROP_WIDTH,MathMax(1,MathMin(width,5)));
    // OBJ_HLINE is horizontal across the chart; keep ray for protocol compatibility.
    ObjectSetInteger(0,name,OBJPROP_RAY_RIGHT,ray);
    ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
    ObjectSetInteger(0,name,OBJPROP_HIDDEN,true);
  }
}

void DrawText(string parts[], int n, int seq){
  if(n<7) return;
  string name=Prefix+parts[1]+"_"+IntegerToString(seq);
  datetime t=StringToTime(parts[2]); double price=StringToDouble(parts[3]);
  string text=parts[4]; color clr=(color)StringToInteger(parts[5]);
  int size=(int)StringToInteger(parts[6]);

  if(ObjectCreate(0,name,OBJ_TEXT,0,t,price)){
    ObjectSetString(0,name,OBJPROP_TEXT,text);
    ObjectSetString(0,name,OBJPROP_FONT,"Arial");
    ObjectSetInteger(0,name,OBJPROP_FONTSIZE,MathMax(6,MathMin(size,24)));
    ObjectSetInteger(0,name,OBJPROP_COLOR,clr);
    ObjectSetInteger(0,name,OBJPROP_ANCHOR,ANCHOR_LEFT);
    ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
    ObjectSetInteger(0,name,OBJPROP_HIDDEN,true);
  }
}

void DrawPatterns(){
  int h=FileOpen(CommandFile,FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON);
  if(h==INVALID_HANDLE) return;
  if(ClearPrevious) DeleteObjects();
  int seq=0;
  while(!FileIsEnding(h)){
    string line=FileReadString(h);
    if(StringLen(line)<8) continue;
    string parts[];
    int n=StringSplit(line,'|',parts);
    if(n<=0) continue;
    if(parts[0]=="LINE") DrawLine(parts,n,seq++);
    else if(parts[0]=="HLINE") DrawHLine(parts,n,seq++);
    else if(parts[0]=="TEXT") DrawText(parts,n,seq++);
  }
  FileClose(h);
  ChartRedraw();
}
