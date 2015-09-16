from worklist import *
from sample import Sample
from concentration import Concentration
import liquidclass
import os.path
from datetime import datetime

ptcrunning=False

class Experiment(object):
    WASHLOC=Plate("Wash",1,2,1,8,False,0)
    REAGENTPLATE=Plate("Reagents",18,1,6,5,False,20,1700)
    SAMPLEPLATELOC=Plate("Samples",4,3,12,8,False,15)
    MAGPLATELOC=Plate("MagPlate",18,2,12,8,False,9)   # HSP9601 on magnetic plate  (Unusable volume of 9ul)
    SAMPLEPLATE=Plate("Samples",4,3,12,8,False,15)
    SHAKERPLATELOC=Plate("Shaker",9,0,1,1)
    #    READERPLATE=Plate("Reader",4,1,12,8,False,15)
    QPCRPLATE=Plate("qPCR",4,1,12,8,False,15)
    DILPLATE=Plate("Dilutions",4,2,12,8,False,15)
    SSDDILLOC=Plate("SSDDil",3,1,1,4,False,100,100000)
    WATERLOC=Plate("Water",3,2,1,4,False,100,100000)
    BLEACHLOC=Plate("Bleach",3,3,1,4,False,0,100000)
    PTCPOS=Plate("PTC",25,1,1,1)
    HOTELPOS=Plate("Hotel",25,0,1,1)
    WASTE=Plate("Waste",20,3,1,1)
    EPPENDORFS=Plate("Eppendorfs",13,1,1,16,False,30,1500)
    WATER=Sample("Water",WATERLOC,-1,None,50000)
    SSDDIL=Sample("SSDDil",SSDDILLOC,-1,None,50000)
    BLEACH=Sample("RNase-Away",BLEACHLOC,-1,None,50000)
    DITIMASK=0   # Which tips are DiTis
    headerfile=os.path.expanduser("~/Dropbox/Synbio/Robot/pyTecan/header.gem")

    RPTEXTRA=0   # Extra amount when repeat pipetting
    MAXVOLUME=200  # Maximum volume for pipetting in ul

    def __init__(self):
        'Create a new experiment with given sample locations for water and self.WASTE'
        self.w=WorkList()
        self.w.comment("Generated %s"%(datetime.now().ctime()));
        self.w.userprompt("The following reagent tubes should be present: %s"%Sample.getAllLocOnPlate(self.REAGENTPLATE))
        self.w.userprompt("The following eppendorf tubes should be present: %s"%Sample.getAllLocOnPlate(self.EPPENDORFS))
        self.w.email(dest='cdsrobot@gmail.com',subject='Run started (Generate: %s)'%(datetime.now().ctime()))
        self.w.email(dest='cdsrobot@gmail.com',subject='Tecan error',onerror=1)
        self.cleanTips=0
        # self.sanitize()  # Not needed, TRP does it, also first use of tips will do this
        self.useDiTis=False
        self.thermotime=0
        self.BLEACH.mixLC=liquidclass.LC("RNaseAway-Mix")
        self.ptcrunning=False
        # Access PTC and RIC early to be sure they are working
        self.w.pyrun("PTC\\ptctest.py")
        #        self.w.periodicWash(15,4)
        self.w.userprompt("Verify that PTC thermocycler lid pressure is set to '0'.")
        
    def setreagenttemp(self,temp=None):
        if temp==None:
            self.w.pyrun("RIC\\ricset.py IDLE")
        else:
            self.w.variable("dewpoint",temp,userprompt="Enter dewpoint",minval=0,maxval=20)
            self.w.variable("rictemp","~dewpoint~+2")
            self.w.pyrun("RIC\\ricset.py ~rictemp~")
