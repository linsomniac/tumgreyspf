#!/usr/bin/env python
#
#  Copyright (c) 2004, Sean Reifschneider, tummy.com, ltd.
#  All Rights Reserved.

S_rcsid = '$Id: tumgreyspfsupp.py,v 1.2 2004-08-23 02:06:46 jafo Exp $'


import syslog, os, sys, string, re, time, popen2, urllib, stat


#  default values
defaultConfigFilename = '/var/local/tumgreyspf/config/tumgreyspf.conf'
defaultConfigData = {
		'debugLevel' : 0,
		'defaultSeedOnly' : 0,
		'defaultAllowTime' : 600,
		'configPath' : 'file:///var/local/lib/tumgreyspf/config',
		'greylistDir' : '/var/local/lib/tumgreyspf/data',
		'spfqueryPath' : '/usr/local/lib/tumgreyspf/spfquery',
		}


#################################
class ConfigException(Exception):
	'''Exception raised when there's a configuration file error.'''
	pass


#################################
def loadConfigFile(file, values):
	'''Load the specified config file if it exists, raise ValueError if there
	is an error in the config file.  "values" is a dictionary of default
	config values.  "values" is modified in place, and nothing is returned.'''

	if not os.path.exists(file): return

	try:
		execfile(file, {}, values)
	except Exception, e:
		import traceback
		etype, value, tb = sys.exc_info()
		raise ConfigException, ('Error reading config file "%s": %s'
				% ( file, sys.exc_info()[1] ))

	return()


####################################################################
def processConfigFile(filename = None, config = None, useSyslog = 1,
		useStderr = 0):
	'''Load the specified config file, exit and log errors if it fails,
	otherwise return a config dictionary.'''

	import tumgreyspfsupp
	if config == None: config = tumgreyspfsupp.defaultConfigData
	if filename == None: filename = tumgreyspfsupp.defaultConfigFilename

	try:
		loadConfigFile(filename, config)
	except Exception, e:
		if useSyslog:
			syslog.syslog(e.args[0])
		if useStderr:
			sys.stderr.write('%s\n' % e.args[0])
		sys.exit(1)

	return(config)


#################
class ExceptHook:
   def __init__(self, useSyslog = 1, useStderr = 0):
      self.useSyslog = useSyslog
      self.useStderr = useStderr
   
   def __call__(self, etype, evalue, etb):
      import traceback, string
      tb = traceback.format_exception(*(etype, evalue, etb))
      tb = map(string.rstrip, tb)
      tb = string.join(tb, '\n')
      for line in string.split(tb, '\n'):
         if self.useSyslog:
            syslog.syslog(line)
         if self.useStderr:
            sys.stderr.write(line + '\n')


####################
def setExceptHook():
	sys.excepthook = ExceptHook(useSyslog = 1, useStderr = 1)


####################
def quoteAddress(s):
	'''Quote an address so that it's safe to store in the file-system.
	Address can either be a domain name, or local part.
	Returns the quoted address.'''

	s = urllib.quote(s, '@_-+')
	if s[0] == '.': s = '%2e' + s[1:]
	return(s)


######################
def unquoteAddress(s):
	'''Undo the quoting of an address.  Returns the unquoted address.'''

	return(urllib.unquote(s))


###############################################################
commentRx = re.compile(r'^(.*)#.*$')
def readConfigFile(path, configData = None, configGlobal = {}):
	'''Reads a configuration file from the specified path, merging it
	with the configuration data specified in configData.  Returns a
	dictionary of name/value pairs based on configData and the values
	read from path.'''

	debugLevel = configGlobal.get('debugLevel', 0)
	if debugLevel >= 3: syslog.syslog('readConfigFile: Loading "%s"' % path)
	if configData == None: configData = {}
	nameConversion = {
			'SPFSEEDONLY' : int,
			'GREYLISTTIME' : int,
			'CHECKERS' : str,
			'OTHERCONFIGS' : str,
			'GREYLISTEXPIREDAYS' : float,
			}

	#  check to see if it's a file
	try:
		mode = os.stat(path)[0]
	except OSError, e:
		syslog.syslog('ERROR stating "%s": %s' % ( path, e.strerror ))
		return(configData)
	if not stat.S_ISREG(mode):
		syslog.syslog('ERROR: is not a file: "%s", mode=%s' % ( path, oct(mode) ))
		return(configData)

	#  load file
	fp = open(path, 'r')
	while 1:
		line = fp.readline()
		if not line: break

		#  parse line
		line = string.strip(string.split(line, '#', 1)[0])
		if not line: continue
		data = map(string.strip, string.split(line, '=', 1))
		if len(data) != 2:
			syslog.syslog('ERROR parsing line "%s" from file "%s"'
					% ( line, path ))
			continue
		name, value = data

		#  check validity of name
		conversion = nameConversion.get(name)
		if conversion == None:
			syslog.syslog('ERROR: Unknown name "%s" in file "%s"' % ( name, path ))
			continue

		if debugLevel >= 4: syslog.syslog('readConfigFile: Found entry "%s=%s"'
				% ( name, value ))
		configData[name] = conversion(value)
	fp.close()
	
	return(configData)


