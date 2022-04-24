import xml.etree.ElementTree as ET
from twisted.internet import reactor, protocol, task
from pymodbus.client.async import ModbusClientProtocol
import json

from klein import Klein                             # Web Framework
from twisted.web.static import File                 # Serve Files to Web
import struct                                       # Struct 4 Byte Registers
import time
from dateutil.parser import parse                  # this lib is being used to parse the string datetime from HMI


import datetime, calendar   # used currently to parse the db data into high charts only !!!

app = Klein()
class MyModbusClientFactory(protocol.ClientFactory):
    Configuration = {}
    Holding_Registers = None
    def __init__(self, Config):
        self.DeviceName = Config['DeviceName']
        self.Configuration = Config
        self.counter = 0
        self.classtest = 0
        self.write_buffer = {}
        self.ConnectionStatus = 'bad'
    def buildProtocol(self, addr):
        p = MyModbusClientProtocol()
        p.factory = self
        p.Config = self.Configuration
        return p
    def clientConnectionLost(self, connector, reason):
        print("connection lost:", reason)
        self.ConnectionStatus = 'ConnectionLost'
        connector.connect()
    def clientConnectionFailed(self, connector, reason):
        print("connection failed:", reason)
        self.ConnectionStatus = 'ConnectionFailed'
        self.Holding_Registers = None
        connector.connect()

class MyModbusClientProtocol(ModbusClientProtocol):
    Config = {}
    TcpTimeOut = 1
    Hold_ST_REG = 0
    Hold_Nu_REG = 1
    ScanRate = 0
    Registers = {}
    write_buffer_registers = {}
    def connectionMade(self):
        self.factory.ConnectionStatus = 'good'
        ModbusClientProtocol.connectionMade(self)
        MyDevice = ConfigFormatter(self.Config)
        Name = MyDevice.DeviceName()
        self.TcpTimeOut = MyDevice.TcpTimeout()
        self.NoOfWrites = MyDevice.NumberOfWrite()
        self.WrieCounter = 0
        self.Hold_Nu_REG = MyDevice.Holding_num()
        self.Hold_ST_REG = MyDevice.Holding_Start()
        self.ScanRate = MyDevice.ScanRate()
        SetRegisters = Register_list(self.Hold_ST_REG, self.Hold_Nu_REG)
        self.Registers = SetRegisters.intialize_Reg()
        print( str(Name) + ' is Connected')
        self.ExecuterList = []
        self.tempwirte = []

        self.T1 = task.LoopingCall(self.ReadCaller)
        self.T1.start(self.ScanRate)
        self.T2 = task.LoopingCall(self.WriteCaller)
        self.T2.start(0)
        self.T3 = task.LoopingCall(self.executer)
        self.T3.start(0.05)

        # self.read()

    def ReadCaller(self):
        self.ExecuterList.append('read')
    def WriteCaller(self):
        if (len(self.factory.write_buffer) != 0):
            if (self.factory.write_buffer) != self.tempwirte:
                self.ExecuterList.append('write')
                self.tempwirte = self.factory.write_buffer
    def StopExecuter(self):
        self.T3.stop()
    def executer(self):
        if len(self.ExecuterList) > 0:
            if self.factory.ConnectionStatus == 'good' :
                method_name = self.ExecuterList[0]
                del self.ExecuterList[0]
                method = None
                method = getattr(self, method_name)
                method()
            else:
                self.StopExecuter()


    def read(self):
        # self.timeout = reactor.callLater(self.TcpTimeOut, self.transport.abortConnection)
        self.timeout = reactor.callLater(0.5, self.StopExecuter)
        rr = self.read_holding_registers(self.Hold_ST_REG, self.Hold_Nu_REG)  # ( Start Register , Number of Registers )
        rr.addCallbacks(self.requestFetched, self.requestNotFetched)
        self.timeout.cancel()

    def write(self):
        # self.timeout = reactor.callLater(self.TcpTimeOut, self.transport.abortConnection)
        for each in self.factory.write_buffer:
            if type(self.factory.write_buffer[each]) is list:
                self.write_registers(self.spliter(each),self.factory.write_buffer[each])  # ( Starting Registers Number , Values as list )
                self.WrieCounter = self.WrieCounter + 1
                self.factory.write_buffer[each] = "None"
                self.factory.write_buffer = {key: value for key, value in self.factory.write_buffer.items() if
                                             value != "None"}
            else:
                if self.factory.write_buffer[each] != "None":
                    deferred = self.write_register(self.spliter(each),int(self.factory.write_buffer[each]))  # ( Register Number , Value )
                    self.WrieCounter = self.WrieCounter + 1
                    self.factory.write_buffer[each] = "None"
                    self.factory.write_buffer = {key: value for key, value in self.factory.write_buffer.items() if value != "None"}
            if self.WrieCounter >= self.NoOfWrites:
                self.WrieCounter = 0
                break
        # self.timeout.cancel()
        # reactor.callLater(self.ScanRate, self.read)


    def writeRegisters(self):
        self.write_registers()
        pass

    def spliter(self, String):
        String = String.split('R')
        String = int(String[1])
        return String

    def requestNotFetched(self, error):
        print(error)
    def requestFetched(self, response):
        try:
            # self.timeout.cancel()
            bit = 0
            for each in self.Registers:
                bit =  int(self.spliter(each))
                self.Registers[each] = response.getRegister(bit)

        except:
            print("Fetched %d" % response.getBit(0))
        self.factory.counter += 1
        self.factory.Holding_Registers = self.Registers
        if self.factory.counter == 1:
            self.factory.counter = 0
            # if (len(self.factory.write_buffer) == 0):
            #     reactor.callLater(self.ScanRate , self.read)
            # else:
            #     reactor.callLater(0, self.write)