#            self.w.pyrun("RIC\\ricset.py %s"%temp)

    def saveworklist(self,filename):
        self.w.saveworklist(filename)

    def savegem(self,filename):
        self.w.flushQueue()
        self.w.savegem(self.headerfile,filename)
        
    def savesummary(self,filename):
        # Print amount of samples needed
        fd=open(filename,"w")
        print >>fd,"Deck layout:"
        print >>fd,self.REAGENTPLATE
        print >>fd,self.SAMPLEPLATE
        print >>fd,self.QPCRPLATE
        print >>fd,self.WATERLOC
        print >>fd,self.WASTE
        print >>fd,self.BLEACHLOC
        print >>fd,self.WASHLOC
        
        print >>fd
        print >>fd,"DiTi usage:",self.w.getDITIcnt()
        print >>fd

        print >>fd,"Run time: %d (pipetting) + %d (thermocycling) = %d minutes\n"%(self.w.elapsed/60.0,self.thermotime/60, (self.w.elapsed+self.thermotime)/60)
        Sample.printprep(fd)
        Sample.printallsamples("All Samples:",fd,w=self.w)
        fd.close()
        
    def sanitize(self,nmix=1,deepvol=20,force=False):
        'Deep wash including RNase-Away treatment'
        fixedTips=(~self.DITIMASK)&15
        self.w.flushQueue()
        if not force and fixedTips==self.cleanTips:
            # print no sanitize needed
            self.w.comment("Sanitize not needed cleanTips=%d"%self.cleanTips)
            return
        self.w.comment("Sanitize (cleanTips=%d)"%self.cleanTips)
        self.w.wash(15,1,2)
        fixedWells=[]
        for i in range(4):
            if (fixedTips & (1<<i)) != 0:
                fixedWells.append(i)
                self.BLEACH.addhistory("SANITIZE",0,1<<i)
        self.w.mix(fixedTips,fixedWells,self.BLEACH.mixLC,200,self.BLEACH.plate,nmix,False);
        self.w.wash(fixedTips,1,deepvol,True)
        self.cleanTips|=fixedTips
        # print "* Sanitize"
        
    def cleantip(self):
        'Get the mask for a clean tip, washing if needed'
        if self.cleanTips==0:
            #self.w.wash(self.cleanTips)
            self.sanitize()
        tipMask=1
        while (self.cleanTips & tipMask)==0:
            tipMask<<=1
        self.cleanTips&=~tipMask
        return tipMask
            
    def multitransfer(self, volumes, src, dests,mix=(False,False),getDITI=True,dropDITI=True,ignoreContents=False):
        'Multi pipette from src to multiple dest.  mix is (src,dest) mixing'
        #print "multitransfer(",volumes,",",src,",",dests,",",mix,",",getDITI,",",dropDITI,")"
        if self.ptcrunning and (src.plate==Experiment.SAMPLEPLATE or len([1 for d in dests if d.plate==Experiment.SAMPLEPLATE])>0):
            self.waitpgm()
            
        if isinstance(volumes,(int,long,float)):
            # Same volume for each dest
            volumes=[volumes for i in range(len(dests))]
        assert(len(volumes)==len(dests))
        #        if len([d.volume for d in dests if d.conc!=None])==0:
        if len([dests[i].volume for i in range(0,len(dests)) if dests[i].conc != None and volumes[i]>0.01])==0:
            maxval=0
        else:
            maxval=max([dests[i].volume for i in range(0,len(dests)) if dests[i].conc != None and volumes[i]>0.01])
            #         maxval=max([d.volume for d in dests if d.conc != None])
        #print "volumes=",[d.volume for d in dests],", conc=",[str(d.conc) for d in dests],", maxval=",maxval
        if mix[1]==False and len(volumes)>1 and ( maxval<.01 or ignoreContents):
            if sum(volumes)>self.MAXVOLUME:
                #print "sum(volumes)=%.1f, MAXVOL=%.1f"%(sum(volumes),self.MAXVOLUME)
                for i in range(1,len(volumes)):
                    if sum(volumes[0:i+1])>self.MAXVOLUME:
                        destvol=max([d.volume for d in dests[0:i]])
                        reuseTip=destvol<=0
                        # print "Splitting multi with total volume of %.1f ul into smaller chunks < %.1f ul after %d dispenses "%(sum(volumes),self.MAXVOLUME,i),
                        # if reuseTip:
                        #     print "with tip reuse"
                        # else:
                        #     print "without tip reuse"
                        self.multitransfer(volumes[0:i],src,dests[0:i],mix,getDITI,not reuseTip)
                        self.multitransfer(volumes[i:],src,dests[i:],(False,mix[1]),not reuseTip,dropDITI)
                        return
                    
            if self.useDiTis:
                tipMask=4
                if  getDITI:
                    ditivol=sum(volumes)+src.inliquidLC.multicond+src.inliquidLC.multiexcess
                    self.w.getDITI(tipMask&self.DITIMASK,min(self.MAXVOLUME,ditivol),True,True)
            else:
                tipMask=self.cleantip()

            cmt="Multi-add  %s to samples %s"%(src.name,",".join("%s[%.1f]"%(dests[i].name,volumes[i]) for i in range(len(dests))))
            #print "*",cmt
            self.w.comment(cmt)

            if mix[0] and not src.isMixed:
                src.mix(tipMask,self.w)
            src.aspirate(tipMask,self.w,sum(volumes),True)
            for i in range(len(dests)):
                if volumes[i]>0.01:
                    dests[i].dispense(tipMask,self.w,volumes[i],src)
            if self.useDiTis and dropDITI:
                self.w.dropDITI(tipMask&self.DITIMASK,self.WASTE)
        else:
            for i in range(len(dests)):
                if volumes[i]>0.01:
                    self.transfer(volumes[i],src,dests[i],(mix[0] and i==0,mix[1]),getDITI,dropDITI)

    def transfer(self, volume, src, dest, mix=(False,False), getDITI=True, dropDITI=True):
        if self.ptcrunning and (src.plate==Experiment.SAMPLEPLATE or dest.plate==Experiment.SAMPLEPLATE)>0:
            self.waitpgm()
        if volume>self.MAXVOLUME:
            destvol=dest.volume
            reuseTip=destvol<=0
            print "Splitting large transfer of %.1f ul into smaller chunks < %.1f ul "%(volume,self.MAXVOLUME),
            if reuseTip:
                print "with tip reuse"
            else:
                print "without tip reuse"
            self.transfer(self.MAXVOLUME,src,dest,mix,getDITI,False)
            self.transfer(volume-self.MAXVOLUME,src,dest,(mix[0] and not reuseTip,mix[1]),False,dropDITI)
            return
        
        cmt="Add %.1f ul of %s to %s"%(volume, src.name, dest.name)
        ditivolume=volume+src.inliquidLC.singletag
        if mix[0] and not src.isMixed:
            cmt=cmt+" with src mix"
            ditivolume=max(ditivolume,src.volume)
        if mix[1] and dest.volume>0 and not src.isMixed:
            cmt=cmt+" with dest mix"
            ditivolume=max(ditivolume,volume+dest.volume)
            #            print "Mix volume=%.1f ul"%(ditivolume)
        if self.useDiTis:
            tipMask=4
            if getDITI:
                self.w.getDITI(tipMask&self.DITIMASK,ditivolume)
        else:
            tipMask=self.cleantip()
        #print "*",cmt
        self.w.comment(cmt)

        if mix[0]:
            src.mix(tipMask,self.w)
        src.aspirate(tipMask,self.w,volume)
        dest.dispense(tipMask,self.w,volume,src)
        if mix[1]:
            dest.mix(tipMask,self.w,True)

        if self.useDiTis and dropDITI:
            self.w.dropDITI(tipMask&self.DITIMASK,self.WASTE)

    # Mix
    def mix(self, src, nmix=4):
        if self.ptcrunning and src.plate==Experiment.SAMPLEPLATE:
            self.waitpgm()

        cmt="Mix %s"%(src.name)
        tipMask=self.cleantip()
        self.w.comment(cmt)
        src.isMixed=False	# Force a mix
        src.mix(tipMask,self.w,False,nmix=nmix)

    def dispose(self, volume, src,  mix=False, getDITI=True, dropDITI=True):
        'Dispose of a given volume by aspirating and not dispensing (will go to waste during next wash)'
        if self.ptcrunning and src.plate==Experiment.SAMPLEPLATE:
            self.waitpgm()
        if volume>self.MAXVOLUME:
            reuseTip=False   # Since we need to wash to get rid of it
            print "Splitting large transfer of %.1f ul into smaller chunks < %.1f ul "%(volume,self.MAXVOLUME),
            if reuseTip:
                print "with tip reuse"
            else:
                print "without tip reuse"
            self.dispose(self.MAXVOLUME,src,mix,getDITI,dropDITI)
            self.dispose(volume-self.MAXVOLUME,src,False,getDITI,dropDITI)
            return
        
        cmt="Remove and dispose of %.1f ul from %s"%(volume, src.name)
        ditivolume=volume+src.inliquidLC.singletag
        if mix and not src.isMixed:
            cmt=cmt+" with src mix"
            ditivolume=max(ditivolume,src.volume)
        if self.useDiTis:
            tipMask=4
            if getDITI:
                self.w.getDITI(tipMask&self.DITIMASK,ditivolume)
        else:
            tipMask=self.cleantip()
        #print "*",cmt
        self.w.comment(cmt)

        if mix and not src.isMixed:
            src.mix(tipMask,self.w)
        src.aspirate(tipMask,self.w,volume)

        if self.useDiTis and dropDITI:
            self.w.dropDITI(tipMask&self.DITIMASK,self.WASTE)

    def stage(self,stagename,reagents,sources,samples,volume,finalx=1.0,destMix=True,dilutant=None):
        # Add water to sample wells as needed (multi)
        # Pipette reagents into sample wells (multi)
        # Pipette sources into sample wells
        # Concs are in x (>=1)

        # Sample.printallsamples("Before "+stagename)
        # print "\nStage: ", stagename, "reagents=",[str(r) for r in reagents], ",sources=",[str(s) for s in sources],",samples=",[str(s) for s in samples],str(volume)

        if len(samples)==0:
            print "No samples\n"
            return

        if dilutant==None:
            dilutant=self.WATER
            
        self.w.comment("Stage: "+stagename)
        if not isinstance(volume,list):
            volume=[volume for i in range(len(samples))]
        for i in range(len(volume)):
            assert(volume[i]>0)
            volume[i]=float(volume[i])
            
        reagentvols=[1.0/x.conc.dilutionneeded()*finalx for x in reagents]
        if len(sources)>0:
            sourcevols=[volume[i]*1.0/sources[i].conc.dilutionneeded()*finalx for i in range(len(sources))]
            while len(sourcevols)<len(samples):
                sourcevols.append(0)
            watervols=[volume[i]*(1-sum(reagentvols))-samples[i].volume-sourcevols[i] for i in range(len(samples))]
        else:
            watervols=[volume[i]*(1-sum(reagentvols))-samples[i].volume for i in range(len(samples))]

        if min(watervols)<-0.01:
            print "Error: Ingredients add up to more than desired volume by %.1f ul"%(-min(watervols))
            for s in samples:
                if (s.volume>0):
                    print "Note: %s already contains %.1f ul\n"%(s.name,s.volume)
            assert(False)

        if sum(watervols)>0.01:
            self.multitransfer(watervols,dilutant,samples,(False,destMix and (len(reagents)+len(sources)==0)))

        for i in range(len(reagents)):
            self.multitransfer([reagentvols[i]*v for v in volume],reagents[i],samples,(True,destMix and (len(sources)==0 and i==len(reagents)-1)))

        if len(sources)>0:
            assert(len(sources)<=len(samples))
            for i in range(len(sources)):
                self.transfer(sourcevols[i],sources[i],samples[i],(True,destMix))


    def lihahome(self):
        'Move LiHa to left of deck'
        self.w.moveliha(self.WASHLOC)
        
    def runpgm(self,pgm,duration,waitForCompletion=True,volume=10,hotlidmode="TRACKING",hotlidtemp=1):
        if self.ptcrunning:
            print "ERROR: Attempt to start a progam on PTC when it is already running"
            assert(False)
        if len(pgm)>8:
            print "ERROR: PTC program name (%s) too long (max is 8 char)"%pgm
            assert(False)
        # move to thermocycler
        self.w.flushQueue()
        self.lihahome()
        cmt="run %s"%pgm
        self.w.comment(cmt)
        #print "*",cmt
        self.w.pyrun("PTC\\ptclid.py OPEN")
        self.moveplate(self.SAMPLEPLATE,"PTC")
        #self.w.vector("Microplate Landscape",self.SAMPLEPLATE,self.w.SAFETOEND,True,self.w.DONOTMOVE,self.w.CLOSE)
        #self.w.vector("PTC200",self.PTCPOS,self.w.SAFETOEND,True,self.w.DONOTMOVE,self.w.OPEN)
        self.w.vector("Hotel 1 Lid",self.HOTELPOS,self.w.SAFETOEND,True,self.w.DONOTMOVE,self.w.CLOSE)
        self.w.vector("PTC200lid",self.PTCPOS,self.w.SAFETOEND,True,self.w.DONOTMOVE,self.w.OPEN)
        self.w.romahome()
        self.w.pyrun("PTC\\ptclid.py CLOSE")
        #        pgm="PAUSE30"  # For debugging
        assert(hotlidmode=="TRACKING" or hotlidmode=="CONSTANT")
        assert((hotlidmode=="TRACKING" and hotlidtemp>=0 and hotlidtemp<=45) or (hotlidmode=="CONSTANT" and hotlidtemp>30))
        self.w.pyrun('PTC\\ptcrun.py %s CALC %s,%d %d'%(pgm,hotlidmode,hotlidtemp,volume))
        self.thermotime+=duration*60+self.w.elapsed   # Add on elapsed time so we can cancel out intervening time in waitpgm()
        self.ptcrunning=True
        Sample.addallhistory("{%s}"%pgm,addToEmpty=False,onlyplate=self.SAMPLEPLATE.name)
        if waitForCompletion:
            self.waitpgm()
            
    def moveplate(self,plate,dest="Home",returnHome=True):
        # move to given destination (one of "Home","Magnet","Shaker","PTC" )
        if plate.name!="Samples" and plate.name!="Dilutions":
            print "Only able to move samples or dilutions plates, not ",plate.name
            assert(False)
            
        if plate.curloc==dest:
            #print "Plate %s is already at %s"%(plate.name,dest)
            return
        
        #print "Move plate %s from %s to %s"%(plate.name,plate.curloc,dest)
        self.w.flushQueue()
        self.lihahome()
        cmt="moveplate %s %s"%(plate.name,dest)
        self.w.comment(cmt)
        if plate.curloc=="Home":
            self.w.vector("Microplate Landscape",plate,self.w.SAFETOEND,True,self.w.DONOTMOVE,self.w.CLOSE)
        elif plate.curloc=="Magnet":
            self.w.vector("Magplate",self.MAGPLATELOC,self.w.SAFETOEND,True,self.w.DONOTMOVE,self.w.CLOSE)
        elif plate.curloc=="Shaker":
            self.w.vector("Shaker",self.SHAKERPLATELOC,self.w.SAFETOEND,True,self.w.DONOTMOVE,self.w.CLOSE)
        elif plate.curloc=="PTC":
            self.w.vector("PTC200",self.PTCPOS,self.w.SAFETOEND,True,self.w.DONOTMOVE,self.w.CLOSE)
        else:
            print "Plate %s is in unknown location: %s"%(plate.name,plate.curloc)
            assert(False)

        if dest=="Home":
            plate.movetoloc(dest)
            self.w.vector("Microplate Landscape",plate,self.w.SAFETOEND,True,self.w.DONOTMOVE,self.w.OPEN)
        elif dest=="Magnet":
            plate.movetoloc(dest,self.MAGPLATELOC)
            self.w.vector("Magplate",self.MAGPLATELOC,self.w.SAFETOEND,True,self.w.DONOTMOVE,self.w.OPEN)
        elif dest=="Shaker":
            plate.movetoloc(dest,self.SHAKERPLATELOC)
            self.w.vector("Shaker",self.SHAKERPLATELOC,self.w.SAFETOEND,True,self.w.DONOTMOVE,self.w.OPEN)
        elif dest=="PTC":
            plate.movetoloc(dest,self.PTCPOS)
            self.w.vector("PTC200",self.PTCPOS,self.w.SAFETOEND,True,self.w.DONOTMOVE,self.w.OPEN)
        else:
            print "Attempt to move plate %s to unknown location: %s"%(plate.name,dest)
            assert(False)

        Sample.addallhistory("{->%s}"%dest,onlyplate=plate.name)
        if returnHome:
            self.w.romahome()

    def shake(self,plate,dur=60,speed=1600,accel=1,returnPlate=True):
        if self.ptcrunning and plate==Experiment.SAMPLEPLATE:
            self.waitpgm()

        # Move the plate to the shaker, run for the given time, and bring plate back
        # Recommended speeds (from http://www.qinstruments.com/en/applications/optimization-of-mixing-parameters.html )
        #  10% fill:  1800-2200, 25%: 1600-2000, 50%: 1400-1800, 75%: 1200-1600
        # At 1600, 150ul is ok, but 200ul spills out
        # Check volumes on plate
        samps=Sample.getAllOnPlate(plate)
        maxvol=max([x.volume for x in samps])
        if (maxvol>151 and speed>=1600) or (maxvol>101 and speed>1800) or (maxvol>51 and speed>2000) or (maxvol>21 and speed>2200):
            print "WARNING: %s plate contains wells with up to %.2f ul, which may spill at %d RPM"%(plate.name, maxvol, speed)
        oldloc=plate.curloc
        self.moveplate(plate,"Shaker",returnHome=False)
        self.w.pyrun("BioShake\\bioexec.py setElmLockPos")
        self.w.pyrun("BioShake\\bioexec.py setShakeTargetSpeed%d"%speed)
        self.w.pyrun("BioShake\\bioexec.py setShakeAcceleration%d"%accel)
        self.w.pyrun("BioShake\\bioexec.py shakeOn")
        self.starttimer()
        Sample.mixall(plate.name)
        Sample.addallhistory("(S%d)"%dur,onlyplate=plate.name)
        self.waittimer(dur)
        self.w.pyrun("BioShake\\bioexec.py shakeOff")
        self.starttimer()
        self.waittimer(5)
        self.w.pyrun("BioShake\\bioexec.py setElmUnlockPos")
        if returnPlate:
            self.moveplate(plate,oldloc)

    def starttimer(self):
    	self.w.starttimer()

    def waittimer(self,duration):
        if duration>10:
            # Might as well sanitize while we're waiting
            elapsed=self.w.elapsed
            self.sanitize()
            self.w.elapsed=elapsed+max(self.w.elapsed-elapsed-duration,0)	# Don't count this time since the wait will handle it
        else:
            self.w.elapsed+=duration
        if duration>0:
            self.w.waittimer(duration)
            #Sample.addallhistory("{%ds}"%duration)

    def pause(self,duration):
        self.starttimer()
        self.waittimer(duration)
        Sample.addallhistory("(%ds)"%duration)
        
    def waitpgm(self, sanitize=True):
        if not self.ptcrunning:
            return
        #print "* Wait for PTC to finish"
        if sanitize:
            self.sanitize()   # Sanitize tips before waiting for this to be done
        self.w.comment("Wait for PTC")
        self.thermotime-=self.w.elapsed
        self.w.pyrun('PTC\\ptcwait.py')
        self.w.pyrun("PTC\\ptclid.py OPEN")
        #        self.w.pyrun('PTC\\ptcrun.py %s CALC ON'%"COOLDOWN")
        #        self.w.pyrun('PTC\\ptcwait.py')
        self.w.vector("PTC200lid",self.PTCPOS,self.w.SAFETOEND,True,self.w.DONOTMOVE,self.w.CLOSE)
        self.w.vector("Hotel 1 Lid",self.HOTELPOS,self.w.SAFETOEND,True,self.w.DONOTMOVE,self.w.OPEN)

        self.w.vector("PTC200WigglePos",self.PTCPOS,self.w.SAFETOEND,False,self.w.DONOTMOVE,self.w.DONOTMOVE)
        self.w.vector("PTC200Wiggle",self.PTCPOS,self.w.SAFETOEND,False,self.w.DONOTMOVE,self.w.CLOSE,True)
        self.w.vector("PTC200Wiggle",self.PTCPOS,self.w.ENDTOSAFE,False,self.w.DONOTMOVE,self.w.OPEN,True)
        self.w.vector("PTC200WigglePos",self.PTCPOS,self.w.ENDTOSAFE,False,self.w.DONOTMOVE,self.w.DONOTMOVE)

        self.w.vector("PTC200Wiggle2Pos",self.PTCPOS,self.w.SAFETOEND,False,self.w.DONOTMOVE,self.w.DONOTMOVE)
        self.w.vector("PTC200Wiggle2",self.PTCPOS,self.w.SAFETOEND,False,self.w.DONOTMOVE,self.w.CLOSE,True)
        self.w.vector("PTC200Wiggle2",self.PTCPOS,self.w.ENDTOSAFE,False,self.w.DONOTMOVE,self.w.OPEN,True)
        self.w.vector("PTC200Wiggle2Pos",self.PTCPOS,self.w.ENDTOSAFE,False,self.w.DONOTMOVE,self.w.DONOTMOVE)

        self.w.vector("PTC200WigglePos",self.PTCPOS,self.w.SAFETOEND,False,self.w.DONOTMOVE,self.w.DONOTMOVE)
        self.w.vector("PTC200Wiggle",self.PTCPOS,self.w.SAFETOEND,False,self.w.DONOTMOVE,self.w.CLOSE,True)
        self.w.vector("PTC200Wiggle",self.PTCPOS,self.w.ENDTOSAFE,False,self.w.DONOTMOVE,self.w.OPEN,True)
        self.w.vector("PTC200WigglePos",self.PTCPOS,self.w.ENDTOSAFE,False,self.w.DONOTMOVE,self.w.DONOTMOVE)

        self.moveplate(self.SAMPLEPLATE,"Home")
        #self.w.vector("PTC200",self.PTCPOS,self.w.SAFETOEND,True,self.w.DONOTMOVE,self.w.CLOSE)
        #self.w.vector("Microplate Landscape",self.SAMPLEPLATE,self.w.SAFETOEND,True,self.w.DONOTMOVE,self.w.OPEN)
        # Verify plate is in place
        self.w.vector("Microplate Landscape",self.SAMPLEPLATE,self.w.SAFETOEND,False,self.w.DONOTMOVE,self.w.CLOSE)
        self.w.vector("Microplate Landscape",self.SAMPLEPLATE,self.w.ENDTOSAFE,False,self.w.OPEN,self.w.DONOTMOVE)
        self.w.romahome()
        self.ptcrunning=False
        #self.w.userprompt("Plate should be back on deck. Press return to continue")
        # Wash tips again to remove any drips that may have formed while waiting for PTC
        self.w.wash(15,1,5,True)


    def dilute(self,samples,factor):
        if isinstance(factor,list):
            assert(len(samples)==len(factor))
            for i in range(len(samples)):
                samples[i].dilute(factor[i])
        else:
            for s in samples:
                s.dilute(factor)
