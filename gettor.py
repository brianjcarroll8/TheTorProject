#!/usr/bin/python2.5
# -*- coding: utf-8 -*-
"""

 gettor.py by Jacob Appelbaum <jacob@appelbaum.net>,
              Christian Fromme <kaner@strace.org>
 This program will hand out Tor via email to supported systems.
 This program is Free Software, see LICENSE for details.

 It is intended to be used in a .forward file as part of a pipe like so:

     cat <<'EOF'> .forward
     |/usr/local/bin/gettor.py
     EOF

 You should have a dist/current/ mirror in a directory that gettor can read.
 Such a mirror can be created like so:

     cd /usr/local/
     rsync -av rsync://rsync.torproject.org/tor/dist/current tor-dist-current/

 You can keep it updated with a cronjob like so:

     MirrorDir=/usr/local/tor-dist-current/
     0 3 * * * rsync -a rsync://rsync.torproject.org/tor/dist/current/ $MirrorDir
 
 You should ensure that for each file and signature pair you wish to 
 distribute, you have created a zip file containing both.

 While this program isn't written in a threaded manner per se, it is designed to function 
 as if it will be called as a pipe many times at once. There is a slight 
 desynchronization with blacklist entry checking and may result in false 
 negatives. This isn't perfect but it is designed to be lightweight. It could 
 be fixed easily with a shared locking system but this isn't implemented yet.

 To clean out the blacklist on a daily basis, install the following cronjob:

     # m h  dom mon dow   command
     1 1 * * * /bin/rm -rf /var/lib/gettor/bl/*

 You'll probably want a directory structure like this owned by uid/gid 'gettor':
    /var/lib/gettor/{bl,pkg}

"""

__program__ = 'gettor.py'
__version__ = '20080914.01'
__url__ = 'https://tor-svn.freehaven.net/svn/tor/trunk/contrib/gettor/'
__author__ = 'Jacob Appelbaum <jacob@appelbaum.net>, Christian Fromme <kaner@strace.org>'
__copyright__ = 'Copyright (c) 2008, Jacob Appelbaum, Christian Fromme'
__license__ = 'See LICENSE for licensing information'

try:
    from future import antigravity
except ImportError:
    antigravity = None

import sys
import os
import gettext
import gettor_blacklist
import gettor_requests
import gettor_responses
import gettor_log
import gettor_config
import gettor_opt
import gettor_packages


# Somewhat poor hack to get what we want: Use different languages for logging
# and for reply mails
# XXX: Change to something more elegant
def switchLocale(newlocale):
    trans = gettext.translation("gettor", "/usr/share/locale", [newlocale])
    trans.install()

def runTests():
    # XXX 
    return True

def installCron(mirror, distdir):
    # XXX: TODO REDO THIS FUNCTION TO USE `crontab -e`
    # XXX: We might want to install a cronjob file to /etc/cron.daily, on
    # system that support it. Also, we should use the mirror from the command
    # line or config file, as well as the distdir from the config to build 
    # the command string
    #comment="\n# Sync Tor software\n"
    #command="0 3 * * * rsync -a rsync://" + mirror + "/tor/dist/current/" 
    #            + distdir + "\n"
    #try:
    #    f = open("/etc/crontab", "a")
    #    f.write(comment + command)
    #    f.close
    #except:
    #    print "Installation failed. Are you root?"
    #    return False
    #print "Cronjob installed: Running every night at three after midnight"
    return True