class ConfigFormatter():
    Conf = {}
    def __init__(self, Config):
        self.Conf = Config
    def GetIP(self):
        IP = self.Conf['Network']['IP']
        return IP
    def TcpTimeout(self):
        Timeout = int(self.Conf['MODBUS']['TCPTIMEOUT'])
        return Timeout
    def NumberOfWrite(self):
        NumberWrites = int(self.Conf['MODBUS']['NoOfWrite'])
        return NumberWrites
    def Holding_Start(self):
        Start = int(self.Conf['REGISTERS']['HoldingRegisters']['Start'])
        return Start
    def Holding_num(self):
        Start = int(self.Conf['REGISTERS']['HoldingRegisters']['Start'])
        End = int(self.Conf['REGISTERS']['HoldingRegisters']['End'])
        return (End - Start)
    def ScanRate(self):
        Scan = float(self.Conf['MODBUS']['SCANRATE'])
        return Scan
    def DeviceName(self):
        Name = self.Conf['DeviceName']
        return Name

class Register_list():
    Start_Reg = None
    Num_Reg = None
    def __init__(self, Start_Reg, Num_Reg):
        self.Start_Reg = Start_Reg
        self.Num_Reg = Num_Reg
    def intialize_Reg(self):
        Registers = {}
        for each in range(self.Start_Reg, self.Num_Reg):
            if each < 10 :
                key = 'R00' + str(each)
                Registers[key] = None
            if (each < 100 and each > 10 ) :
                key = 'R0' + str(each)
                Registers[key] = None
            if each > 99 :
                key = 'R' + str(each)
                Registers[key] = None
        return Registers

class XmlListConfig(list):
    def __init__(self, aList):
        for element in aList:
            if element:
                # treat like dict
                if len(element) == 1 or element[0].tag != element[1].tag:
                    self.append(XmlDictConfig(element))
                # treat like list
                elif element[0].tag == element[1].tag:
                    self.append(XmlListConfig(element))
            elif element.text:
                text = element.text.strip()
                if text:
                    self.append(text)

class UpdateHandler():
    def __init__(self, Taglist, Instances):
        self.Taglist = Taglist
        self.Instances = Instances
        self.temp1 = 0

    def initialize_outputlist(self):
        self.outputlist = {}
        Devices = self.Taglist
        prepare = {'OutputTags': {}}
        for each in Devices:
            if (Devices[each]['Type'] == 'Output'):
                temp = {each : {'Value': Devices[each]['Value']}}
                prepare['OutputTags'].update(temp)
        self.outputlist = prepare

    def AssignSource(self):
        for each in self.Taglist:
            for every in range(1, (len(self.Instances))):
                Device = Instances[every].DeviceName
                if Device == self.Taglist[each]['Source']:
                    temp = {'DeviceID': every}
                    self.Taglist[each].update(temp)
    def AssignKeys(self):
        for each in self.Taglist:
            keys = []
            start = int(self.Taglist[each]['StartReg'])
            until = int(self.Taglist[each]['StartReg'])+ int(self.Taglist[each]['NumReg'])
            for st in range(start, until):
                if st < 10:
                    key = 'R00' + str(st)
                    keys.append(key)
                if (st < 100 and st > 10):
                    key = 'R0' + str(st)
                    keys.append(key)
                if st > 99:
                    key = 'R' + str(st)
                    keys.append(key)
            self.Taglist[each]['keys'] = keys
    def Start(self):
       self.l1 = task.LoopingCall(self.Handler)
       self.l1.start(0.1)
    def Stop(self):
        self.l1.stop()
    def UpdateTagList(self):
        pass
    def Handler(self):
        for each in self.Taglist:
            if (self.Taglist[each]['Type'] == 'Input'):
                if (int(self.Taglist[each]['NumReg']) == 1):
                    try:
                        self.Taglist[each]['Value'] = Instances[self.Taglist[each]['DeviceID']].Holding_Registers[TagsList[each]['keys'][0]]
                        self.Taglist[each]['Status'] = 128
                    except:
                        self.Taglist[each]['Status'] = 0

                if (int(self.Taglist[each]['NumReg']) == 4):
                    try:
                        Byte1 = Instances[self.Taglist[each]['DeviceID']].Holding_Registers[TagsList[each]['keys'][0]]
                        Byte1 = Byte1 - 2 ** 16 if Byte1 & 2 ** 15 else Byte1
                        Byte2 = Instances[self.Taglist[each]['DeviceID']].Holding_Registers[TagsList[each]['keys'][1]]
                        Byte2 = Byte2 - 2 ** 16 if Byte2 & 2 ** 15 else Byte2
                        Byte3 = Instances[self.Taglist[each]['DeviceID']].Holding_Registers[TagsList[each]['keys'][2]]
                        Byte3 = Byte3 - 2 ** 16 if Byte3 & 2 ** 15 else Byte3
                        Byte4 = Instances[self.Taglist[each]['DeviceID']].Holding_Registers[TagsList[each]['keys'][3]]
                        Byte4 = Byte4 - 2 ** 16 if Byte4 & 2 ** 15 else Byte4
                        data = [Byte1, Byte2, Byte3, Byte4]
                        data1 = struct.unpack('<f', struct.pack('4b', *data))[0]
                        self.Taglist[each]['Value']= format(data1, '.2f')
                        self.Taglist[each]['Status'] = 128
                    except:
                        self.Taglist[each]['Status'] = 0
            if (self.Taglist[each]['Type'] == 'Output'):
                pass


    def UpdateTagValue(self, Tag, Value):              # Returns True if Successfull
        if Tag not in self.Taglist:
            print (Tag, ' tag is not located in Global System Tag list')
            return False
        elif Tag in self.Taglist:
            if len(self.Taglist[Tag]['keys']) == 1:
                TagsUpdate.Taglist[Tag]['Value'] = int(Value)
                DeviceID = int(self.Taglist[Tag]['DeviceID'])
                if Instances[DeviceID].ConnectionStatus == 'good':
                    if (int(self.Taglist[Tag]['Value']) != int(self.outputlist['OutputTags'][Tag]['Value'])):
                        key = self.Taglist[Tag]['keys'][0]
                        value = self.Taglist[Tag]['Value']
                        dict = {key: value}
                        Instances[DeviceID].write_buffer.update(dict)
                        self.outputlist['OutputTags'][Tag]['Value'] = value
                        self.temp1 = 0
                else:
                    if self.temp1 == 0:
                        self.temp1 = 1
                        for net in self.Taglist:
                            if ( self.Taglist[net]['Type'] == 'Output' and self.Taglist[net]['DeviceID'] == DeviceID ):
                                self.outputlist['OutputTags'][net]['Value'] = -999
            else:
                DeviceID = int(self.Taglist[Tag]['DeviceID'])
                key = 'FunctionCode16'
                key = self.Taglist[Tag]['keys'][0]
                dict = {key: Value}
                # print(self.Taglist[Tag]['Value'])
                # print(self.outputlist['OutputTags'][Tag]['Value'])
                TagsUpdate.Taglist[Tag]['Value'] = Value
                if (self.Taglist[Tag]['Value'] != (self.outputlist['OutputTags'][Tag]['Value'])):
                    if Instances[DeviceID].ConnectionStatus == 'good':
                        Instances[DeviceID].write_buffer.update(dict)
                        self.outputlist['OutputTags'][Tag]['Value'] = Value
                    elif Instances[DeviceID].ConnectionStatus == 'bad':
                        pass
                    else:
                        pass
            return True
    def UpdateRegistersValue(self, RegistersListPack):
        temp = RegistersListPack.keys()
        temp = list(temp)
        tag = temp[0]
        DeviceID = int(self.Taglist[tag]['DeviceID'])
        key = 'FunctionCode6'
        pass

    def init_historian(self):
        self.HisList = []
        for each in self.Taglist:
            if self.Taglist[each]['HIS'] == 'ENABLED':
                self.HisList.append(each)
        import MySQLdb
        try:
            self.db = MySQLdb.connect('localhost', 'root', 'raspberry', 'MAIN')
            self.curs = self.db.cursor()
            return True
        except:
            print('Failed to Connect to MySQL Database')
            return False

    def Start_His(self):
        self.Process = []
        for each in self.HisList:
            Sample_Rate = int(self.Taglist[each]['HIS_SR'])
            self.Process.append(task.LoopingCall(self.his_collector, each))
            self.Process[-1].start(Sample_Rate)
    def Stop_His(self):
        for each in self.Process:
            self.Process[each].stop()

    def his_collector(self, His_Tag):
        TEXT = str("INSERT INTO tempdat(tdate, ttime, zone, Value) VALUES(CURRENT_DATE(), NOW(), '{0}', {1});".format(str(His_Tag), str(self.Taglist[His_Tag]['Value'])))
        try:
            self.curs.execute(TEXT)
            self.db.commit()
        except:
            print('Error writing {0} to the Historian Server'.format(His_Tag))

