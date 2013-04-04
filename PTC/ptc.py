# Module to interface to PTC-200
import serial
import string

class PTCStatus:
    # Construct status from PTC-200s reply to STATUS? stored in 'm' as a sequence
    besrhold=0
    ATTARGET=1
    PAUSED=2
    LIDOPEN=4
    LIDHEATING=8
    INCUBATING=16
    RUNNING=32
    BLOCKACTIVE=64
    ABORTED=128
    
    def update(self,m):
        # print "m=",m
        self.block=m[0]
        self.blocktemp=float(m[1])
        self.probetemp=float(m[2])
        self.calctemp=float(m[3])
        self.lidtemp=float(m[4])
        rstat=string.split(m[5],",")
        self.pgm=rstat[0].strip('"')
        self.method=rstat[1]
        self.lid=rstat[2]
        self.cmd=m[6].strip('"')
        self.cycles=int(m[7])
        self.cycle=int(m[8])
        self.step=int(m[9])
        self.ptime=float(m[10])
        self.stime=float(m[11])
        self.etime=float(m[12])
        self.bsr=int(m[13])
        self.besr=int(m[14])
        self.besrhold|=self.besr
        self.unknown=m[15:17]

    def __str__(self):
        return (
                 "pgm:"+self.pgm+
                 # ", block:"+self.block+
                 ", method:"+self.method+
                 ", lid:"+self.lid+
                 ", blocktemp:"+("%.1f"%self.blocktemp)+
                 # ", probetemp:"+("%.1f"%self.probetemp)+
                 ", calctemp:"+("%.1f"%self.calctemp)+
                 ", lidtemp:"+("%.1f"%self.lidtemp)+
                 ", cmd:"+self.cmd+
                 ", ptime:"+("%.2f"%self.ptime)+
                 ", stime:"+("%.2f"%self.etime)+
                 ", etime:"+("%.2f"%self.etime)+
                 ", cycles:"+str(self.cycles)+
                 ", cycle:"+str(self.cycle)+
                 ", step:"+str(self.step)+
                 ", bsr:"+str(self.bsr)+
                 ", besr:"+str(self.besr)+
                 ", besr(HOLD):"+str(self.besrhold)+
                 ", unknown:"+str(self.unknown)+
                 ""
                 )
    def clearbesr(self):
        self.besrhold=0
    
class PTC:
    debug=False
    ser=None
    PORT=2
    stat=PTCStatus()
    
    class CmdError(BaseException):
        pass
    
    def __init__(self,to=1):
        self.ser = serial.Serial(self.PORT,baudrate=9600,timeout=to)
        if self.debug:
            print self.ser.portstr

    def __del__(self):
        self.close()
        
    def setdebug(self):
        self.debug=True
        
    def close(self):
        if self.ser.isOpen():
            print "Closing port"
            self.ser.close()

    def execute(self,cmd):
        if self.debug:
            print "Sending command: ",cmd,
        self.ser.write(cmd+"\n")
        line=self.ser.readline()
        if self.debug:
            print ", response:",line
        return string.strip(line)

    def gettemp(self):
        res=self.execute("CALCTEMP?")
        temp=float(res)
        return temp

    def cancel(self):
        res=self.execute("CANCEL")

    def version(self):
        res=self.execute("BOOTVERSION?")
        return res
    
    def getstatus(self):
        res=self.execute("STATUS?")
        res=string.split(res,';')
        self.stat.update(res)
        return self.stat

    def geterrors(self):
        res=self.execute("ERRORS?")
        return res

    def run(self,name):
        res=self.execute("RUN \"%s\",CALC,ON",name)

    def getlidstatus(self):
        res=self.execute("LID?")
        return res
    def lidopen(self):
        res=self.execute("LID OPEN")
    def lidclose(self,force):
        res=self.execute("LID CLOSE")
    def setlidforce(self,force):
        if force not in [0,0.5,1,2]:
            raise self.CmdError("Bad force value")
        res=self.execute("LIDFORCE %f"%force)

    def folders(self):
        self.execute("FOLDERS?")

    def programs(self,folder):
        res = self.execute('PROGRAMS? "%s"'%folder)
        res=string.split(res,',')
        res=res[1:]
        for i in range(len(res)):
            res[i]=res[i].strip('"')
        return res

    def erase(self, pgm):
        res = self.execute('ERASE "%s"'%pgm)
        return res