def processMail(conf, log, logLang, packageList):
    # Get message from stdin
    rawMessage = gettor_requests.getMessage()
    parsedMessage = gettor_requests.parseMessage(rawMessage)
    if not parsedMessage:
        log.info(_("No parsed message. Dropping message."))
        exit(1)
    signature = False
    signature = gettor_requests.verifySignature(rawMessage)
    log.info(_("Signature is: %s") % str(signature))
    replyTo = False
    srcEmail = conf.getSrcEmail()
    # Check package list sanity
    for key, val in packageList.items():
        # Remove invalid packages
        if not os.access(val, os.R_OK):
            log.info(_("Warning: %s not accessable. Removing from list.") % val)
            del packageList[key]
    if len(packageList) < 1:
        log.info(_("Sorry, your package list is unusable."))
        return False

    # XXX TODO: Ensure we have a proper replyTO or bail out (majorly malformed mail).
    replyTo = gettor_requests.parseReply(parsedMessage)

    # Get disired reply language, if any
    replyLang = gettor_requests.parseLocale(parsedMessage)
    if not replyLang:
        replyLang = logLang

    if not signature:
        # Check to see if we've helped them to understand that they need DKIM in the past
        previouslyHelped = gettor_blacklist.blackList(replyTo)
    
    if not replyTo:
        log.info(_("No help dispatched. Invalid reply address for user."))
        return False

    if not signature and previouslyHelped:
        log.info(_("Unsigned messaged to gettor by blacklisted user dropped."))
        return False

    if not signature and not previouslyHelped:
        # Reply with some help and bail out
        gettor_blacklist.blackList(replyTo, True)
        switchLocale(replyLang)
        message = _("""
Hello! This is the "get tor" robot.

Unfortunately, we won't answer you at this address. We only process
requests from email services that support "DKIM", which is an email
feature that lets us verify that the address in the "From" line is
actually the one who sent the mail.

Gmail and Yahoo Mail both use DKIM. You will have better luck sending
us mail from one of those.

(We apologize if you didn't ask for this mail. Since your email is from
a service that doesn't use DKIM, we're sending a short explanation,
and then we'll ignore this email address for the next day or so.
        """)
        switchLocale(logLang)
        gettor_responses.sendHelp(message, srcEmail, replyTo)
        log.info(_("Unsigned messaged to gettor. We issued some help about using DKIM."))
        return True

    if signature:
        log.info(_("Signed messaged to gettor."))
        
        try:
            package = gettor_requests.parseRequest(parsedMessage, packageList)
        except:
            package = None

        if package != None:
            log.info(_("Package: %s selected.") % str(package))
            switchLocale(replyLang)
            message = _("""
Here's your requested software as a zip file. Please unzip the 
package and verify the signature.
            """)
            switchLocale(logLang)
            gettor_responses.sendPackage(message, srcEmail, replyTo, packageList[package])  
            return True
        else:
            switchLocale(replyLang)
            message = [_("Hello, I'm a robot. ")]
            message.append(_("Your request was not understood. Please select one of the following package names:\n"))

            for key in packageList.keys():
                message.append(key + "\n")
            message.append(_("Please send me another email. It only needs a single package name anywhere in the body of your email.\n"))
            switchLocale(logLang)
            gettor_responses.sendHelp(''.join(message), srcEmail, replyTo)
            log.info(_("Signed messaged to gettor. We issued some help about proper email formatting."))
            return True

if __name__ == "__main__":
    # Parse command line, setup config, logging and language
    options, arguments = gettor_opt.parseOpts()
    conf = gettor_config.gettorConf(options.configfile)
    logger  = gettor_log.gettorLogger()
    log = logger.getLogger()
    logLang = conf.getLocale()
    switchLocale(logLang)
    distDir = conf.getDistDir()
    if not os.path.isdir(distDir):
        log.info(_("Sorry, %s is not a directory.") % distDir)
        exit(1)

    packs = gettor_packages.gettorPackages(options.mirror, conf)

    if options.fetchpackages:
        if packs.syncWithMirror() != 0:
            log.error(_("Syncing Tor packages failed."))
            exit(1)
        else:
            log.info(_("Syncing Tor packages done."))
            exit(0)
    if options.preppackages:
        if not packs.buildPackages():
            log.error(_("Building packages failed."))
            exit(1)
        else:
            log.info(_("Building packages done."))
            exit(0)
    if options.runtests:
        if not runTests():
            log.error(_("Tests failed."))
            exit(1)
        else:
            log.info(_("Tests passed."))
            exit(0)
    if options.installcron:
        if not installCron(options.mirror, distDir):
            log.error(_("Installing cron failed"))
            exit(1)
        else:
            log.info(_("Installing cron done."))
            exit(0)
    
    # Main loop
    if not processMail(conf, log, logLang, packs.getPackageList()):
        log.error(_("Processing mail failed."))
        exit(1)

    exit(0)
