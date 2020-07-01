# weeWX
#
# Author: Jet 2020
# based on HTML.py example
#
#
"""
<plugin key="weeWX" name="weeWX" author="Jet" version="0.1" externallink="">
    <description>
    </description>
    <params>
        <param field="Address" label="IP Address" width="200px" required="true"/>
        <param field="Port" label="Port" width="75px" default="80"/>
        <param field="Mode1" label="Polling period [s]" width="75px" default="10"/>
        <param field="Mode6" label="Debug" width="150px">
            <options>
                <option label="None" value="0"  default="true" />
                <option label="Python Only" value="2"/>
                <option label="Basic Debugging" value="62"/>
                <option label="Basic+Messages" value="126"/>
                <option label="Connections Only" value="16"/>
                <option label="Connections+Python" value="18"/>
                <option label="Connections+Queue" value="144"/>
                <option label="All" value="-1"/>
            </options>
        </param>
    </params>
</plugin>
"""
import Domoticz
import os
import re
import io
import sys
from io import StringIO
from csv import DictReader

class BasePlugin:
    httpConn = None
    runAgain = 1
    disconnectCount = 0
    
    outdoor=1
    indoor=2
    wind=3
    extraSensor=4
    nrExtraSensors=7
    rain=11
   
    def __init__(self):
        return

    def connection(self):
        Domoticz.Debug("weeWx connecting "+Parameters["Address"]+" "+Parameters["Port"])
        return Domoticz.Connection(Name="GetStatus", Transport="TCP/IP", Protocol="HTTP", Address=Parameters["Address"], Port=Parameters["Port"])
      
    def onStart(self):        
        Domoticz.Log("onStart - Plugin is starting.")
        self.period=int(Parameters["Mode1"])
        Domoticz.Heartbeat(self.period)
        if Parameters["Mode6"] != "0":
            Domoticz.Debugging(int(Parameters["Mode6"]))
            DumpConfigToLog()
#               TypeName="Temp+Hum+Baro",
        if self.outdoor not in Devices: Domoticz.Device(Name="outdoor",Unit=self.outdoor, TypeName="Temp+Hum+Baro", Used=1).Create()       
        if self.indoor not in Devices: Domoticz.Device(Name="indoor",Unit=self.indoor, TypeName="Temp+Hum", Used=1).Create()       
        if self.wind not in Devices: Domoticz.Device(Name="wind",Unit=self.wind, TypeName="Wind+Temp+Chill", Used=1).Create() 
        for nr in range(1,self.nrExtraSensors+1):
          unit=nr+self.extraSensor-1
          if unit not in Devices: Domoticz.Device(Name="extra"+str(nr),Unit=unit, TypeName="Temp+Hum", Used=1).Create()       
        if self.rain not in Devices: Domoticz.Device(Name="rain",Unit=self.rain, TypeName="Rain", Used=1).Create() 

        try:
            temp = Devices[1].TimedOut
        except AttributeError:
            self.timeoutversion = False
        else:
            self.timeoutversion = True


    def onStop(self):
        Domoticz.Log("onStop - Plugin is stopping.")

    def onConnect(self, Connection, Status, Description):
        if (Status == 0):
            sendData = { 'Verb' : 'GET',
                'URL'  : '/data.csv',
                'Headers' : { 'Accept': '*/*', \
                              'Host': Parameters["Address"]+":"+Parameters["Port"], \
                              'User-Agent':'Domoticz/1.0' }
              }
            Connection.Send(sendData)
            Domoticz.Debug("weeWx connected successfully.")
#            Connection.Send("GET /data.csv")
        else:
            Domoticz.Log("Failed to connect ("+str(Status)+") to: "+Parameters["Address"]+":"+Parameters["Mode1"]+" with error: "+Description)

    def onMessage(self, Connection, Data):
