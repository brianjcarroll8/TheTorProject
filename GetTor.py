#!/usr/bin/python2.5
# -*- coding: utf-8 -*-

__program__ = 'GetTor.py'
__url__ = 'https://tor-svn.freehaven.net/svn/tor/trunk/contrib/gettor/'
__author__ = 'Jacob Appelbaum <jacob@appelbaum.net>, Christian Fromme <kaner@strace.org>'
__copyright__ = 'Copyright (c) 2008, 2009, The Tor Project'
__license__ = 'See LICENSE for licensing information'

try:
    from future import antigravity
except ImportError:
    antigravity = None

import sys

import gettor.gtlog
import gettor.opt
import gettor.config
import gettor.requests
import gettor.responses
import gettor.utils

log = gettor.gtlog.getLogger()

def processFail(conf, rawMessage, sendTo):
    """This routine gets called when something went wrong with the processing"""
    # Keep a copy of the failed email for later reference
    log.info("We'll keep a record of this mail.")
    gettor.utils.dumpMessage(conf, rawMessage)
    # Send out notification to user, if possible
    if not gettor.responses.sendNotification(conf, sendTo):
        log.error("Also failed to send the user a proper notification. :-/")
    else:
        log.info("Failure notification sent to user %s" % sendTo)

def processMail(conf):
    """All mail processing happens here. Processing goes as follows:
    - Parse request. This means: Find out everything we need to reply in 
      an appropriate manner. Reply address, language, package name.
      Also try to find out if the user wants split packages and if he has 
      a valid signature on his mail.
    - Send reply. Use all information gathered from the request and pass
      it on to the reply class/method to decide what to do."""
        
    rawMessage = ""
    replyTo = ""
    log.info("Processing mail..")
    # Retrieve request from stdin
    try:
        request = gettor.requests.requestMail(conf)
        rawMessage = request.getRawMessage()
        replyTo, lang, pack, split, sig, cmdAddr = request.parseMail()
        log.info("Request from %s package %s, lang %s, split %s, cmdaddr %s" \
                    % (replyTo, pack, lang, split, cmdAddr))
        log.info("Signature is %s" % sig)
    except Exception, e:
        log.error("Parsing the request failed.")
        log.error("Here is the exception I saw: %s" % sys.exc_info()[0])
        log.error("Detail: %s" % e) 
        processFail(conf, rawMessage, replyTo)
        return False

    # Ok, information aquired. Initiate reply sequence
    try:
        reply = gettor.responses.Response(conf, replyTo, lang, pack, split, \
                                            sig, cmdAddr)
        if not reply.sendReply():
            log.error("Sending reply failed.")
            processFail(conf, rawMessage, replyTo)
            return False
        return True
    except Exception, e:
        log.error("Sending the reply failed.")
        log.error("Here is the exception I saw: %s" % sys.exc_info()[0])
        log.error("Detail: %s" %e)
        processFail(conf, rawMessage, replyTo)
        raise
        return False

def processOptions(options, conf):
    """Do everything that's not part of parsing a mail. Prepare GetTor usage,
    install files, fetch packages, do some black/whitelist voodoo and so on""" 
    # Order matters!
    if options.insttrans:
        m = gettor.utils.installTranslations(conf, options.i18ndir)
    if options.fetchpackages:
        gettor.utils.fetchPackages(conf, options.mirror)
    if options.preppackages:
        gettor.utils.prepPackages(conf)
    if options.installcron:
        gettor.utils.installCron()
    if options.whitelist:
        gettor.utils.addWhitelistEntry(conf, options.whitelist)
    if options.blacklist:
        gettor.utils.addBlacklistEntry(conf, options.blacklist)
    if options.lookup:
        gettor.utils.lookupAddress(conf, options.lookup)
    if options.clearwl:
        gettor.utils.clearWhitelist(conf)
    if options.clearbl:
        gettor.utils.clearBlacklist(conf)
    if options.cmdpass:
        gettor.utils.setCmdPassword(conf, options.cmdpass)

def main():
    # Parse command line, setup config and logging
    options, arguments = gettor.opt.parseOpts()
    config = gettor.config.Config(options.configfile)
    gettor.gtlog.initialize()

    if sys.stdin.isatty():
        # We separate this because we need a way to know how we reply to the 
        # caller: Send mail or just dump to stdout/stderr.
        processOptions(options, config)
    else:
        # We've got mail
        if processMail(config):
            log.info("Processing mail finished")
        else:
            log.error("Processing mail failed")

    log.info("Done.")

if __name__ == "__main__":
    main()
