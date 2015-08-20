import os 
import sys                                                              
import re 
import imp
import timeit
import subprocess
from PhysicsTools.HeppyCore.framework.config import CFG
class CmsswPreprocessor :
	def __init__(self,configFile,command="cmsRun",prefetch=False) :
		self.configFile=configFile
		self.command=command
		self.prefetch=prefetch
		self.garbageFiles=[]
	def prefetchOneXrootdFile(self,fname):
		tmpdir = os.environ['TMPDIR'] if 'TMPDIR' in os.environ else "/tmp"
		rndchars  = "".join([hex(ord(i))[2:] for i in os.urandom(8)])
		localfile = "%s/%s-%s.root" % (tmpdir, os.path.basename(fname).replace(".root",""), rndchars)
		try:
		    print "Fetching %s to local path %s " % (fname,localfile)
		    start = timeit.default_timer()
		    subprocess.check_output(["xrdcp","-f","-N",fname,localfile])
		    print "Time used for transferring the file locally: %s s" % (timeit.default_timer() - start)
		    return (localfile,True)
		except:
		    print "Could not save file locally, will run from remote"
		    if os.path.exists(localfile): os.remove(localfile) # delete in case of incomplete transfer
		    return (fname,False)
	def maybePrefetchFiles(self,component):
		newfiles = []
		component._preprocessor_tempFiles = []
		for fn in component.files:
		    if self.prefetch and fn.startswith("root://"):
		        (newfile,istemp) = self.prefetchOneXrootdFile(fn)
		        newfiles.append(newfile)
		        if istemp: 
		            component._preprocessor_tempFiles.append(newfile)
		    else:
		        newfiles.append(fn)
		component.files = newfiles
	def endLoop(self,component):
		for fname in component._preprocessor_tempFiles:
		    print "Removing local cache file ",fname
		    os.remove(fname)
		component._preprocessor_tempFiles = []
	def run(self,component,wd,firstEvent,nEvents):
		print wd,firstEvent,nEvents
		if firstEvent != 0: raise RuntimeError, "The preprocessor can't skip events at the moment"
		if nEvents is None:
			nEvents = -1
		self.maybePrefetchFiles(component)
		cmsswConfig = imp.load_source("cmsRunProcess",os.path.expandvars(self.configFile))
		inputfiles= []
		for fn in component.files :
			if not re.match("file:.*",fn) and not re.match("root:.*",fn) :
				fn="file:"+fn
			inputfiles.append(fn)

                # Four cases: 
                # - no options, cmsswConfig with initialize function
                #     run initialize with default parameters
                # - filled options, cmsswConfig with initialize function
                #     pass on options to initialize
                # - no options, classic cmsswConfig
                #     legacy mode
                # - filled options, classic cmsswConfig
                #     legacy mode but warn that options are not passed on

                if hasattr(cmsswConfig, "initialize"):
                        if len(self.options) == 0:                                
                                cmsswConfig.process = cmsswConfig.initialize()                                 
                        else:                                
                                cmsswConfig.process = cmsswConfig.initialize(**self.options)                                 
                else:
                        if len(self.options) == 0:                             
                                pass
                        else:
                                print "WARNING: cmsswPreprocessor received options but can't pass on to cmsswConfig"
                
		cmsswConfig.process.source.fileNames = inputfiles
		cmsswConfig.process.maxEvents.input=nEvents
		#fixme: implement skipEvent / firstevent

		outfilename=wd+"/cmsswPreProcessing.root"
		# for outName in cmsswConfig.process.endpath.moduleNames():
		for module in cmsswConfig.process.endpaths.viewvalues():
			for outName in module.moduleNames():
				out = getattr(cmsswConfig.process,outName)
    			out.fileName = outfilename

		if not hasattr(component,"options"):
			component.options = CFG(name="postCmsrunOptions")
                #use original as primary and new as secondary 
                #component.options.inputFiles= component.files
		#component.options.secondaryInputFiles=[outfilename]

                #use new as primary and original as secondary
                if self.addOrigAsSecondary:
                    component.options.secondaryInputFiles= component.files
		component.options.inputFiles=[outfilename]
                component.files=[outfilename]

		configfile=wd+"/cmsRun_config.py"
		f = open(configfile, 'w')
		f.write(cmsswConfig.process.dumpPython())
		f.close()
		runstring="%s %s >& %s/cmsRun.log" % (self.command,configfile,wd)
		print "Running pre-processor: %s " %runstring
                ret=os.system(runstring)
                if ret != 0:
                     print "CMSRUN failed"
                     exit(ret)
		return component
