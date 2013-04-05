from Experiment.sample import Sample
from Experiment.experiment import *

scale=1   # Overall scale of reactions
nreplicates=1
negRT=1

### Setup samples
e=Experiment()
e.setreagenttemp(4.0)
rpos=0; spos=0;qpos=0
R_MT7=Sample("MT7",e.REAGENTPLATE,rpos,2); rpos=rpos+1
R_Theo=Sample("Theo",e.REAGENTPLATE,rpos,25/7.5); rpos=rpos+1
R_L2b12=Sample("L2b12",e.REAGENTPLATE,rpos,10); rpos=rpos+1
R_L2b12Cntl=Sample("L2b12Cntl",e.REAGENTPLATE,rpos,10); rpos=rpos+1
R_MStop=Sample("MStp",e.REAGENTPLATE,rpos,2); rpos=rpos+1
R_MRT=Sample("MRT",e.REAGENTPLATE,rpos,2); rpos=rpos+1
R_MRTNeg=Sample("MRTNeg",e.REAGENTPLATE,rpos,2); rpos=rpos+1
R_MLigB=Sample("MLigB",e.REAGENTPLATE,rpos,1.25); rpos=rpos+1
R_MLigase=Sample("MLigase",e.REAGENTPLATE,rpos,2); rpos=rpos+1
R_MQA=Sample("MQA",e.REAGENTPLATE,rpos,20.0/12); rpos=rpos+1
R_MQB=Sample("MQB",e.REAGENTPLATE,rpos,20.0/12); rpos=rpos+1

### T7 
templates=[R_L2b12]
#templates=[R_L2b12,R_L2b12Cntl]
nTemplates=len(templates)
nT7=nTemplates*nreplicates
S_T7MINUS=[Sample("R1.T7PLUS.%d"%i,e.SAMPLEPLATE,i+spos) for i in range(nT7)]; spos=spos+nT7
S_T7PLUS=[Sample("R1.T7MINUS.%d"%i,e.SAMPLEPLATE,i+spos) for i in range(nT7)]; spos=spos+nT7
S_T7=S_T7MINUS+S_T7PLUS
for i in range(nreplicates):
    e.stage('T7M',[R_MT7],templates,S_T7MINUS[i*nTemplates:(i+1)*nTemplates],10*scale)
    e.stage('T7P',[R_MT7,R_Theo],templates,S_T7PLUS[i*nTemplates:(i+1)*nTemplates],10*scale)
nT7*=2
e.runpgm("37-15MIN")

## Stop
e.dilute(S_T7,2)
e.stage('Stop',[R_MStop],[],S_T7,20*scale)

### RT
e.dilute(S_T7,2)
nRT=nT7
S_RTPos=[Sample("R1.RT.%d"%i,e.SAMPLEPLATE,i+spos) for i in range(nRT)]; spos=spos+nRT
e.stage('RTPos',[R_MRT],S_T7,S_RTPos,5*scale)

negRT=min(nRT,negRT)
S_RTNeg=[Sample("R1.RTNeg.%d"%i,e.SAMPLEPLATE,i+spos) for i in range(negRT)]; spos=spos+negRT
e.stage('RTNeg',[R_MRTNeg],S_T7[0:negRT],S_RTNeg,5*scale)
S_RT=S_RTPos+S_RTNeg
nRT=len(S_RT)
e.runpgm("TRP-SS")

## Extension
e.dilute(S_RT,5)
nExt=nRT
S_EXT=[Sample("R1.EXT.%d"%i,e.SAMPLEPLATE,i+spos) for i in range(nExt)]; spos=spos+nExt
e.stage('LigAnneal',[R_MLigB],S_RT,S_EXT,10*scale)
e.runpgm("TRP-ANNEAL")

e.dilute(S_EXT,2)
e.stage('Ligation',[R_MLigase],[],S_EXT,20*scale)
e.runpgm("TRP-EXTEND")

## Dilute for qPCR
e.dilute(S_EXT,20)
S_EXTDIL=[Sample("R1.EXTDIL.%d"%i,e.SAMPLEPLATE,i+spos) for i in range(nExt)]; spos=spos+nExt
e.stage('PreQPCR-Dilute',[],S_EXT,S_EXTDIL,200)
        
## qPCR
e.dilute(S_EXTDIL,20.0/8.0)
nQPCR=nExt
S_QPCR_A=[Sample("R1.QPCR.A.%d"%i,e.QPCRPLATE,i+qpos) for i in range(nQPCR)]; qpos=qpos+nQPCR
e.stage('QPCRA',[R_MQA],S_EXTDIL,S_QPCR_A,10)
S_QPCR_B=[Sample("R1.QPCR.B.%d"%i,e.QPCRPLATE,i+qpos) for i in range(nQPCR)]; qpos=qpos+nQPCR
e.stage('QPCRA',[R_MQB],S_EXTDIL,S_QPCR_B,10)
S_QPCR=S_QPCR_A+S_QPCR_B
nQPCR=nQPCR*2

e.w.userprompt("Process complete. Continue to turn off reagent cooler")
e.setreagenttemp(None)

# Save worklist to a file
e.saveworklist("trp1.gwl")
e.savegem("header.gem","trp1.gem")
e.savesummary("trp1.txt")

# Build a script to prefill the reagent wells for testing
pre=Experiment()
print "e=",e,"e.worklist=",e.w,",e.w.l=",e.w.list
print "pre=",pre,"pre.worklist=",pre.w,",pre.w.l=",pre.w.list
allReagents=[R_MT7,R_Theo,R_L2b12,R_L2b12Cntl,R_MStop,R_MRT,R_MRTNeg,R_MLigB,R_MLigase,R_MQA,R_MQB]
# Will add 10ul extra in addition to bringing the currently negative sample volumes to zero
pre.stage('Prefill',[],[],allReagents,20)  
pre.savegem("header.gem","prefill.gem")
pre.savesummary("prefill.txt")
