#!/opt/splunk/bin/python
# Copyright (C) 2014 MuS
# http://answers.splunk.com/users/2122/mus

# enable / disable logger debug output
myDebug = 'no'

# Changelog
# 18 December 2016 - tested on Splunk 6.5.1
# 19 December 2016 - added logging to splunkd.log / sorting of the result
# 26 February 2018 - minor code fix as requested by Splunk
# 18 August 2018 - exclude inputs from default run, added option to specifiy entities to be reloaded

# import some Python moduls
import splunk
import sys
import os
import splunk.Intersplunk
import re
import logging
import collections
import splunk.rest as rest
from optparse import OptionParser


# get SPLUNK_HOME form OS
SPLUNK_HOME = os.environ['SPLUNK_HOME']

# get myScript name and path
myScript = os.path.basename(__file__)
myPath = os.path.dirname(os.path.realpath(__file__))

# define the logger to write into log file
def setup_logging(n):
    logger = logging.getLogger(n)
    if myDebug == 'yes':
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.ERROR)
    LOGGING_DEFAULT_CONFIG_FILE = os.path.join(SPLUNK_HOME, 'etc', 'log.cfg')
    LOGGING_LOCAL_CONFIG_FILE = os.path.join(
        SPLUNK_HOME, 'etc', 'log-local.cfg')
    LOGGING_STANZA_NAME = 'python'
    LOGGING_FILE_NAME = '%s.log' % myScript
    BASE_LOG_PATH = os.path.join('var', 'log', 'splunk')
    LOGGING_FORMAT = '%(asctime)s %(levelname)-s\t%(module)s:%(lineno)d - %(message)s'
    splunk_log_handler = logging.handlers.RotatingFileHandler(
        os.path.join(SPLUNK_HOME, BASE_LOG_PATH, LOGGING_FILE_NAME), mode='a')
    splunk_log_handler.setFormatter(logging.Formatter(LOGGING_FORMAT))
    logger.addHandler(splunk_log_handler)
    splunk.setupSplunkLogger(logger, LOGGING_DEFAULT_CONFIG_FILE,
                             LOGGING_LOCAL_CONFIG_FILE, LOGGING_STANZA_NAME)
    return logger


# start the logger only if needed
logger = setup_logging('logger started ...')

# starting the main
logger.info('starting the main task ...')

# get key value pairs from user search
keywords, options = splunk.Intersplunk.getKeywordsAndOptions()
logger.debug('got these options: %s ...' % (options))  # logger
# get user option or use a default value
myEntity = options.get('entity', 'safe')
logger.debug('got this entity: %s ...' % (myEntity))  # logger


# getting the sessionKey, owner, namespace
results, dummyresults, settings = splunk.Intersplunk.getOrganizedResults()
results = []  # we don't care about incoming results
logger.info('setting: %s ' % settings)
sessionKey = settings.get('sessionKey', None)  # getting session key but will not log!
owner = settings.get('owner', None)  # getting user / owner
logger.info('using owner: %s ' % owner)
namespace = settings.get('namespace', None)  # getting namespace
logger.info('using namespace: %s ' % namespace)

# setting up empty output list
myList = []

# # debugcode
# import sys, os
# sys.path.append(os.path.join(os.environ['SPLUNK_HOME'],'etc','apps','SA-VSCode','bin'))
# import splunk_debug as dbg
# dbg.enable_debugging(timeout=25)

# getting all the _reload links form the response content
reloadLinks = []  # set empty list
if myEntity == 'safe' or myEntity == 'all':  # reload all entities
    logger.info('reloading all entities ...')
    # get rest response and content
    response, content = rest.simpleRequest('/servicesNS/-/-/admin', sessionKey=sessionKey, method='GET')
    
    if sys.version_info[0] >= 3: 
        content = content.decode()

    for line in content.split('\n'):  # loop throught the content
        logger.info('line: %s ' % line)
        if '_reload' in line:  # _reload link found
            reloadLink = re.findall(r'href\=\"(.+?)\"', line)  # getting the links
            logger.info('reloadLink: %s ' % reloadLink)
            if not reloadLink:  # if no link was found
                logger.info('line did not match ...')
            for name in reloadLink:  # add only capable endpoints / take from debug.py
                logger.info('name: %s' % name)
                logger.info('checking auth-service: ...')
                if 'auth-services' in name:  # refreshing auth causes logout, no reload here!
                    logger.info('found auth-service: stepping forward ...')
                    continue # skip it to be safe
                logger.info('checking cooked: ...')
                if 'cooked' in name:  # refreshing cooked causes splunktcp reset, only when all is requested!
                    if 'all' in myEntity:
                        logger.info('appending final links ...')
                        reloadLinks.append(name)  # appending relaod link to list
                    logger.info('found cooked: stepping forward ...')
                    continue # otherwise skip it to be safe
                logger.info('checking windows: ...')
                if sys.platform == 'win32' and name == 'fifo':
                    # splunkd never loads FIFO on windows, but advertises it anyway
                    logger.info('found windows stuff: stepping forward ...')
                    continue
                logger.info('appending final links ...')
                reloadLinks.append(name)  # appending relaod link to list

else:  # reload all entities
    logger.info('reloading one entities ...')
    # get rest response and content
    myREST = '/servicesNS/-/-/admin/%s' % myEntity
    logger.info('getting reload link from : %s' % myREST)
    response, content = rest.simpleRequest(myREST, sessionKey=sessionKey, method='GET')
    contentnew = content.decode()
    for line in contentnew.split('\n'):  # loop throught the content
        logger.info('line: %s ' % line)
        if '_reload' in line:  # _reload link found
            reloadLink = re.findall(r'href\=\"(.+?)\"', line)  # getting the links
            logger.info('reloadLink: %s ' % reloadLink)
            if not reloadLink:  # if no link was found
                logger.info('line did not match ...')
            for name in reloadLink:  # add only capable endpoints / take from debug.py
                logger.info('name: %s' % name)
                logger.info('appending final links ...')
                reloadLinks.append(name)  # appending relaod link to list

logger.info('final reloadLinks: %s' % reloadLinks)

# reloading the endpoints now
logger.info('reloading the endpoints now ...')
for target in reloadLinks:  # looping through the reload links
    endpointresult = {}  # set empty result dict
    logger.info('reloading the %s endpoints now ...' % target)
    # get rest response and content
    response, content = rest.simpleRequest(target, sessionKey=sessionKey, method='POST')
    endpointresult['endpoint'] = target  # set result endpoint
    endpointresult['status'] = response['status']  # set endpoint reload status
    logger.info('endpointresult: %s' % endpointresult)
    od = collections.OrderedDict(sorted(endpointresult.items()))  # sort the list
    myList.append(od)  # append the ordered results to the list

logger.info('done with the work ...')
logger.info('this is myList: %s' % myList)
logger.info('output the result to splunk> ...')
splunk.Intersplunk.outputResults(myList)  # output the result to splunk