####################################################
def lookupConfig(configPath, msgData, configGlobal):
	'''Given a path, load the configuration as dictated by the
	msgData information.  Returns a dictionary of name/value pairs.'''

	debugLevel = configGlobal.get('debugLevel', 0)

	#  set up default config
	configData = {
			'SPFSEEDONLY' : configGlobal.get('defaultSeedOnly'),
			'GREYLISTTIME' : configGlobal.get('defaultAllowTime'),
			'CHECKGREYLIST' : 1,
			'CHECKSPF' : 1,
			'OTHERCONFIGS' : 'envelope_sender,envelope_recipient',
			}

	#  load directory-based config information
	if configPath[:8] == 'file:///':
		if debugLevel >= 3:
			syslog.syslog('lookupConfig: Starting file lookup from "%s"'
					% configPath)
		basePath = configPath[7:]
		configData = {}

		#  load default config
		path = os.path.join(basePath, '__default__')
		if os.path.exists(path):
			if debugLevel >= 3:
				syslog.syslog('lookupConfig: Loading default config: "%s"' % path)
			configData = readConfigFile(path, configData, configGlobal)
		else:
			syslog.syslog(('lookupConfig: No default config found in "%s", '
					'this is probably an install problem.') % path)

		#  load other configs from OTHERCONFIGS
		configsAlreadyLoaded = {}
		didLoad = 1
		while didLoad:
			didLoad = 0
			otherConfigs = string.split(configData.get('OTHERCONFIGS', ''), ',')
			if not otherConfigs or otherConfigs == ['']: break
			if debugLevel >= 3:
				syslog.syslog('lookupConfig: Starting load of configs: "%s"'
						% str(otherConfigs))

			#  SENDER/RECIPIENT
			for cfgType in otherConfigs:
				cfgType = string.strip(cfgType)

				#  skip if already loaded
				if configsAlreadyLoaded.get(cfgType) != None: continue
				configsAlreadyLoaded[cfgType] = 1
				didLoad = 1
				if debugLevel >= 3:
					syslog.syslog('lookupConfig: Trying config "%s"' % cfgType)

				#  SENDER/RECIPIENT
				if cfgType == 'envelope_sender' or cfgType == 'envelope_recipient':
					#  get address
					if cfgType == 'envelope_sender': address = msgData.get('sender')
					else: address = msgData.get('recipient')
					if not address:
						if debugLevel >= 2:
							syslog.syslog('lookupConfig: Could not find %s' % cfgType)
						continue

					#  split address into domain and local
					data = string.split(address, '@', 1)
					if len(data) != 2:
						if debugLevel >= 2:
							syslog.syslog('lookupConfig: Could not find %s address '
									'from "%s", skipping' % ( cfgType, address ))
						continue
					local = quoteAddress(data[0])
					domain = quoteAddress(data[1])

					#  load configs
					path = os.path.join(basePath, cfgType)
					domainPath = os.path.join(path, domain, '__default__')
					localPath = os.path.join(path, domain, local)
					for name in ( domainPath, localPath ):
						if debugLevel >= 3:
							syslog.syslog('lookupConfig: Trying file "%s"' % name)
						if os.path.exists(name):
							configData = readConfigFile(name, configData, configGlobal)

				#  CLIENT IP ADDRESS
				elif cfgType == 'client_address':
					ip = msgData.get('client_address')
					if not ip:
						if debugLevel >= 2:
							syslog.syslog('lookupConfig: Could not find client '
									'address')
					else:
						path = basePath
						for name in [ 'client_address' ] \
								+ list(string.split(ip, '.')):
							path = os.path.join(path, name)
							defaultPath = os.path.join(path, '__default__')
							if debugLevel >= 3:
								syslog.syslog('lookupConfig: Trying file "%s"'
										% defaultPath)
							if os.path.exists(defaultPath):
								configData = readConfigFile(defaultPath, configData,
										configGlobal)
						if debugLevel >= 3:
							syslog.syslog('lookupConfig: Trying file "%s"' % path)
						if os.path.exists(path):
							configData = readConfigFile(path, configData, configGlobal)

				#  unknown configuration type
				else:
					syslog.syslog('ERROR: Unknown configuration type: "%s"'
							% cfgType)

	#  unkonwn config path
	else:
		syslog.syslog('ERROR: Unknown path type in: "%s", using defaults'
				% msgData)

	#  return results
	return(configData)