class XmlDictConfig(dict):
    '''
    And then use xmldict for what it is... a dict.
    '''
   # NumberOfDevices = 0
    def __init__(self, parent_element):
        if parent_element.items():
            self.update(dict(parent_element.items()))
        for element in parent_element:
            if element:
                # treat like dict - we assume that if the first two tags
                # in a series are different, then they are all different.
                if len(element) == 1 or element[0].tag != element[1].tag:
                    aDict = XmlDictConfig(element)
                # treat like list - we assume that if the first two tags
                # in a series are the same, then the rest are the same.
                else:
                    # here, we put the list in dictionary; the key is the
                    # tag name the list elements all share in common, and
                    # the value is the list itself
                    aDict = {element[0].tag: XmlListConfig(element)}
                # if the tag has attributes, add those to the dict
                if element.items():
                    aDict.update(dict(element.items()))
                self.update({element.tag: aDict})
            # this assumes that if you've got an attribute in a tag,
            # you won't be having any text. This may or may not be a
            # good idea -- time will tell. It works for the way we are
            # currently doing XML configuration files...
            elif element.items():
                self.update({element.tag: dict(element.items())})
            # finally, if there are no child tags and no attributes, extract
            # the text
            else:
                self.update({element.tag: element.text})



class TagProcessor():
    def __init__(self):
        pass
    def ProcessXML(self, XML):
        Tags = {}
        for each in XML['ControlNetwork']:
            exclude = []
            try:
                for every in XML['ControlNetwork'][each]['TAGS']:
                    temp = {every : {'Value': XML['ControlNetwork'][each]['TAGS'][every]['Value'],
                                     'StartReg': XML['ControlNetwork'][each]['TAGS'][every]['StartReg'],
                                     'NumReg': XML['ControlNetwork'][each]['TAGS'][every]['NumReg'],
                                     'Source': XML['ControlNetwork'][each]['DeviceName'],
                                     'Type': XML['ControlNetwork'][each]['TAGS'][every]['Type'],
                                     'HIS': XML['ControlNetwork'][each]['TAGS'][every]['HIS'],
                                     'HIS_SR': XML['ControlNetwork'][each]['TAGS'][every]['HIS_SR']}}
                    Tags.update(temp)
            except:
                pass
        return Tags

