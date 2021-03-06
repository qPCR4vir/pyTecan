# Reagent - a set of samples that are allocated as they are needed
import sys
from Experiment.sample import Sample
import decklayout

__allReagents={}

class Reagent(object):
    def __init__(self,name,plate=decklayout.REAGENTPLATE,well=None,conc=None,hasBeads=False,extraVol=50):
        self.sample=None
        self.name=name
        self.plate=plate
        self.preferredWell=well
        self.conc=conc
        self.hasBeads=hasBeads
        self.extraVol=extraVol
        self.initVol=0

    def getsample(self):
        if self.sample is None:
            #print "Creating sample for reagent %s with %.1f ul"%(self.name,self.initVol)
            self.sample=Sample(self.name,self.plate,self.preferredWell,self.conc,hasBeads=self.hasBeads,volume=self.initVol)
            wellname=self.sample.plate.wellname(self.sample.well)
            if self.preferredWell != None and self.preferredWell != wellname:
                print "WARNING: %s moved from preferred well %s to %s\n"%(self.name,self.preferredWell,wellname)
        return self.sample

    def reset(self):
        'Reset reagent: clear sample, adjust initial volume to make current volume equal to extraVol'
        if self.sample!=None:
            adj=self.extraVol-self.sample.volume
            if adj>0:
                #print "Adjusting initVol of %s to %.1f"%(self.name,self.initVol+adj)
                self.initVol+=adj
            self.sample=None

def isReagent(name):
    return name in __allReagents

def getsample(name):
    return __allReagents[name].getsample()

def lookup(name):
    return __allReagents[name]

def __getattr__(name):
    return get(name)

def add(name,plate=decklayout.REAGENTPLATE,well=None,conc=None,hasBeads=False,extraVol=50):
    if name in __allReagents:
        print "ERROR: Attempt to add duplicate reagent, ",name
        assert False
    __allReagents[name]=Reagent(name,plate,well,conc,hasBeads,extraVol)
    return __allReagents[name]

def reset():
    for r in __allReagents:
        __allReagents[r].reset()

def printprep(fd=sys.stdout):
    for p in sorted(set([r.plate for r in __allReagents.itervalues()])):
        print >>fd,"\nPlate %s:"%p.name
        total=0
        for r in sorted(__allReagents.itervalues(),key=lambda p:p.sample.well if p.sample!=None else None):
            s=r.sample
            if s is None:
                continue
            if s.plate!=p:
                continue
            if s.conc!=None:
                c="[%s]"%str(s.conc)
            else:
                c=""
            if s.volume==r.initVol:
                # Not used
                #note="%s%s in %s.%s not consumed"%(s.name,c,str(s.plate),s.plate.wellname(s.well))
                #notes=notes+"\n"+note
                pass
            elif r.initVol>0:
                print >>fd,"%s%s in %s.%s consume %.1f ul, provide %.1f ul"%(s.name,c,s.plate.name,s.plate.wellname(s.well),r.initVol-s.volume,r.initVol)
            total+=round((r.initVol-s.volume)*10)/10.0
            if r.initVol>s.plate.maxVolume:
                print "ERROR: Excess initial volume (",r.initVol,") for ",s,", maximum is ",s.plate.maxVolume
        print >>fd,"Total %s volume = %.1f ul"%(p.name,total)

