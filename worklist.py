# Module for generating a worklist from a set of commands
class Plate(object):
    def __init__(self,name, grid, pos, nx=12, ny=8):
        self.name=name
        self.grid=grid
        self.pos=pos
        self.nx=nx
        self.ny=ny

    def __str__(self):
        return self.name
        
class WorkList(object):
    OPEN=0
    CLOSE=1
    DONOTMOVE=2
    SAFETOEND=0
    ENDTOSAFE=1
    
    debug=False
    list=[]
    volumes={}
    
    def bin(s):
        return str(s) if s<=1 else bin(s>>1) + str(s&1)

    @staticmethod
    def wellSelection(nx,ny,pos):
        'Build a well selection string'
        s="%02x%02x"%(nx,ny)
        vals=[ 0 for x in range(7*((nx*ny+6)/7)) ]
        for i in pos:
            vals[i]=1
        bitCounter=0
        bitMask=0
        for i in range(len(vals)):
            if vals[i]:
                bitMask=bitMask | (1<<bitCounter)
            bitCounter=bitCounter+1
            if bitCounter>6:
                s=s+chr(0x30+bitMask)
                bitCounter=0
                bitMask=0
        if bitCounter>0:
            s=s+chr(0x30+bitMask)
        return s


    #def aspirate(tipMask, liquidClass, volume, loc, spacing, ws):
    def aspirate(self,wells, liquidClass, volume, loc):
        self.aspirateDispense('Aspirate',wells, liquidClass, volume, loc)

    def dispense(self,wells, liquidClass, volume, loc):
        self.aspirateDispense('Dispense',wells, liquidClass, volume, loc)

    def mix(self,wells, liquidClass, volume, loc, cycles=3):
        self.aspirateDispense('Mix',wells, liquidClass, volume, loc, cycles)
        
    def aspirateDispense(self,op,wells, liquidClass, volume, loc, cycles=None):
        # Update volumes
        if op=='Aspirate':
            vincr=-volume
        elif op=='Dispense':
            vincr=volume
        else:
            vincr=0
            
        if vincr != 0:
            if loc not in self.volumes:
                self.volumes[loc]={}
            for well in wells:
                if well not in self.volumes[loc]:
                    self.volumes[loc][well]=vincr
                else:
                    self.volumes[loc][well]=self.volumes[loc][well]+vincr
                    
            
        tipMask=0
        spacing=1
        pos=[0 for x in range(len(wells))]
        for i in range(len(wells)):
            well=wells[i]
            if isinstance(well,(long,int)):
                ival=int(well)
                (col,row)=divmod(ival,loc.ny)
                col=col+1
                row=row+1
            else:
                col=int(well[1:])
                row=ord(well[0])-ord('A')+1
            assert(row>=1 and row<=loc.ny and col>=1 and col<=loc.nx)
            pos[i]=(row-1)+loc.ny*(col-1)
            if i>0:
                assert(col==prevcol)
            prevcol=col

        span=pos[len(pos)-1]-pos[0]
        if span<4:
            spacing=1
        else:
            spacing=2
        allvols=[0 for x in range(12)]
        for i in range(len(wells)):
            if i==0:
                tip=0
            else:
                dm=divmod(pos[i]-pos[0],spacing)
                assert(dm[1]==0)
                tip=dm[0]
            tipMask=tipMask | (1<<tip)
            if type(volume)==type([]):
                allvols[tip]=volume[i]
            else:
                allvols[tip]=volume

        if self.debug:
            print "allvols=",allvols
            print "pos[0]=",pos[0]
            print "spacing=",spacing

        ws=WorkList.wellSelection(loc.nx,loc.ny,pos)
        volstr="%.2f"%allvols[0]
        for i in range(1,11):
            volstr="%s,%.2f"%(volstr,allvols[i]);
        if op=="Mix":
            self.list.append( '%s(%d,"%s",%s,%d,%d,%d,"%s",%d,0)'%(op,tipMask,liquidClass,volstr,loc.grid,loc.pos,spacing,ws,cycles))
        else:
            self.list.append( '%s(%d,"%s",%s,%d,%d,%d,"%s",0)'%(op,tipMask,liquidClass,volstr,loc.grid,loc.pos,spacing,ws))

    # Get DITI
    def getDITI(self, tipMask, volume, retry=True):
        DITI200=1
        DITI10=2
        assert(tipMask>=1 and tipMask<=15)
        assert(volume>0 and volume<200)
        if retry:
            options=1
        else:
            options=0
        if volume<10:
            type=DITI10
        elif volume<200:
            type=DITI200
        self.list.append('GetDITI(%d,%d,%d)'%(tipMask,type,options))

    def dropDITI(self, tipMask, loc, airgap=10, airgapSpeed=70):
        'Drop DITI, airgap is in ul, speed in ul/sec'
        assert(tipMask>=1 and tipMask<=15)
        assert(airgap>=0 and airgap<=100)
        assert(airgapSpeed>=1 and airgapSpeed<1000)
        self.list.append('DropDITI(%d,%d,%d,%f,%d)'%(tipMask,loc.grid,loc.pos,airgap,airgapSpeed))

    def vector(self, vector,loc, direction, andBack, beginAction, endAction, slow=True):
        'Move ROMA.  Gripper actions=0 (open), 1 (close), 2 (do not move).'
        if slow:
            speed=1
        else:
            speed=0
        if andBack:
            andBack=1
        else:
            andBack=0
        self.list.append('Vector("%s",%d,%d,%d,%d,%d,%d,%d,0)'%(vector,loc.grid,loc.pos,direction,andBack,beginAction, endAction, speed))

    def romahome(self):
        self.list.append('ROMA(2,0,0,0,0,0,60,0,0)')
        
    def userprompt(self, text, beeps=0, closetime=-1):
        'Prompt the user with text.  Beeps = 0 (no sound), 1 (once), 2 (three times), 3 (every 3 seconds).  Close after closetime seconds if > -1'
        self.list.append('UserPrompt("%s",%d,%d)'%(text,beeps,closetime))

    def comment(self, text):
        self.list.append('Comment("%s")'%text)
        
    def execute(self, command, wait=True, resultvar=None):
        'Execute an external command'
        flags=0
        if wait:
            flags=flags | 2
        if resultvar!=None and resultvar!="":
            flags=flags | 4
        else:
            resultvar=""
        self.list.append('Execute("%s",%d,"%s")'%(command,flags,resultvar))

    def pyrun(self, cmd):
        self.execute("c:\Python32\python.exe c:\Home\Admin\%s"%cmd)
        
    def dump(self):
        'Dump current worklist'
        for i in range(len(self.list)):
            print self.list[i]

    def dumpvols(self):
        'Dump final volumes'
        for loc in self.volumes:
            for well in self.volumes[loc]:
                print "%-14s\t%s\t%6.1f"%(str(loc),str(well),self.volumes[loc][well])

    def save(self,filename):
        'Save worklist in a file in format that Gemini can load'
        fd=open(filename,'w')
        for loc in self.volumes:
            for well in self.volumes[loc]:
                if self.volumes[loc][well]<0:
                    print >>fd,'B;Comment("Make sure %s.%s has at least %.1f ul")'%(str(loc),str(well),-self.volumes[loc][well])
        for i in range(len(self.list)):
            print >>fd, "B;%s"%str(self.list[i])
        fd.close()
        