class softtags_handler():
    def __init__(self, SoftTags):
        self.SoftTagsList = SoftTags
        import os
        if os.name == 'posix':
            self.Path = '/home/pi/Project/TestFolder'
        else:
            self.Path = 'TestFolder'
        if not (os.path.exists(self.Path + '/SoftTags.txt')):
            temp = self.Path + '/SoftTags.txt'
            with open(temp, 'w') as file:
                file.write(json.dumps(self.SoftTagsList))
        else:
            with open(self.Path + '/SoftTags.txt', 'r') as f:
                s = f.read()
                xx = json.loads(s)
                self.SoftTagsList = xx
        self.l2 = task.LoopingCall(self.RuntimeValues)
        self.l2.start(1800)
        # self.l2.start(10)

    def RuntimeValues(self):
        temp = self.Path + '/SoftTags.txt'
        with open(temp, 'w') as file:
            file.write(json.dumps(self.SoftTagsList))

    def UpdateSoftTag(self, SoftTag, Value):
        if SoftTag in self.SoftTagsList:
            self.SoftTagsList[SoftTag]['Value'] = Value
            # temp = {SoftTag : Value}
            # self.SoftTagsList.update(temp)

        else:
            print('The Soft Tag is not existed in the global tag list')
    def Processing(self, Received):
        self.templist = {}
        for every in Received:
            if every not in self.SoftTagsList:
                print('{0} is not included in the global soft tag'.format(every))
            else:
                self.templist.update(Received[every])
        return self.templist


class Control_Builder():
    def __init__(self, CM_Details, TagsUpdate, SoftTagUpdate):
        # Read and Parse the xml file for modules
        # create a list of all modules instances and for each
        # Control Module create instances of function and set
        # the execution order the block    = [ { CM_Name1 : { block1: { Ex_Order : 1, Parm1 : 0 }, block2 : { Ex_Order : 1, Parm1 : 0 }  } ]
        # Builder the Module
        #
        # CM_Details = { 'CM_Name1' : {'AI1' : { 'Type' : 'AI', 'Ex_Order' : 1, 'Parm1' : 0, 'IO_IN' : 'E1_TEST3' , 'Input_Ref' : None}, \
        #                              'AO1' : { 'Type' : 'AO', 'Ex_Order' : 1, 'Parm1' : 0, 'IO_IN' : 'E1_TEST1', 'Input_Ref' : {'IN1_cv' : {'AI1': 'out_cv'}} } }}

        # print (TagsUpdate.Taglist)
        self.XML_Modules = []
        self.ListModules = {}
        self.ExeModules = {}
        self.ExeModules_Inst = {}
        self.SoftTagUpdate = SoftTagUpdate
        import os
        if os.name == 'posix':
            self.Path = '/home/pi/Project/TestFolder'
        else:
            self.Path = 'TestFolder'
        if os.path.exists(self.Path):
            pass
        else:
            os.makedirs('TestFolder')

        for every in CM_Details:
            self.CM_Name = every
            self.blocks = CM_Details[every]
            self.tempbl = {}
            self.tempp2 = len(self.blocks )
            for every2 in range(1, self.tempp2 +1):
                for FNBLOCK in self.blocks:
                    if int(self.blocks[FNBLOCK]['Ex_Order']) == every2:
                        oo = {FNBLOCK : self.blocks[FNBLOCK]}
                        self.tempbl.update(oo)
            # print('order dict : ' , self.tempbl)
            self.XML_Modules.append(self.blocks)
            self.temp = ({every : self.tempbl})
            self.ListModules.update(self.temp)
        self.block_oj = {}
        # create an instance of each function block
        self.Control_Modules = []
        for each in self.ListModules:
            self.block_oj = {}
            for every in self.ListModules[each]:
                # create instance of each one
                self.temp = {}
                if self.ListModules[each][every]['Type'] == 'Softy':
                    Object = Softparmeter(self.ListModules[each][every], SoftTagUpdate)
                else:
                    Object = function_blocks(every, self.ListModules[each][every], TagsUpdate, SoftTagUpdate)
                self.temp = {every : Object}
                self.block_oj.update(self.temp)
            self.Control_Modules.append(self.block_oj)
            self.temp1 = { each : self.block_oj}
            if not (os.path.exists(self.Path + '/' + str(each) + '.txt')):
                pass
            else:
                with open(self.Path + '/' + str(each) + '.txt', 'r') as f:
                    s = f.read()
                    xx = json.loads(s)
                    for fb in self.temp1[each]:
                        self.temp1[each][fb].Parameters = xx[fb]
            self.ExeModules.update(self.temp1)
        # print(self.ExeModules)
    def run(self):
        for eavery in self.ExeModules:
            self.temp = Module(self.ExeModules[eavery], eavery, self.SoftTagUpdate)
            self.temp1 = {eavery : self.temp}
            self.ExeModules_Inst.update(self.temp1)
        self.executing()
    def stop(self):
        self.l1.stop()
    def executing(self):
        for every in self.ExeModules_Inst:
            self.ExeModules_Inst[every].Run()