#        DumpHTTPResponseToLog(Data)
        strData = Data["Data"].decode("utf-8", "ignore")
        Status = int(Data["Status"])
        LogMessage(strData)

        if (int(Parameters["Mode6"]) & 2):
          Domoticz.Log("ON MESSAGE CALLED = "+strData)

        if (Status == 200):
            if ((self.disconnectCount & 1) == 1):
#                Domoticz.Log("Good Response received from selv, Disconnecting.")
#                self.httpConn.Disconnect()
                unused=0
            else:
#                Domoticz.Log("Good Response received from selv, Dropping connection.")
                self.httpConn = None
            self.disconnectCount = self.disconnectCount + 1
            
            with io.StringIO(strData) as read_obj: 
              csv_dict_reader = DictReader(read_obj)
              row=next(csv_dict_reader)
#temp, hum, hum_staus, pressure, forecast              
              val=str(row['outTemp'])+';'+str(row['outHumidity'])+';0;'+str(row['barometer'])+';0'
              Devices[self.outdoor].Update(0,val)
              val=str(row['inTemp'])+';'+str(row['inHumidity'])+';0'
              Devices[self.indoor].Update(0,val)
#WB;WD;WS;WG;temp;chill
              if row['windDir']=="None": wd="N"
              else: wd=["N","NE","E","SE","S","SW","W","NW"][(int(field(row,'windDir'))*2+45)/90%8]
              arr=[field(row,'windDir'),wd,field(row,'windSpeed',10),field(row,'windGust',10),field(row,'outTemp'),field(row,'windchill')]
              val=";".join(arr)
              if (int(Parameters["Mode6"]) & 2):
                Domoticz.Log("wind val = "+str(val))
#              val=str(row['windDir'])+';;'+str(10*row['windSpeed'])+';'+str(10*row['windGust'])+';'+str(row['outTemp'])+';'+str(row['windchill'])
              Devices[self.wind].Update(0,str(val))

              for nr in range(1,self.nrExtraSensors+1):
                unit=nr+self.extraSensor-1
                val=str(row['extraTemp'+str(nr)])+';'+str(row['extraHumid'+str(nr)])+';0'
                Devices[unit].Update(0,val)
#svalue=RAINRATE;RAINCOUNTER                
              Devices[self.rain].Update(0, ";".join([field(row,'hourRain',1000),field(row,'dayRain',10)])) # fixme
              
# parse result                
        elif (Status == 400):
            Domoticz.Error("weewx returned a Bad Request Error.")
        elif (Status == 500):
            Domoticz.Error("weewx returned a Server Error.")
        else:
            Domoticz.Error("weewx returned a status: "+str(Status))
             
              
              
              
    def onDisconnect(self, Connection):
        unused=0
#        Domoticz.Log("onDisconnect called for connection to: "+Connection.Address+":"+Connection.Port)

    def onHeartbeat(self):
        self.httpConn = self.connection()
        self.httpConn.Connect()

def dump(obj):
  for attr in dir(obj):
    Domoticz.Log("obj.%s = %r" % (attr, getattr(obj, attr)))
    
global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

# Generic helper functions
def LogMessage(Message):
    if Parameters["Mode6"] == "File":
        f = open(Parameters["HomeFolder"]+"http.html","w")
        f.write(Message)
        f.close()
        Domoticz.Log("File written")

def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
    return

def field(row,name,mult=1):
  val=row[name]
  if val=="None": val=0
  return str(round(mult*float(val)))
  
#def DumpHTTPResponseToLog(httpDict):
#    if isinstance(httpDict, dict):
#        Domoticz.Debug("HTTP Details ("+str(len(httpDict))+"):")
#        for x in httpDict:
#            if isinstance(httpDict[x], dict):
#                Domoticz.Debug("--->'"+x+" ("+str(len(httpDict[x]))+"):")
#                for y in httpDict[x]:
#                    Domoticz.Debug("------->'" + y + "':'" + str(httpDict[x][y]) + "'")
#            else:
#                Domoticz.Debug("--->'" + x + "':'" + str(httpDict[x]) + "'")
