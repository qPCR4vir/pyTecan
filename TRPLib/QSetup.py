# Setup QPCR experiments
import TRP
import os
import sys
import math
from Experiment.experiment import Experiment
from Experiment.sample import Sample
from Experiment.JobQueue import JobQueue
from TRPLib.TRP import  diluteName
from Experiment import worklist, reagents, decklayout,clock

class QSetup(object):
    TGTINVOL=4
    
    def __init__(self,trp,vol=15,maxdil=16,mindilvol=50,maxdilvol=100,debug=False):
        'Create a new QPCR setup structure'
        self.volume=vol
        self.samples=[]
        self.needDil=[]
        self.primers=[]
        self.nreplicates=[]
        self.dilProds=[]
        self.reuse=[]   # Index of prior dilution that can be used as input to this one; otherwise None
        self.stages=[]
        self.MAXDIL=maxdil
        self.MINDILVOL=mindilvol
        self.MAXDILVOL=maxdilvol
        self.trp=trp
        self.debug=debug
        self.dilutant=decklayout.SSDDIL
        self.jobq=JobQueue()
        
    def addSamples(self, src, needDil, primers,nreplicates=1,names=None,saveVol=None,saveDil=None,save=True):
        'Add sample(s) to list of qPCRs to do'
        #print "addSamples(%s)"%src
        if not isinstance(src,list):
            src=[src]
        if save:
            # saveVol is total amount (after dilution) to be immediately saved
            if saveDil is None:
                saveDil=min(needDil,self.MAXDIL)
                if needDil/saveDil>1 and needDil/saveDil<2:
                    saveDil=math.sqrt(needDil)
            elif saveDil>needDil:
                print "addSamples: saveDil=",saveDil, ", but needDil is only ", needDil
                saveDil=needDil
    
            if saveVol is None:
                saveVol=max(self.MINDILVOL*1.0/saveDil,self.TGTINVOL)
            
            if names is None:
                tgt=[Sample(diluteName(src[i].name,saveDil),decklayout.DILPLATE) for i in range(len(src))]
            else:
                tgt=[Sample(diluteName(names[i],saveDil),decklayout.DILPLATE) for i in range(len(src))]
            sv=tgt
            
            for i in range(len(sv)):
                #print "Save ",src[i]
                svtmp=self.trp.runQPCRDIL(src=[src[i]],vol=saveVol*saveDil,srcdil=saveDil,tgt=[tgt[i]],dilPlate=True,dilutant=self.dilutant)  
                sv[i]=svtmp[0]
        else:
            saveDil=1
            sv=src

        needDil=needDil/saveDil
        nstages=int(math.ceil(math.log(needDil)/math.log(self.MAXDIL)))
        for svi in range(len(sv)):
            s=sv[svi]
            if s.hasBeads:
                prereqs=[]
            else:
                j0=self.jobq.addShake(sample=s,prereqs=[])
                prereqs=[j0]
            intermed=s

            for i in range(nstages):
                dil=math.pow(needDil,1.0/nstages)
                #print "stage ",i,", needDil=",needDil,", dil=",dil
                if i>0:
                    vol=self.MAXDILVOL
                else:
                    vol=min(self.MAXDILVOL,max(self.MINDILVOL,dil*self.TGTINVOL))
                if not save and i==0 and names is not None:
                    # Need to replace the name in this condition
                    dest=Sample(diluteName(names[svi],dil),decklayout.DILPLATE)
                else:
                    dest=Sample(diluteName(intermed.name,dil),decklayout.DILPLATE)
                #print "dest=",dest
                j1=self.jobq.addMultiTransfer(volume=vol*(dil-1)/dil,src=self.dilutant,dest=dest,prereqs=[])
                prereqs.append(j1)
                j2=self.jobq.addTransfer(volume=vol/dil,src=intermed,dest=dest,prereqs=prereqs)
                #print "Dilution of %s was %.2f instead of %.2f (error=%.0f%%)"%(dest.name,(dil/(1+dil))/(1/dil),dil,((dil/(1+dil))/(1/dil)/dil-1)*100)
                if dest.hasBeads:
                    prereqs=[j2]
                else:
                    j3=self.jobq.addShake(sample=dest,prereqs=[j2])
                    prereqs=[j3]
                intermed=dest
            self.dilProds=self.dilProds+[intermed]
            self.primers=self.primers+[primers]
            self.nreplicates=self.nreplicates+[nreplicates]
    
    def findReuses(self):
        'Find any prior dilutions that can be reused'
        maxstages=max(self.stages)
        for j in range(len(self.samples)):
            for i in range(len(self.samples)):
                # Check if we can reuse i to form j
                if i!=j and self.samples[i]==self.samples[j] and self.needDil[i]<self.needDil[j] and self.needDil[i]>1:
                    # Possible reuse
                    # Check if we already have a better one
                    if self.reuse[j]!=None and self.needDil[self.reuse[j]]>self.needDil[i]:
                        continue
                    # Check if it would increase number of stages
                    stages=int(math.ceil(math.log(self.needDil[j]/self.needDil[i])/math.log(self.MAXDIL))+self.stages[i])
                    if stages>maxstages:
                        continue
                    print "Reuse %s@%f to form %s@%f"%(self.samples[i],self.needDil[i],self.samples[j],self.needDil[j])
                    self.reuse[j]=i
                    self.stages[j]=stages
            totalDil=self.needDil[j]
            stages=self.stages[j]
            if self.reuse[j] != None:
                totalDil = totalDil / self.needDil[self.reuse[j]]
                stages = stages - self.stages[self.reuse[j]]
            if stages>1:
                print "Need to form %s@%f by diluting %f in %d stages "%(self.samples[j],self.needDil[j],totalDil,stages)
                d=1
                if self.reuse[j]!=None:
                    d=self.needDil[self.reuse[j]]
                for k in range(stages-1):
                    d=min(d*self.MAXDIL,totalDil)
                    self.addSamples([self.samples[j]],d,[])	# Add extra intermediate that can be reused
                    if k==0:
                        self.reuse[-1]=self.reuse[j]
                    else:
                        self.reuse[-1]=len(self.samples)-2
                self.reuse[j]=len(self.samples)-1
                
        for i in range(len(self.samples)):
            print "%d: %s@%f"%(i,self.samples[i],self.needDil[i]),
            if self.reuse[i]!=None:
                print ", use %d with additional %f dilution"%(self.reuse[i], self.needDil[i]/self.needDil[self.reuse[i]]),
            print " [%d stages]"%self.stages[i]
                
    def allprimers(self):
        return set([p for sublist in self.primers for p in sublist])

    def addReferences(self,mindil=1,nsteps=6,dstep=4,nreplicates=1,ref=None,primers=None):
        'Add all needed references'
        #print "addReferences(mindil=",mindil,", nsteps=",nsteps,", dstep=",dstep,", nrep=", nreplicates, ", ref=",ref,")"
        # Make sure the ref reagent is loaded
        if ref is None:
            ref=reagents.getsample("QPCRREF")
        if primers is None:
            primers=self.allprimers()
        dils=[1]
        for i in range(nsteps):
            needDil=mindil*math.pow(dstep,i)
            srcDil=1
            src=[ref]
            for j in range(len(dils)):
                if needDil/dils[j] <= self.MAXDIL:
                    srcDil=dils[j]
                    if srcDil==1:
                        src=[ref]
                    else:
                        srcname="%s.D%d"%(ref.name,srcDil)
                        src=[Sample.lookup(srcname)]
                        if src[0] is None:
                            src=[Sample(srcname,decklayout.DILPLATE)]
                    break
            tmp=self.MINDILVOL
            self.MINDILVOL=75   # Make sure there's enough for resuing dilutions
            self.addSamples(src=src,needDil=needDil/srcDil,primers=primers,nreplicates=nreplicates,save=needDil/srcDil>self.MAXDIL,saveVol=75)
            self.MINDILVOL=tmp
            dils.append(needDil)

        self.addSamples(src=[self.dilutant],needDil=1,primers=primers,nreplicates=nreplicates,save=False)

    def idler(self,t):
        endTime=clock.elapsed()+t
        if self.debug:
            print "Idler(%.0f)"%t
        while clock.elapsed()<endTime:
            j=self.jobq.getJob()
            if j is None:
                break
            self.jobq.execJob(self.trp.e,j)
        if self.debug:
            print "Idler done with ",endTime-clock.elapsed()," seconds remaining"

    def run(self):
        'Run the dilutions and QPCR setup'
        # Setup qPCRs
        #self.jobq.dump()
        self.idler(100000)
        self.trp.e.waitpgm()		# May still need to wait for PTC to complete before able to do final jobs
        self.idler(100000)
        
        if self.jobq.len()>0:
            print "Blocked jobs remain on queue:"
            self.jobq.dump()
            assert False
        worklist.userprompt('Starting qPCR setup',timeout=5)
        for p in self.allprimers():
            # Build list of relevant entries
            ind=[ i for i in range(len(self.dilProds)) if p in self.primers[i]]
            self.trp.runQPCR(src=[self.dilProds[i] for i in ind],vol=self.volume,srcdil=10.0/4,primers=[p],nreplicates=[self.nreplicates[i] for i in ind])