class Module():
    def __init__(self, Functions, ModuleName, SoftTagUpdate):
        self.Functions = Functions
        self.ModuleName = ModuleName
        self.RuntimeValues()
        self.SoftTagUpdate = SoftTagUpdate
        self.NumFun = len(Functions)
        self.Count = 0
        self.execut = []
        self.exeRef = {}
        for exec1 in range(1, self.NumFun + 1):
            for FNBLOCK in self.Functions:
                temp11 = self.Functions[FNBLOCK].InputUpdate()
                if int(temp11['Ex_Order']) == exec1:
                    self.execut.append(self.Functions[FNBLOCK])
                    tt = {FNBLOCK : exec1 }
                    self.exeRef.update(tt)
    def __str__(self):
        return str(self.ModuleName)
    def Run(self):
        print('Start Executing', self.ModuleName,'/', self.execut)
        self.l1 = task.LoopingCall(self.Execute)
        self.l2 = task.LoopingCall(self.RuntimeValues)
        self.l1.start(0)
        self.l2.start(1800)
        # self.l2.start(10)
    def Execute(self):
        for every in self.execut:
            indx = self.execut.index(every)
            temp0 = self.execut[indx].InputUpdate()
            if temp0['Input_Ref'] == None:
                self.execut[indx].run()
            else:
                for peace in temp0['Input_Ref']:
                    temp = temp0['Input_Ref'][peace]
                    for each_ref in temp:
                        if each_ref != 'Soft':
                            inst = self.execut[(self.exeRef[each_ref] - 1)]
                            exec("self.execut[indx].%s = inst.%s" % (peace, temp[each_ref]))
                        else:
                            exec("self.execut[indx].%s = self.SoftTagUpdate.SoftTagsList['%s']['Value']" % (peace, temp[each_ref]))
                self.execut[indx].run()

    def RuntimeValues(self):
        tempy = {}
        for every in self.Functions:
            key = every
            value = self.Functions[every].Parameters
            temp = {key : value}
            tempy.update(temp)
        import os
        if os.name == 'posix':
            self.Path = '/home/pi/Project/TestFolder'
        else:
            self.Path = 'TestFolder'
        # if not (os.path.exists(self.Path + '/' + str(self.ModuleName) + '.txt')):
        # print('saving module')
        temp = self.Path + '/' + str(self.ModuleName) + '.txt'
        with open(temp, 'w') as file:
            file.write(json.dumps(tempy))

class Softparmeter():
    def __init__(self, Soft_prm, SoftTagsUpdate):
        self.IN1_cv = 0
        self.SoftTagsUpdate = SoftTagsUpdate
        self.Parameters = Soft_prm
        self.Tag = Soft_prm['IO_IN']
        pass
    def __str__(self):
        return str(self.Tag)
    def __repr__(self):
        return str(self.Tag)
    def run(self):
        self.SoftTagsUpdate.UpdateSoftTag(self.Tag, self.IN1_cv)
        pass
    def InputUpdate(self):
        return self.Parameters


class function_blocks():
    def __init__(self, FB_Name, FB_Parm, IO, SoftTagsUpdate):
        self.out_cv = 0
        self.out1_cv = 0
        self.out_st = 0
        self.IN1_cv = 0
        self.IN2_cv = 0
        self.IN3_cv = 0
        self.IN4_cv = 0
        self.IN1_st = 0
        self.output = IO
        self.IO1 = IO.Taglist
        self.Funcion_Name = FB_Name
        self.Parameters = FB_Parm
        self.temp1 = 0
        self.temp2 = 0
        self.SoftTagsUpdate = SoftTagsUpdate
        # print(self.Parameters)
        if self.Parameters['Type'] == 'AI':
            self.Tag = self.Parameters['IO_IN']
        if self.Parameters['Type'] == 'AO':
            self.Tag = self.Parameters['IO_IN']
    def __str__(self):
        return str(self.Funcion_Name)
    def __repr__(self):
        return str(self.Funcion_Name)
    def AI(self):
        self.Parameters['OUT_D'] = self.IO1[self.Tag]['Value']
        self.out_st = self.IO1[self.Tag]['Status']
        pass
    def OR(self):
        if ( int(self.IN1_cv) or int(self.IN2_cv) or int(self.IN3_cv) or int(self.IN4_cv) ) > 0:
            self.Parameters['OUT_D'] = 1
        else:
            self.Parameters['OUT_D'] = 0
    def RS(self):
        Set = int(self.IN1_cv)
        Reset = int(self.IN2_cv)
        if Set == 1 and Reset == 0:
            self.temp1 = 1
        if Reset == 1:
            self.temp1 = 0
        self.Parameters['OUT_D'] = self.temp1
    def AND(self):
        if ( int(self.IN1_cv) and int(self.IN2_cv)) > 0:
            self.Parameters['OUT_D'] = 1
        else:
            self.Parameters['OUT_D'] = 0
    def AO(self):
        self.output.UpdateTagValue(self.Tag, self.IN1_cv)
        self.Parameters['OUT_D'] = self.IN1_cv

    def BFO(self):
        temp = int(self.IN1_cv)
        temp = "{0:b}".format(temp)
        temp = list(temp)
        temp1 = []
        for each in range((len(temp) - 1), -1, -1):
            temp1.append(temp[each])
        if (len(temp1) < 16):
            for every in range(len(temp1), 16):
                every = 0
                temp1.append(every)
        for each in range(0, 16):
            exec("self.out%d_cv = temp1[%d]" % ((each + 1), each))
    def BFI(self):
        temp = ""
        for each in range(1, 16):
            exec("temp = temp + str(self.IN%d_cv)" % (each))
    def NDE(self):
        IN = int(self.IN1_cv)
        if self.Parameters['OUT_D'] == 1 and self.temp1 == 1:
            self.Parameters['OUT_D'] = 0
            self.temp1 = 0
        if IN == 1:
            self.temp1 = 1
        if IN == 0 and self.temp1 == 1:
            self.Parameters['OUT_D'] = 1
        pass
    def OND(self):
        temp = datetime.datetime.now()
        #temp = datetime.datetime.timestamp(temp)
        temp = time.mktime(temp.timetuple())
        if (int(self.IN1_cv) >= 1 and self.temp1 == 0):
            self.temp1 = temp
        if ((temp - self.temp1) >= int(self.Parameters['Time_Duration']) and self.temp1 > 0 and int(self.IN1_cv) >= 1 ):
            self.Parameters['OUT_D'] = 1
        else:
            self.Parameters['OUT_D'] = 0
        if int(self.IN1_cv) == 0:
            self.temp1 = 0
        if int(self.IN1_cv) >= 1:
            self.Parameters['Elapsed_Time'] = temp - self.temp1
            if int(self.Parameters['Elapsed_Time']) >= int(self.Parameters['Time_Duration']) :
                self.Parameters['Elapsed_Time'] = int(self.Parameters['Time_Duration'])
    def TP(self):
        temp = datetime.datetime.now()
        #temp = datetime.datetime.timestamp(temp)
        temp = time.mktime(temp.timetuple())
        self.Parameters['IN_D'] = self.IN1_cv
        if (int(self.IN1_cv) == 0 and int(self.Parameters['OUT_D']) == 0) :
            self.temp1 = 0
            self.temp2 =0
        if (int(self.IN1_cv) >= 1 and self.temp1 == 0 and self.temp2 ==0):
            self.temp1 = temp
            self.temp2 = 1
            self.Parameters['OUT_D'] = 1
        if self.Parameters['OUT_D'] == 1 :
            self.Parameters['Elapsed_Time'] = temp - self.temp1
            if int(self.Parameters['Elapsed_Time']) >= int(self.Parameters['Time_Duration']) :
                self.Parameters['Elapsed_Time'] = int(self.Parameters['Time_Duration'])
            if (temp - self.temp1 ) >= int(self.Parameters['Time_Duration']):
                self.Parameters['OUT_D'] = 0

    def DTE_STSP(self):
        self.IN1_cv = int(self.IN1_cv)
        if int(self.Parameters['OUT_D2']) == 1:
            self.Parameters['OUT_D2'] = 0
        if int(self.Parameters['OUT_D']) == 1:
            self.Parameters['OUT_D'] = 0
        if self.IN1_cv == 1:
            st01 = parse(self.IN2_cv)
            st01 = time.mktime(st01.timetuple())
            sp01 = parse(self.IN3_cv)
            sp01 = time.mktime(sp01.timetuple())
            ct = time.time()
            if (ct > st01 and ct < st01 + 5):
                self.Parameters['OUT_D'] = 1
            if (ct > sp01 and ct < sp01 + 5):
                self.Parameters['OUT_D2'] = 1
        else:
            self.Parameters['OUT_D'] = 0
    def SP_CTRL(self):
        self.IN1_cv = int(self.IN1_cv)
        if self.IN1_cv == 1:
            if int(self.IN2_cv) != int(self.IN3_cv) :
                self.SoftTagsUpdate.UpdateSoftTag(self.Parameters['IO_IN'], int(self.IN3_cv))
    def DC(self):
        SP_Tag = self.Parameters['SP_Tag']
        if SP_Tag in self.SoftTagsUpdate.SoftTagsList:
            SP = int(self.SoftTagsUpdate.SoftTagsList[SP_Tag]['Value'])
        else:
            SP = int(self.IN3_cv)
        PV = int(self.IN1_cv)
        CAS_IN = int(self.IN2_cv)
        if SP == 0 and PV == 1:
            self.Parameters['OUT_D'] = 0
        if SP == 1 and PV == 0:
            self.Parameters['OUT_D'] = 1
        if CAS_IN == 1 and SP == 0 and PV == 0 and self.temp1 == 0:
            self.Parameters['OUT_D'] = 1
            SP = 1
            if SP_Tag in self.SoftTagsUpdate.SoftTagsList:
                self.SoftTagsUpdate.UpdateSoftTag(SP_Tag, SP)
            self.temp1 = 1
        if CAS_IN == 0 and SP == 1 and PV == 1 and self.temp1 == 1:
            self.Parameters['OUT_D'] = 0
            SP = 0
            self.temp1 = 0
            if SP_Tag in self.SoftTagsUpdate.SoftTagsList:
                self.SoftTagsUpdate.UpdateSoftTag(SP_Tag, SP)
    def MXRT(self):
        PV = int(self.IN1_cv)
        MAXTime = int(self.IN2_cv)
        ENA = int(self.IN3_cv)
        if PV == 1:
            if self.temp1 == 0 :
                self.temp2 = time.time()
                self.temp1 = 1
            if self.temp1 == 1:
                current_time = time.time()
                counter = current_time - self.temp2
                value = datetime.datetime.utcfromtimestamp(counter)
                EPLISED = value.strftime('%H:%M:%S')
                self.out1_cv = EPLISED
                if ((counter >= ( MAXTime * 60 )) and ENA == 1 ):
                    self.Parameters['OUT_D'] = 1
        if PV == 0 and self.temp1 != 0 :
            self.temp1 = 0
            self.Parameters['OUT_D'] = 0


    def run(self):
        method_name = self.Parameters['Type']  # set by the command line options
        method = None
        method = getattr(self, method_name)
        method()
    def InputUpdate(self):
        return self.Parameters




from autobahn.twisted.websocket import WebSocketServerProtocol, \
    WebSocketServerFactory

class MyServerProtocol(WebSocketServerProtocol):
    SoftTagsList = None
    def onConnect(self, request):
        pass
    def onOpen(self):
        pass
    def onMessage(self, payload, isBinary):
        message = payload.decode('utf-8')
        if message == 'Get':
            getlist = ['OnOff', 'SetPoints', 'InputBox_']
            temp = {}
            for each in self.SoftTagsList:
                if self.SoftTagsList[each]['Type'] in getlist:
                    temp1 = {each : self.SoftTagsList[each]}
                    temp.update(temp1)
            a = json.dumps(temp)
            # c = bytes(a, 'utf-8')
            c = a.encode('utf-8')
            self.sendMessage(c, isBinary)
        elif message == 'Get_FS':
            a = json.dumps(self.SoftTagsList)
            # c = bytes(a, 'utf-8')
            c = a.encode('utf-8')
            self.sendMessage(c, isBinary)
        else:
            message = json.loads(message)
            print(message)
            for each in message:
                if each in self.SoftTagsList:
                    if message[each] != None:
                        self.SoftTagsList[each]['Value'] = message[each]
                else:
                    print('The Value of This ' + str(each) + ' has been neglect it')

    def onClose(self, wasClean, code, reason):
        pass
        # print("WebSocket connection closed: {0}".format(reason))
    def Senddata(self):
        print('wo')
        # temp = b'Sarmad'
        # self.sendMessage(temp)
        pass

def checkdbifexists(file_path):
    import os.path
    if os.path.exists(file_path):
        return True
    else:
        return False


from os import name
if name == 'posix':
    Db_Path = '/home/pi/Project/Database_test.xml'
    log_Path = '/home/pi/Project/file.txt'
else:
    Db_Path = 'Database_test.xml'
    log_Path = 'file.txt'


import sys
from twisted.python import log
log.startLogging(sys.stdout)
log.startLogging(open(log_Path, 'w'))


if(checkdbifexists(Db_Path) == True):
    tree = ET.parse(Db_Path)
    root = tree.getroot()
    xmldict = XmlDictConfig(root)
    Instances = []
    Instances.append(len(xmldict['ControlNetwork']))
    for each in xmldict['ControlNetwork']:
        Instances.append(MyModbusClientFactory(xmldict['ControlNetwork'][each]))
    selector = 1
    for each in xmldict['ControlNetwork']:
        reactor.connectTCP(xmldict['ControlNetwork'][each]['Network']['IP'], int(xmldict['ControlNetwork'][each]['MODBUS']['Port']), Instances[selector])
        selector = selector + 1
    ProcessTagList = TagProcessor()
    TagsList = ProcessTagList.ProcessXML(xmldict)
    TagsUpdate = UpdateHandler(TagsList, Instances)
    TagsUpdate.initialize_outputlist()
    TagsUpdate.AssignSource()
    TagsUpdate.AssignKeys()
    TagsUpdate.Start()
    if TagsUpdate.init_historian():
        TagsUpdate.Start_His()

    for every in xmldict['ControlStratagies']:
        temp = xmldict['ControlStratagies'][every]['Control_Module']
        # print(temp)
        temp_soft = xmldict['ControlStratagies'][every]['SoftTags']
        SoftTagsUpdate = softtags_handler(temp_soft)
        # print(SoftTagsUpdate.SoftTagsList)
        print('Initializing ', every)
        a = Control_Builder(temp, TagsUpdate, SoftTagsUpdate)
        a.run()


    import random
    def printer1():
        # print(TagsUpdate.Taglist)
        b1 = Instances[1].Holding_Registers
        # TagsUpdate.UpdateTagValue('E1_LS1', random.randint(10, 100))
        TagsUpdate.UpdateTagValue('E1_LS1', [random.randint(10, 100),random.randint(10, 100)])
        # SoftTagsUpdate.UpdateSoftTag('SW_SP01', random.randint(100, 999))
        # TagsUpdate.UpdateTagValue('E1_TES', random.randint(10, 2047))
        # print('direct : ' , TagsUpdate.Taglist['E1_TEST3'])

        # print(b1)

    l2 = task.LoopingCall(printer1)
    # l2.start(0.25)

    # import rethinkdb as r
    # from twisted.internet.defer import inlineCallbacks
    # class redblist():
    #     def __init__(self):
    #         r.connect("localhost", 28015).repl()
    #
    #
    #     def ret(self, tags, softtags):
    #         for every in softtags:
    #             temp = { 'Tag' : every, 'Value':softtags[every]}
    #             r.table("authors").insert(temp).run()
    #
    #
    #     def listen(self):
    #         cursor = r.table("authors").changes().run()
    #         for document in cursor:
    #             print(document)

    #
    # db = redblist()
    # db.ret(TagsUpdate.Taglist, SoftTagsUpdate.SoftTagsList)
    # db.listen()




    @app.route('/')
    def Home_Page(request):
        if name == 'posix':
            #file = File('/home/pi/Project/index.html')
            file = File('/home/pi/Project/ChartBuilder.html')
        else:
            file = File('index.html')
        file.isLeaf = True
        return file


    @app.route('/Get_Values')
    def Get_Values(request):
        return json.dumps(SoftTagsUpdate.SoftTagsList)

    @app.route('/ChartBuilder/')
    def ChartBuilder(request):
        if name == 'posix':
            file = File('/home/pi/Project/ChartBuilder.html')
        else:
            file = File('ChartBuilder.html')
        file.isLeaf = True
        return file
    @app.route('/charts4/')
    def Chart_1(request):
        if name == 'posix':
            file = File('/home/pi/Project/charts4.html')
        else:
            file = File('charts4.html')
        file.isLeaf = True
        return file
    @app.route('/charts5/')
    def Chart_2(request):
        if name == 'posix':
            file = File('/home/pi/Project/charts5.html')
        else:
            file = File('charts5.html')
        file.isLeaf = True
        return file
    @app.route('/chartdata/<string:name>')    # {'Start': '2017-12-02T12:13', 'End': '2017-12-05T12:31'}
    def data_5(request,  name='world'):       # you have to send in the above format to get the readings
        content = json.loads(name)
        print(content)
        Start = content['Start']
        Start = Start.split('T')
        print(Start)
        StartDate = Start[0]
        StartDate = unicode(StartDate)
        StartTime = Start[1]
        End = content['End']
        End = End.split('T')
        EndDate = End[0]
        EndDate = unicode(EndDate)
        EndTime = End[1]
        print (StartDate, EndDate)
        Command = "SELECT * FROM tempdat WHERE tdate >= '{0}' AND tdate <= '{1}' AND zone = 'E1_TT1';".format(StartDate, EndDate)
        print(Command)
      #  Command = 'SELECT * FROM tempdat WHERE zone = "E1_TT1" ;'
        try:
            chartlist = []
            TagsUpdate.curs.execute(Command)
            for each in TagsUpdate.curs.fetchall():
                temp = []
                t1 = each[1]
                tf = (datetime.datetime.min + t1).time()
                d1 = each[0]
                dt = datetime.datetime.combine(d1, tf)
                dts = calendar.timegm(dt.utctimetuple())*1000 + dt.microsecond * 0.0011383651
                temp.append(dts)
                temp.append(float(each[3]))
                chartlist.append(temp)
            test = json.loads(str(chartlist))
            return json.dumps(test)
        except:
            Error = {'Error': 32}
            return json.dumps(Error)
    @app.route('/chartdata2/<string:name>')    # {'Start': '2017-12-02T12:13', 'End': '2017-12-05T12:31'}
    def data_1(request,  name='world'):       # you have to send in the above format to get the readings
        content = json.loads(name)
        print(content)
        Start = content['Start']
        Start = Start.split('T')
        print(Start)
        StartDate = Start[0]
        StartDate = unicode(StartDate)
        StartTime = Start[1]
        End = content['End']
        End = End.split('T')
        EndDate = End[0]
        EndDate = unicode(EndDate)
        EndTime = End[1]
        print (StartDate, EndDate)
        Command = "SELECT * FROM tempdat WHERE tdate >= '{0}' AND tdate <= '{1}' AND zone = 'E1_HT1';".format(StartDate, EndDate)
        print(Command)
      #  Command = 'SELECT * FROM tempdat ;'
        try:
            chartlist = []
            TagsUpdate.curs.execute(Command)
            for each in TagsUpdate.curs.fetchall():
                temp = []
                t1 = each[1]
                tf = (datetime.datetime.min + t1).time()
                d1 = each[0]
                dt = datetime.datetime.combine(d1, tf)
                dts = calendar.timegm(dt.utctimetuple())*1000 + dt.microsecond * 0.0011383651
                temp.append(dts)
                temp.append(float(each[3]))
                chartlist.append(temp)
            test = json.loads(str(chartlist))
            return json.dumps(test)
        except:
            Error = {'Error': 32}
            return json.dumps(Error)
    @app.route('/socket/')
    def Test1(request):
        if name == 'posix':
            file = File('/home/pi/Project/websocket.html')
        else:
            file = File('websocket.html')
        file.isLeaf = True
        return file
    @app.route('/Devices/')
    def Test1(request):
        if name == 'posix':
            file = File('/home/pi/Project/ConnectDevices.html')
        else:
            file = File('ConnectDevices.html')
        file.isLeaf = True
        return file
    @app.route('/Random/')
    def Test2(request):
        b = Instances[1].Holding_Registers['R004']
        c = TagsUpdate.Taglist['E1_TT1']['Value']
        return json.dumps(c)
    @app.route('/static/', branch=True)
    def static(request):
        if name == 'posix':
            return File("./home/pi/Project//static")
        else:
            return File("./static/")

    # /var/lib/misc/dnsmasq.leases
    if name == 'posix':
        DNSMASQ_LEASES_FILE = "/var/lib/misc/dnsmasq.leases"
    else:
        DNSMASQ_LEASES_FILE = "dnsmasq.leases"
    class LeaseEntry:
        def __init__(self, leasetime, macAddress, ipAddress, name):
            if (leasetime == '0'):
                self.staticIP = True
            else:
                self.staticIP = False
            self.leasetime = datetime.datetime.fromtimestamp(
                int(leasetime)
            ).strftime('%Y-%m-%d %H:%M:%S')
            self.macAddress = macAddress.upper()
            self.ipAddress = ipAddress
            self.name = name
        def serialize(self):
            return {
                'staticIP': self.staticIP,
                'leasetime': self.leasetime,
                'macAddress': self.macAddress,
                'ipAddress': self.ipAddress,
                'name': self.name
            }
    def leaseSort(arg):
        # Fixed IPs first
        if arg.staticIP == True:
            return 0
        else:
            return arg.name.lower()
    @app.route("/leases")
    def getLeases(request):
        leases = list()
        with open(DNSMASQ_LEASES_FILE) as f:
            for line in f:
                elements = line.split()
                entry = LeaseEntry(elements[0],
                                   elements[1],
                                   elements[2],
                                   elements[3])
                leases.append(entry)
        leases.sort(key=leaseSort)
        leases = [lease.serialize() for lease in leases]
        return json.dumps(leases)


    factory = WebSocketServerFactory(u"ws://127.0.0.1:9000")
    factory.protocol = MyServerProtocol
    # MyServerProtocol.SoftTags = SoftTagsUpdate.SoftTagsList
    MyServerProtocol.SoftTagsList = SoftTagsUpdate.SoftTagsList

    factory.setProtocolOptions(maxConnections=10)
    # note to self: if using putChild, the child must be bytes...
    reactor.listenTCP(9000, factory)


    app.run(host='0.0.0.0', port=5010)













