#!/usr/bin/python

#MACHINE = 'trestles'
MACHINE = 'gordon'

#DEFAULTPPN = 32
DEFAULTPPN = 16
#DEFAULTPMEMGB = 1.8
#DEFAULTPMEMGB = 3.8
DEFAULTPMEMMB = 3500
#MEMORYLIMIT = 0
MEMORYLIMIT = 1

# Adam suggested these defaults:
# default queue: normal
# default nodes|ppn: 1:32
# default walltime: 01:00:00

# THISDIR = '/users/sdsc/kenneth/info/trestles'
#THISDIR = '/var/spool/torque'
#THISDIR = '/opt/torque'
THISDIR = '/home/catalina/production'
# ACCOUNTFILTER = '/opt/torque/triton_submitfilter.pl'
#ACCOUNTFILTER = '/home/servers/trestles/bin/trestles_submitfilter.pl'
#ACCOUNTFILTER = '/opt/torque/trestles_submitfilter.pl'
#ACCOUNTFILTER = '/home/servers/trestles/bin/trestles_submitfilter.pl'
ACCOUNTFILTER = '/home/servers/gordon/bin/gordon_submit_filter.pl'
SHOWACCOUNTS = '/home/servers/gordon/bin/show_accounts.pl'
#ACCOUNTFILTER = None
#SHOWACCOUNTS = None

import sys
import re
import os
import pwd
import subprocess
import copy
import optparse
import string

#[kenneth@trestles bin]$ ./show_accounts.pl
#ID name      project      used     available
#--------------------------------------------
#kenneth      tgu247       0        100000
#kenneth      use300       26       250000
#kenneth      tgu241       0        100000

showaccounts_pat = r"-----\s+(?P<username>\S+)\s+(?P<project>\S+)\s+"
showaccounts_reo = re.compile(showaccounts_pat)

sys.path.append(THISDIR)

#import joblimits
#import joblimitsnew as joblimits
import joblimits

def changeaddprops (removelist=[],addlist=[],nodereq=""):
    #remove bad properties, add good ones 'shared' property to the nodes req
    # for line_index nodes_tuple[0], take the last nodes=
    # req, and change/add the 'shared' property.
    for removeproperty in removelist:
        remove_reo = re.compile(':' + removeproperty)
        nodereq = remove_reo.sub('',nodereq)
    for addproperty in addlist:
        add_reo = re.compile(':' + addproperty)
        if add_reo.search(nodereq) == None:
            nodereq = nodereq + ':' + addproperty
    return nodereq

changeqos = 0
line_list = []
nodecount = 0
duration_sec = 0
queuename = None
#queuename = 'normal'
QOS = None
foundstatement = 0
foundwalltime = 0
username = pwd.getpwuid(os.geteuid())[0]
account = None
# directives dictionary: { <option letter> : { 'value' : <value string>,
#                                              'source' : <commandline|scriptline>,
#                                              'linenum' : <None|line number>
#                                            },
#                        }
ddict = {}

#The directive prefix string will be determined in order of preference from:
#
#The value of the -C option argument if the option is specified on the
#command line.
#
#The value of the environment variable PBS_DPREFIX if it is defined.
#
#The four character string #PBS.
for envkey in os.environ.keys():
    #sys.stderr.write("%s=%s\n" % (envkey, os.environ[envkey]))
    if envkey == 'PBS_DPREFIX' and os.environ[envkey] != '#PBS':
        sys.stderr.write("%s=%s not allowed\n" % (envkey, os.environ[envkey]))
        sys.exit(1)

comment_pat = r"(?P<allline>^#.*$)"
comment_reo = re.compile(comment_pat)
#pbs_pat = r"(?P<allline>^#PBS\s*(?P<directive>-(?P<option>.)\s*(?P<body>.*))$)"
pbs_pat = r"(?P<allline>^#PBS\s*(?P<directive>-(?P<option>.)\s*(?P<body>\S*))\s*$)"
pbs_reo = re.compile(pbs_pat)
lline_pat = r"^#PBS\s*-l\s+.*$"
lline_reo = re.compile(lline_pat)
goodlline_pat = r"^#PBS\s*-l\s+nodes=\d+:ppn=\d+(:exclusive|:shared)*,walltime=[:\d]+\s*$"
goodlline_reo = re.compile(goodlline_pat)
# looks like spaces in the directive body are not allowed
# qsub throws a 'directive error'
nodes_pat = r".*(?P<nodes>nodes=(?P<nodespec>.*)),*"
nodes_reo = re.compile(nodes_pat)
nodespec_pat = r"^((?P<countname>\d+|\S+?))(:(?P<ppn>ppn=\d+))*(:(?P<properties>\S+))*$"
nodespec_reo = re.compile(nodespec_pat)
totalmem_pat = r".*(?P<nodes>mem=(?P<totalmemspec>.*)),*"
totalmem_reo = re.compile(totalmem_pat)
pmem_pat = r".*(?P<nodes>pmem=(?P<pmemspec>.*)),*"
pmem_reo = re.compile(pmem_pat)
count_reo = re.compile(r"\d+")
nodename_reo = re.compile(r"[-a-zA-Z0-9]+")
whitespace_reo = re.compile(r"^\s*$")
#walltime_pat = r"walltime=((?P<hours>\d+):)?((?P<minutes>\d+):)?(?P<seconds>\d+)"
walltime_pat = r"walltime=(((?P<hours>\d+):)?((?P<minutes>\d+):))?(?P<seconds>\d+)"
walltime_reo = re.compile(walltime_pat)
qos_reo = re.compile(r"QOS=(?P<value>.*)")
preempting_reo = re.compile(r"Catalina_preempting=(?P<value>.*)")
run_at_risk_reo = re.compile(r"Catalina_run_at_risk=(?P<value>.*)")
bind_reo = re.compile(r"Catalina_do_not_start=(?P<value>.*)")
cancel_reo = re.compile(r"Catalina_do_not_cancel=(?P<value>.*)")
usage_reo = re.compile(r"Catalina_node_usage=(?P<value>.*)")
maxhops_reo = re.compile(r"Catalina_maxhops=(?P<value>.*)")

baddash_reo = re.compile(r"-(?P<letter>[lqvC]).*")

nodecount = None
totalwall = None
qosfound = 0
run_at_riskfound = 0
queuefound = 0
accountfound = 0
claccountfound = 0
lastdirective_index = None
foundvariables = 0

aflines_list = []
for line in sys.stdin.readlines():
    aflines_list.append(line)

if joblimits.warnusers_dict.has_key(username):
    for line in aflines_list:
        sys.stdout.write(line)
    sys.exit(0)

# should inherit env from current process
# shell defaults to false: os.execvp...
#af_obj = subprocess.Popen([ACCOUNTFILTER] + sys.argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
#stdoutdata, stderrdata = af_obj.communicate(input=''.join(aflines_list))
#if af_obj.returncode != 0:
#    sys.stderr.write(stderrdata + "\n")
#    sys.exit(af_obj.returncode)
#joblines_list = re.findall(r"(.*\n*)", stdoutdata)

joblines_list = aflines_list

# set username, QOS, queue, nodes line
# take the last directive line, before script statements

llines_list = []
nodereq_list = []
walltime_list = []
totalmem_list = []
pmem_list = []
otherresources_list = []
foundstatement = 0
foundlline = 0
lastdirective_index = None
usagevalue = None
#for line_index in range(len(joblines_list)):
for line_index,line in enumerate(joblines_list):
    #sys.stderr.write("JOBFILTER: (%s)\n" % (line,))
    #line = joblines_list[line_index]
    if foundstatement != 0:
        #PBS lines after first statement are ignored, according to jobfilter.pl
        continue
    pbs_mo = None
    pbs_mo = pbs_reo.match(line)
    if pbs_mo != None:
        #sys.stderr.write("directive (%s)\n" % (pbs_mo.group('allline'),) )
        # find last nodes line
        #PBS -l walltime=1:630,nodes=1+dash-0-1,walltime=630,mem=320kb
        # qsub seems to take the first walltime across lines and
        # the last nodes...need to test what happens on a real system.
        lastdirective_index = line_index
        if pbs_mo.group('option') == 'v':
            foundvariables = 1
            if pbs_mo.groupdict()['body'] != None:
                ddict['v'] = { 'value' : pbs_mo.group('body'),
                               'source' : 'scriptline',
                               'linenum' : line_index}
                req_list = pbs_mo.group('body').split(',')
                ddict['v']['req_list'] = req_list
                for req in req_list:
                    qos_mo = None
                    qos_mo = qos_reo.match(req)
                    if qos_mo != None:
                        qosfound = 1
                        QOS = qos_mo.group('value')
                        # QOS allowed to this user?
                        #if not qos_mo.group('value') in joblimits.userqos_dict['DEFAULT']:
                        #    if not joblimits.userqos_dict.has_key(username) or \
                        #      not qos_mo.group('value') in joblimits.userqos_dict[username]:
                        #        sys.stderr.write("user (%s) does not have access to QOS (%s)\n" % (username, req))
                        #        sys.exit(1)
                        #sys.stderr.write("Setting QOS (%s)\n" % (QOS,))
                        ddict['v']['QOS'] = QOS
                    usage_mo = None
                    usage_mo = usage_reo.match(req)
                    if usage_mo != None:
                        usagefound = 1
                        usagevalue = usage_mo.group('value')
                        ddict['v']['usage'] = usagevalue
                    run_at_risk_mo = None
                    run_at_risk_mo = run_at_risk_reo.match(req)
                    if run_at_risk_mo != None:
                        run_at_riskfound = 1
                        ddict['v']['run_at_risk'] = run_at_risk_mo.group('value')
                    #else:
                    #    sys.stderr.write("No QOS in (%s)\n" % (req,))
                    preempting_mo = None
                    preempting_mo = preempting_reo.match(req)
                    if preempting_mo != None:
                        sys.stderr.write("Preemption not currently supported (%s)\n" % (req,))
                        sys.exit(1)
        elif pbs_mo.group('option') == 'l':
            llines_list.append((line_index, pbs_mo.group('allline')))
            if pbs_mo.groupdict()['body'] != None:
                ddict['l'] = { 'value' : pbs_mo.group('body'),
                               'source' : 'scriptline',
                               'linenum' : line_index}
                req_list = pbs_mo.group('body').split(',')
                ddict['l']['req_list'] = req_list
                for req in req_list:
                    nodes_mo = None
                    nodes_mo = nodes_reo.match(req)
                    if nodes_mo != None:
                        if nodes_mo.groupdict()['nodespec'] != None:
                            nodereq_list.append((line_index,req))
                    walltime_mo = None
                    walltime_mo = walltime_reo.match(req)
                    if walltime_mo != None:
                        walltime_list.append((line_index,req))
                    totalmem_mo = None
                    totalmem_mo = totalmem_reo.match(req)
                    if totalmem_mo != None:
                        totalmem_list.append((line_index,req))
                    pmem_mo = None
                    pmem_mo = pmem_reo.match(req)
                    if pmem_mo != None:
                        pmem_list.append((line_index,req))
                    if nodes_mo == None and walltime_mo == None and totalmem_mo == None and pmem_mo == None:
                        # this is not nodes= nor walltime=
                        otherresources_list.append((line_index,req))
        # reject array jobs for now
        if pbs_mo.group('option') == 't':
            sys.stderr.write("array jobs not supported at this time")
            sys.exit(1)
        # find last -q line
        if pbs_mo.group('option') == 'q':
            if pbs_mo.groupdict()['body'] != None:
                ddict['q'] = { 'value' : pbs_mo.group('body'),
                               'source' : 'scriptline',
                               'linenum' : line_index}
                queuename = pbs_mo.group('body')
                queuefound = 1
        # find last -a line
        if pbs_mo.group('option') == 'A':
            if pbs_mo.groupdict()['body'] != None:
                ddict['A'] = { 'value' : pbs_mo.group('body'),
                               'source' : 'scriptline',
                               'linenum' : line_index}
                account = pbs_mo.group('body')
                accountfound = 1
    else:
        #sys.stderr.write("pbs_mo is None (%s)\n" % (line,))
        comment_mo = None
        comment_mo = comment_reo.match(line)
        whitespace_mo = None
        whitespace_mo = whitespace_reo.match(line)
        if comment_mo != None:
            #sys.stderr.write("comment_mo != None (%s)\n" % (line,))
            pass
        elif whitespace_mo != None:
            #sys.stderr.write("whitespace_mo != None (%s)\n" % (line,))
            pass
        else:
            # not a comment nor #PBS nor whitespace, so a statement
            #sys.stderr.write("found statement (%s)\n" % (line,))
            foundstatement = 1
            lastdirective_index = line_index - 1
            break

#sys.stderr.write("JOBFILTER: ddict (%s)\n" % (ddict,))
# handle multiple -l, multiple nodes=, multiple walltime=
# assume last nodes= and last walltime= across all
# -l lines is desired, generate single #PBS -l 

if len(llines_list) >= 1:
    ddict['l'] = { 'value' : None,
                   'source' : 'scriptline',
                   'req_list' : None,
                   'linenum' : None}
    new_resource_list = []
    if len(nodereq_list) >= 1:
        nodes_mo = None
        nodes_mo = nodes_reo.match(nodereq_list[-1][1])
        if nodes_mo != None:
            new_resource_list.append(nodereq_list[-1][1])
            if nodes_mo.groupdict()['nodespec'] != None:
                #nodereq_list.append((line_index,req))
            
                nodespec_list = nodes_mo.group('nodespec').split('+')
                nodecount = 0
                proccount = 0
                for nodespec in nodespec_list:
                    nodespec_mo = None
                    nodespec_mo = nodespec_reo.match(nodespec)
                    if nodespec_mo != None:
                         if nodespec_mo.group('properties') != None:
                             properties_list = nodespec_mo.group('properties').split(':')
                         count_mo = None
                         count_mo = count_reo.match(nodespec_mo.group('countname'))
                         nodename_mo = None
                         nodename_mo = nodename_reo.match(nodespec_mo.group('countname'))
                         if count_mo != None:
                             nodecount = nodecount + int(nodespec_mo.group('countname'))
                             if nodespec_mo.group('ppn') == None:
                                 proccount = proccount + int(nodespec_mo.group('countname')) * int(DEFAULTPPN)
                             else:
                                 ppnname,ppnvalue = string.split(nodespec_mo.group('ppn'), '=')
                                 proccount = proccount + int(nodespec_mo.group('countname')) * int(ppnvalue)
                         elif nodename_mo != None:
                             nodecount = nodecount + 1
                             if nodespec_mo.group('ppn') == None:
                                 proccount = proccount + 1 * int(DEFAULTPPN)
                             else:
                                 ppnname,ppnvalue = string.split(nodespec_mo.group('ppn'), '=')
                                 proccount = proccount + 1 * int(ppnvalue)
                         else:
                             sys.stderr.write("jobfilter.py failed to parse resource request (%s)" % (pbs_mo.group('allline'),))
                             sys.exit(1)
                ddict['l']['nodecount'] = nodecount
    if len(walltime_list) >= 1:
        walltime_mo = None
        walltime_mo = walltime_reo.match(walltime_list[-1][1])
        if walltime_mo != None:
            new_resource_list.append(walltime_list[-1][1])
            #walltime_tuple = (line_index,req)
            #walltime_list.append((line_index,req))
            #foundwalltime = 1
            totalwall = 0
            if walltime_mo.groupdict()['hours'] != None:
                totalwall = totalwall + 3600 * int(walltime_mo.group('hours'))
            if walltime_mo.groupdict()['minutes'] != None:
                totalwall = totalwall + 60 * int(walltime_mo.group('minutes'))
            if walltime_mo.groupdict()['seconds'] != None:
                totalwall = totalwall + int(walltime_mo.group('seconds'))
            ddict['l']['totalwall'] = totalwall
    if len(pmem_list) >= 1:
        pmem_mo = None
        pmem_mo = pmem_reo.match(pmem_list[-1][1])
        if pmem_mo != None:
            new_resource_list.append(pmem_list[-1][1])
            ddict['l']['pmem'] = pmem_mo.group('pmemspec')
    if len(totalmem_list) >= 1:
        totalmem_mo = None
        totalmem_mo = totalmem_reo.match(totalmem_list[-1][1])
        if totalmem_mo != None:
            new_resource_list.append(totalmem_list[-1][1])
            ddict['l']['totalmem'] = totalmem_mo.group('totalmemspec')
    req_list = new_resource_list + map(lambda x: x[1], otherresources_list)
    ddict['l']['req_list'] = req_list
    if len(llines_list) > 1 or len(nodereq_list) > 1 or len(walltime_list) > 1:
        # generate single -l
        #sys.stderr.write("Multiple -l or node= or walltime= detected.\n")
        new_resource_body = ','.join(req_list)
        #sys.stderr.write("Modifying to single -l spec (#PBS -l %s)\n" % new_resource_body)
        ddict['l']['value'] = new_resource_body
        
        #sys.stderr.write("req_list (%s)\n" % (ddict['l']['req_list'],))
        # comment out old -l lines
        for line_index, line in llines_list:
            newreqline = '#' + joblines_list[line_index]
            joblines_list[line_index] = newreqline
        llines_list = []
        # insert new #PBS -l
        ddict['l']['linenum'] = lastdirective_index + 1
        #sys.stderr.write("ddict['l']['linenum'] (%s)\n" % ddict['l']['linenum'])
        llines_list = [(lastdirective_index + 1, ddict['l']['value'])]
        newjoblines_list = joblines_list[:lastdirective_index+1] + ['#PBS -l ' + ddict['l']['value'] + "\n",] + joblines_list[lastdirective_index+1:]
        joblines_list = copy.deepcopy(newjoblines_list)
        lastdirective_index = lastdirective_index + 1


    else:
        # use the existing one for ddict
        pbs_mo = pbs_reo.match(llines_list[-1][1])
        if pbs_mo.groupdict()['body'] != None:
            ddict['l']['value'] = pbs_mo.group('body')

if lastdirective_index == None:
    lastdirective_index = 0

# command line directives override script directives
# parse command line args
# for command line, qsub takes all -l, last walltime, last nodes in effect
# for command line, qsub only takes last -v
# for command line, qsub only takes last -q
# for command line, qsub only takes last -C
# can't modify, so exit, if bad
parser = optparse.OptionParser()
parser.add_option("-W", action="store_true", dest="dashW")
parser.add_option("-V", action="store_true", dest="dashV")
parser.add_option("-I", action="store_true", dest="dashI")
parser.add_option("-l", action="append", type="string", dest="dashl")
parser.add_option("-v", action="store", type="string", dest="dashv")
parser.add_option("-q", action="store", type="string", dest="dashq")
parser.add_option("-A", action="store", type="string", dest="dashA")
parser.add_option("-C", action="store", type="string", dest="dashC")
parser.add_option("-o", action="store", type="string", dest="dasho")
parser.add_option("-e", action="store", type="string", dest="dashe")
parser.add_option("-N", action="store", type="string", dest="dashN")
parser.add_option("-j", action="store", type="string", dest="dashj")
parser.remove_option("-h")
parser.add_option("-h", action="store_true", dest="dashh")
parser.add_option("-X", action="store_true", dest="dashX")
(options, optargs) = parser.parse_args()
if options.dashC != None and options.dashC !='#PBS':
    sys.stderr.write("-C is not #PBS\n")
    sys.exit(1)
if options.dashq != None:
    queuename = options.dashq
    queuefound = 1
    ddict['q'] = { 'value' : options.dashq,
                   'source' : 'commandline',
                   'linenum' : None}
if options.dashA != None:
    account = options.dashA
    claccountfound = 1
    ddict['A'] = { 'value' : options.dashA,
                   'source' : 'commandline',
                   'linenum' : None}
clnodereq_list = []
clwalltime_list = []
clpmem_list = []
cltotalmem_list = []
clnodes = 0
clprocs = 0
clwalltime = 0
clpmem = 0
cltotalmem = 0
clvars = 0
if options.dashl != None:
    req_list = []
    for lelement in options.dashl:
        req_list = req_list + lelement.split(',')
        #if not ddict.has_key('l'):
        #    ddict['l'] = { 'value' : lelement,
        #                   'source' : 'commandline',
        #                   'linenum' : None}
        ddict['l'] = { 'value' : string.join(req_list,','),
                       'source' : 'commandline',
                       'linenum' : None}
        ddict['l']['clreq_list'] = req_list
        ddict['l']['req_list'] = req_list

    foundnodereq = 0
    foundwalltimereq = 0
    foundpmemreq = 0
    foundtotalmemreq = 0
    for req in req_list:
        nodes_mo = None
        nodes_mo = nodes_reo.match(req)
        if nodes_mo != None:
            clnodereq_list.append((None,req))
            if foundnodereq > 0:
                sys.stderr.write("only one -l nodes= allowed!\n")
                sys.exit(1)
            else:
                foundnodereq = 1
            nodecount = 0
            proccount = 0
            if nodes_mo.groupdict()['nodespec'] != None:
                nodespec_list = nodes_mo.group('nodespec').split('+')
                for nodespec in nodespec_list:
                    nodespec_mo = None
                    nodespec_mo = nodespec_reo.match(nodespec)
                    if nodespec_mo != None:
                         #if nodespec_mo.group('properties') == None:
                         #    if queuename == 'shared':
                         #        sys.stderr.write("-l nodes=<nodes>:ppn=<ppn>:shared is required\n")
                         #        if not joblimits.warnusers_dict.has_key(username):
                         #            sys.exit(1)
                         #    elif queuename == 'normal':
                         #        sys.stderr.write("-l nodes=<nodes>:ppn=<ppn>:exclusive is required\n")
                         #        if not joblimits.warnusers_dict.has_key(username):
                         #            sys.exit(1)
                         #    else:
                         #        sys.stderr.write("Could not parse (%s) for queue (%s)\n" % (nodespec,queuename))
                         #        sys.exit(1)
                         #properties_list = nodespec_mo.group('properties').split(':')
                         #if queuename == 'shared' and (not 'shared' in properties_list \
                         #  or 'exclusive' in properties_list):
                         #    sys.stderr.write("-l nodes=<nodes>:ppn=<ppn>:shared is required\n")
                         #    if not joblimits.warnusers_dict.has_key(username):
                         #        sys.exit(1)
                         #elif queuename == 'normal' and (not 'exclusive' in properties_list \
                         #  or 'shared' in properties_list):
                         #    sys.stderr.write("-l nodes=<nodes>:ppn=<ppn>:exclusive is required\n")
                         #    if not joblimits.warnusers_dict.has_key(username):
                         #        sys.exit(1)
                         if nodespec_mo.group('properties') != None:
                             properties_list = nodespec_mo.group('properties').split(':')
                         count_mo = None
                         count_mo = count_reo.match(nodespec_mo.group('countname'))
                         nodename_mo = None
                         nodename_mo = nodename_reo.match(nodespec_mo.group('countname'))
                         if count_mo != None:
                             nodecount = nodecount + int(nodespec_mo.group('countname'))
                             if nodespec_mo.group('ppn') == None:
                                 proccount = proccount + int(nodespec_mo.group('countname')) * int(DEFAULTPPN)
                             else:
                                 ppnname,ppnvalue = string.split(nodespec_mo.group('ppn'), '=')
                                 proccount = proccount + int(nodespec_mo.group('countname')) * int(ppnvalue)
                         elif nodename_mo != None:
                             nodecount = nodecount + 1
                             if nodespec_mo.group('ppn') == None:
                                 proccount = proccount + 1 * int(DEFAULTPPN)
                             else:
                                 ppnname,ppnvalue = string.split(nodespec_mo.group('ppn'), '=')
                                 proccount = proccount + 1 * int(ppnvalue)
                         else:
                             sys.stderr.write("jobfilter.py failed to parse resource request (%s)" % (pbs_mo.group('allline'),))
                             sys.exit(1)
                         clnodes = 1
                         if nodespec_mo.group('ppn') == None:
                             clprocs = 0
                         else:
                             clprocs = 1
                ddict['l']['nodecount'] = nodecount
                #sys.stderr.write("-l nodecount (%s)!\n" % nodecount)
        walltime_mo = None
        walltime_mo = walltime_reo.match(req)
        if walltime_mo != None:
            clwalltime_list.append((None,req))
            if foundwalltimereq > 0:
                sys.stderr.write("only one -l walltime= allowed!\n")
                sys.exit(1)
            else:
                foundwalltimereq = 1
            clwalltime = 1
            totalwall = 0
            if walltime_mo.groupdict()['hours'] != None:
                totalwall = totalwall + 3600 * int(walltime_mo.group('hours'))
            if walltime_mo.groupdict()['minutes'] != None:
                totalwall = totalwall + 60 * int(walltime_mo.group('minutes'))
            if walltime_mo.groupdict()['seconds'] != None:
                totalwall = totalwall + int(walltime_mo.group('seconds'))
            ddict['l']['totalwall'] = totalwall
        pmem_mo = None
        pmem_mo = pmem_reo.match(req)
        if pmem_mo != None:
            clpmem_list.append((None,req))
            if foundpmemreq > 0:
                sys.stderr.write("only one -l pmem= allowed!\n")
                sys.exit(1)
            else:
                foundpmemreq = 1
            clpmem = 1
            ddict['l']['pmem'] = pmem_mo.group('pmemspec')
        totalmem_mo = None
        totalmem_mo = totalmem_reo.match(req)
        if totalmem_mo != None:
            cltotalmem_list.append((None,req))
            if foundtotalmemreq > 0:
                sys.stderr.write("only one -l mem= allowed!\n")
                sys.exit(1)
            else:
                foundtotalmemreq = 1
            cltotalmem = 1
            ddict['l']['totalmem'] = totalmem_mo.group('totalmemspec')

# command line -v overrides...
if options.dashv != None:
    clvars = 1
    qoselementfound = 0
    bindelementfound = 0
    cancelelementfound = 0
    usageelementfound = 0
    req_list = options.dashv.split(',')
    ddict['v'] = { 'value' : options.dashv,
                   'source' : 'commandline',
                   'linenum' : None}
    ddict['v']['req_list'] = req_list
    # find last Catalina_do_not_start, Catalina_node_usage and QOS

    for req in req_list:
        bind_mo = bind_reo.match(req)
        cancel_mo = cancel_reo.match(req)
        usage_mo = usage_reo.match(req)
        qos_mo = qos_reo.match(req)
        run_at_risk_mo = None
        run_at_risk_mo = run_at_risk_reo.match(req)
        preempting_mo = preempting_reo.match(req)
        if bind_mo != None:
            bindelementfound = 1
            bindvalue = bind_mo.group('value')
        if cancel_mo != None:
            cancelelementfound = 1
            cancelvalue = cancel_mo.group('value')
        if usage_mo != None:
            usageelementfound = 1
            usagevalue = usage_mo.group('value')
        if qos_mo != None:
            qoselementfound = 1
            #qosvalue = qos_mo.group('value')
            QOS = qos_mo.group('value')
            ddict['v']['QOS'] = QOS
            #if not qosvalue in joblimits.userqos_dict['DEFAULT']:
            #    if not joblimits.userqos_dict.has_key(username) or \
            #      not qosvalue in joblimits.userqos_dict[username]:
            #        sys.stderr.write("user (%s) does not have access to QOS (%s)\n" % (username, req))
            #        sys.exit(1)
        if run_at_risk_mo != None:
            run_at_riskfound = 1
            ddict['v']['run_at_risk'] = run_at_risk_mo.group('value')
        if preempting_mo != None:
            sys.stderr.write("Preemption not currently supported (%s)\n" % (req,))
            sys.exit(1)
    if qoselementfound == 0:
        sys.stderr.write("-v QOS=<qos>... required\n")
        # queuename = options.dashq
        # queuefound = 1
        sys.stderr.write("-v QOS=<qos>... required\n")
        if queuefound == 1 and joblimits.queueqos_dict.has_key(queuename):
            sys.stderr.write("for queue (%s): -v QOS=%s\n" % (queuename,joblimits.queueqos_dict[queuename]))
        sys.exit(1)
    if queuename == 'shared':
        #if bindelementfound == 0 or bindvalue != '1':
        #    sys.stderr.write("-q shared requires -v Catalina_do_not_start=1\n")
        #    if not joblimits.warnusers_dict.has_key(username):
        #        sys.exit(1)
        #if cancelelementfound == 0 or cancelvalue != '1':
        #    sys.stderr.write("-q shared requires -v Catalina_do_not_cancel=1\n")
        #    if not joblimits.warnusers_dict.has_key(username):
        #        sys.exit(1)
        #if (usageelementfound == 0 or usagevalue != 'shared') and QOS != '4':
        #    sys.stderr.write("-q shared requires -v Catalina_node_usage=shared")
        #    if not joblimits.warnusers_dict.has_key(username):
        #        sys.exit(1)
        pass
    if queuename == 'normal':
        if bindelementfound != 0 and bindvalue == '1':
            sys.stderr.write("-q normal forbids -v Catalina_do_not_start=1\n")
            if not joblimits.warnusers_dict.has_key(username):
                sys.exit(1)
        if cancelelementfound != 0 and cancelvalue == '1':
            sys.stderr.write("-q normal forbids -v Catalina_do_not_cancel=1\n")
            if not joblimits.warnusers_dict.has_key(username):
                sys.exit(1)
        #if usageelementfound != 0 and usagevalue == 'shared':
        #    sys.stderr.write("-q normal forbids -v Catalina_node_usage=shared")
        #    if not joblimits.warnusers_dict.has_key(username):
        #        sys.exit(1)
        if run_at_riskfound != 0 and int(ddict['v']['run_at_risk']) >= 1:
            sys.stderr.write("-q normal forbids -v Catalina_run_at_risk=1")
            if not joblimits.warnusers_dict.has_key(username):
                sys.exit(1)

#if '-I' in sys.argv:
# Apparently, with -I and a job script, submit filter is run three times:
# - with just command line args plus command line -l as script directive
# - with command line args and script directives, including any conflicting
#   -l directives
# - with command line args and script directives in argv, script -l
#   replaces both command line and script directive
#   only script -l is presented as script directive
#[kenneth@rocks-133 trestles]$ qsub -I -q shared -l nodes=2:ppn=3 testjob
#Starting jobfilter!
#sys.argv (['/var/spool/torque/jobfilter.py', '-I', '-q', 'shared', '-l', 'nodes=2:ppn=3', 'testjob'])
##PBS -l nodes=2:ppn=3
#
#
#Exiting...
#Starting jobfilter!
#sys.argv (['/var/spool/torque/jobfilter.py', '-I', '-q', 'shared', '-l', 'nodes=2:ppn=3', 'testjob'])
##PBS -q normal -l nodes=1:ppn=2:exclusive,walltime=02:02:630 -v Catalina_test_var=testing,QOS=2,TORQUETEST=testing,CATTEST=testing
#
#Exiting...
#Starting jobfilter!
#sys.argv (['/var/spool/torque/jobfilter.py', '-q', 'normal', '-l', 'nodes=1:ppn=2:exclusive,walltime=02:02:630', '-v', 'Catalina_test_var=testing,QOS=2,TORQUETEST=testing,CATTEST=testing'])
##PBS -l nodes=1:ppn=2:exclusive,walltime=02:02:630
#
#
#Exiting...
#qsub: waiting for job 853.rocks-133.sdsc.edu to start
#qsub: job 853.rocks-133.sdsc.edu ready
#
#[kenneth@test-0-1 ~]$


if options.dashI != None:
    jobtype = 'dashI'
    if len(optargs) > 0:
        # don't support job script with -I...
        sys.stderr.write("unrecognized argument: %s with -I\n" % (optargs,))
        sys.exit(1)
    if options.dashl == None:
        sys.stderr.write("-I requires -l nodes=...,walltime=...\n")
        sys.exit(1)
    #if options.dashv == None:
    #    #sys.stderr.write("-q shared -I requires -v QOS=<qos>,Catalina_node_usage=shared #QOS values of 0,1,2...\n")
    #    sys.stderr.write("-q shared -I requires -v QOS=<qos> #QOS values of 0,1,2...\n")
    #    sys.stderr.write("-q normal -I requires -v QOS=<qos> #QOS values of 0,1,2...\n")
    #    sys.exit(1)
    if clnodes == 0:
        sys.stderr.write("-I requires -l nodes=...,walltime=...\n")
        sys.exit(1)
    if clwalltime == 0:
        sys.stderr.write("-I requires -l nodes=...,walltime=...\n")
        sys.exit(1)
    if options.dashq == None:
        sys.stderr.write("-I requires -q <queuename>\n")
        sys.exit(1)
    #if options.dashq == 'shared' and clpmem == 0 and cltotalmem ==0:
    #    sys.stderr.write("-I -q shared requires -l mem=... or pmem=...\n")
    #    sys.exit(1)
else:
    jobtype = 'nodashI'

# check the job request
# set defaults
if not ddict.has_key('q'):
    ddict['q'] = { 'value' : 'normal',
                   'source' : 'default',
                   'linenum' : lastdirective_index + 1}
    #sys.stderr.write("Failed to find -q, setting queue to %s\n" % (ddict['q']['value'],))
    newjoblines_list = joblines_list[:lastdirective_index+1] + ['#PBS -q ' + ddict['q']['value'] + "\n",] + joblines_list[lastdirective_index+1:]
    joblines_list = copy.deepcopy(newjoblines_list)
    lastdirective_index = lastdirective_index + 1
if not ddict.has_key('A'):
    if SHOWACCOUNTS == None:
        accountvalue = 'noaccount'
    else:
        showaccounts_output = os.popen(SHOWACCOUNTS).read()
        showaccounts_mo = None
        showaccounts_mo = showaccounts_reo.search(showaccounts_output)
        accountvalue = showaccounts_mo.group('project')
        if showaccounts_mo != None:
            ddict['A'] = { 'value' : showaccounts_mo.group('project'),
                           'source' : 'default',
                           'linenum' : lastdirective_index + 1}
            #sys.stderr.write("Failed to find -A, setting account to %s\n" % (ddict['A']['value'],))
            newjoblines_list = joblines_list[:lastdirective_index+1] + ['#PBS -A ' + ddict['A']['value'] + "\n",] + joblines_list[lastdirective_index+1:]
            joblines_list = copy.deepcopy(newjoblines_list)
            lastdirective_index = lastdirective_index + 1
        else:
            sys.stderr.write("showaccounts output (%s)\n" % (showaccounts_output,))
            sys.stderr.write("failed to find default account\n")
            sys.exit(1)
if joblimits.queueprop_dict.has_key(ddict['q']['value']):
    queueproperty = joblimits.queueprop_dict[ddict['q']['value']][0]
#if ddict['q']['value'] == 'normal':
#    queueproperty = 'exclusive'
#elif ddict['q']['value'] == 'shared':
#    queueproperty = 'shared'
else:
    sys.stderr.write("failed to recognize queue (%s)\n" % (ddict['q']['value'],))
    sys.exit(1)
changequeue = None
if not ddict.has_key('l'):
    #sys.stderr.write("ddict has no 'l'\n")
    #queueproperty = joblimits.queueprop_dict[ddict['q']['value']][0]
    if ddict['q']['value'] == 'normal':
        ddict['l'] = { 'value' : "nodes=1:ppn=%s:%s,walltime=01:00:00" % (DEFAULTPPN,queueproperty),
                       'source' : 'default',
                       'linenum' : lastdirective_index + 1,
                       'req_list' : ["nodes=1:ppn=%s:%s" % (DEFAULTPPN,queueproperty),'walltime=01:00:00',"mem=%smb" % (DEFAULTPPN * DEFAULTPMEMMB,)],
                       'nodecount' : 1,
                       'totalwall' : 3600,
                     }
    elif ddict['q']['value'] == 'vsmp':
        ddict['l'] = { 'value' : "nodes=1:ppn=16:%s,walltime=01:00:00" % (queueproperty,),
                       'source' : 'default',
                       'linenum' : lastdirective_index + 1,
                       'req_list' : ["nodes=1:ppn=16:%s" % (queueproperty,),'walltime=01:00:00',"mem=%smb" % (16 * DEFAULTPMEMMB,)],
                       'nodecount' : 1,
                       'totalwall' : 3600,
                     }
    else:
        ddict['l'] = { 'value' : "nodes=1:ppn=%s,walltime=01:00:00" % (DEFAULTPPN,),
                       'source' : 'default',
                       'linenum' : lastdirective_index + 1,
                       'req_list' : ["nodes=1:ppn=%s" % (DEFAULTPPN,),'walltime=01:00:00',"mem=%smb" % (DEFAULTPPN * DEFAULTPMEMMB,)],
                       'nodecount' : 1,
                       'totalwall' : 3600,
                     }
    #sys.stderr.write("Failed to find -l, setting node,walltime request to %s\n" % (ddict['l']['value'],))
    newjoblines_list = joblines_list[:lastdirective_index+1] + ['#PBS -l ' + ddict['l']['value'] + "\n",] + joblines_list[lastdirective_index+1:]
    joblines_list = copy.deepcopy(newjoblines_list)
    lastdirective_index = lastdirective_index + 1
else:
    changel = None
    new_req_list = []
    #sys.stderr.write("ddict['l']['req_list'] (%s)\n" % (ddict['l']['req_list'],))
    #sys.stderr.write("ddict['l']['source'] (%s)\n" % (ddict['l']['source'],))
    #sys.stderr.write("ddict['l'] (%s)\n" % (ddict['l'],))
    for req in ddict['l']['req_list']:
        #sys.stderr.write("req (%s)\n" % (req,))
        nodes_mo = None
        nodes_mo = nodes_reo.match(req)
        #if nodes_mo != None:
        if nodes_mo != None and nodes_mo.groupdict()['nodespec'] != None:
            proccount = 0
      
            nodespec_list = nodes_mo.group('nodespec').split('+')
            #sys.stderr.write("nodespec_list (%s)\n" % (nodespec_list,))
            newnodespec_list = []
            for nodespec in nodespec_list:
                #sys.stderr.write("nodespec (%s)\n" % nodespec)

                nodespec_mo = None
                nodespec_mo = nodespec_reo.match(nodespec)
                if nodespec_mo != None:
                    if nodespec_mo.group('ppn') == None:
                        ppnvalue = 1 * int(DEFAULTPPN)
                        proccount = proccount + 1 * int(DEFAULTPPN)
                    else:
                        ppnname,ppnvalue = string.split(nodespec_mo.group('ppn'), '=')
                        proccount = proccount + 1 * int(ppnvalue)
                    ppn_string = "ppn=%s" % ppnvalue
                    countname_string = nodespec_mo.group('countname')
                    if nodespec_mo.group('properties') != None:
                        properties_list = nodespec_mo.group('properties').split(':')
                    else:
                        properties_list = []
                    #sys.stderr.write("properties_list (%s)\n" % (properties_list,))
                    #sys.stderr.write("nodepsec (%s)\n" % (nodespec,))
                    #sys.stderr.write("nodepsec_mo.group('countname') (%s)\n" % (nodespec_mo.group('countname'),))
                    #sys.stderr.write("nodepsec_mo.group('ppn') (%s)\n" % (nodespec_mo.group('ppn'),))
                    #sys.stderr.write("nodepsec_mo.group('properties') (%s)\n" % (nodespec_mo.group('properties'),))
                    if joblimits.queueprop_dict[ddict['q']['value']][0] == None:
                        found_queueproperty = 1
                    else:
                        found_queueproperty = 0
                    found_flashproperty = 0
                    flashproperty = None
                    badqproperty = None
                    badqproperty_list = []
                    #sys.stderr.write("last-4: properties_list (%s)\n" % (properties_list,))
                    for qp in properties_list:
                        if qp == joblimits.queueprop_dict[ddict['q']['value']][0]:
                            found_queueproperty = 1
                        if qp in ['noflash', 'flash', 'bigflash']:
                            found_flashproperty = 1
                            flashproperty = qp
                        if qp not in joblimits.queueprop_dict[ddict['q']['value']]:
                            badqproperty = qp
                            badqproperty_list.append(qp)
                        #else:
                        #    sys.stderr.write("good qp (%s)\n" % qp)
                        #if ddict['q']['value'] == 'normal' and qp == 'vsmp':
                        #    badqproperty = qp
                        #if ddict['q']['value'] == 'vsmp' and qp == 'native':
                        #    badqproperty = qp
                    #sys.stderr.write("last-3: properties_list (%s)\n" % (properties_list,))
                    if badqproperty != None:
                        #sys.stderr.write("ddict['l']['source'] (%s)\n" % ddict['l']['source'])
                        if ddict['l']['source'] == 'commandline':
                            sys.stderr.write("%s not supported with -q %s\n" % (badqproperty_list, ddict['q']['value']))
                            sys.exit(1)
                        else:
                            newprop_list = []
                            for qp in properties_list:
                                #if qp != badqproperty:
                                if qp not in badqproperty_list:
                                    newprop_list.append(qp)
                            properties_list = newprop_list
                            #if len(newprop_list) > 0:
                            #    new_properties = string.join(newprop_list,':')
                            #    nodespec = nodespec_mo.group('countname') + ':' + ppnvalue + ':' + new_properties
                            #    properties_list = newprop_list
                            #else:
                            #    nodespec = nodespec_mo.group('countname') + ':' + ppnvalue
                    #sys.stderr.write("badqproperty_list (%s)\n" % (badqproperty_list,))
                    #sys.stderr.write("last-2: properties_list (%s)\n" % (properties_list,))
                    if ddict['q']['value'] in ['normal','shared']:
                        if found_flashproperty == 0:
                            #sys.stderr.write("found_flashproperty == 0)\n")
                            if ddict['l']['source'] == 'commandline':
                                # assume user knows to specify flash
                                pass
                            else:
                                # removing flash properties, so get rid
                                # of flash addition
                                nodespec = nodespec + ":%s" % 'flash'
                                properties_list.append('flash')
                                changel = 1
                                pass
                        elif flashproperty == 'noflash':
                            #sys.stderr.write("nodespec removing noflash)\n")
                            # generate ndoespec without noflash
                            noflash_list = []
                            for qp in properties_list:
                                if qp != 'noflash':
                                    noflash_list.append(qp)
                            if len(noflash_list) > 0:
                               # sys.stderr.write("properties_list (%s)\n" % (properties_list,))
                               # sys.stderr.write("noflash_list (%s)\n" % (noflash_list,))
                                noflash_properties = string.join(noflash_list,':')
                                #nodespec = nodespec_mo.group('countname') + ':' + ppnvalue + ':' + noflash_properties
                            properties_list = noflash_list
                            #else:
                            #    nodespec = nodespec_mo.group('countname') + ':' + ppnvalue
                    #elif found_flashproperty == 1:
                    #    sys.stderr.write("noflash/flash/bigflash not supported with -q %s\n" % ddict['q']['value'])
                    #    sys.exit(1)
                    #sys.stderr.write("nodespec (%s)\n" % (nodespec,))
                    #sys.stderr.write("last-1: properties_list (%s)\n" % (properties_list,))
                    #sys.stderr.write(" properties_list (%s)\n" % (properties_list,))
                    if found_queueproperty == 0:
                        #sys.stderr.write("found_queueproperty == 0\n")
                        if ddict['l']['source'] == 'commandline':
                            if ddict['q']['value'] == 'normal' and 'vsmp' in properties_list:
                                sys.stderr.write("Please use -q vsmp for access to vsmp nodes\n")
                                sys.exit(1)
                            else:
                                sys.stderr.write("-q %s requires -l nodes with property %s\n" % (ddict['q']['value'],joblimits.queueprop_dict[ddict['q']['value']][0]))
                                sys.exit(1)
                        else:
                            #if ddict['q']['value'] == 'normal' and 'vsmp' in properties_list:
                            #    changequeue = 'vsmp'
                            #    queuename = 'vsmp'
                            #    ddict['q']['value'] = 'vsmp'
                            #    changeqos = 1
                            #    QOS = joblimits.queueqos_dict['vsmp'][0]
                            #    #sys.stderr.write("1. QOS (%s)\n" % QOS)
                            #    new_req = req
                            #else:
                            #    #sys.stderr.write("adding required node property (%s)\n" % joblimits.queueprop_dict[ddict['q']['value']][0])
                            #    new_req = req + ":%s" % joblimits.queueprop_dict[ddict['q']['value']][0]
                            #    properties_list.append(joblimits.queueprop_dict[ddict['q']['value']][0])
                            #    changel = 1
                            #new_req = req + ":%s" % joblimits.queueprop_dict[ddict['q']['value']][0]
                           # sys.stderr.write("nodespec (%s)\n" % (nodespec,))
                            #nodespec = nodespec + ":%s" % joblimits.queueprop_dict[ddict['q']['value']][0]
                            properties_list.append(joblimits.queueprop_dict[ddict['q']['value']][0])
                            changel = 1
                    #else:
                        #sys.stderr.write("found_queueproperty != 0\n")
                        #new_req = req
                    #    nodespec = nodespec
                    #sys.stderr.write("last: properties_list (%s)\n" % (properties_list,))
                    nodespec = countname_string + ':' + ppn_string + ':' + string.join(properties_list,':')
                else:
                    sys.stderr.write("jobfilter failed parse (%s)\n" % (req,))
                    sys.exit(1)
                newnodespec_list.append(nodespec)
            new_req = "nodes=" + string.join(newnodespec_list,'+')

        else:
            #if nodes_mo != None:
            #    sys.stderr.write("nodes_mo.groupdict()['nodespec'] (%s) \n" % (nodes_mo.groupdict()['nodespec'],))
            #else:
            #    sys.stderr.write("nodes_mo == None\n")
            new_req = req
        #sys.stderr.write("new_req (%s)\n" % new_req)
        new_req_list.append(new_req)
    ddict['l']['req_list'] = new_req_list
    #sys.stderr.write("req_list (%s)\n" % (ddict['l']['req_list'],))
            
    #if not ddict['l'].has_key('nodecount') or not ddict['l'].has_key('totalwall') or (not ddict['l'].has_key('totalmem') and not ddict['l'].has_key('pmem')):
    if not ddict['l'].has_key('nodecount') or not ddict['l'].has_key('totalwall') or (not ddict['l'].has_key('totalmem') ):
        #sys.stderr.write("req_list (%s)\n" % (ddict['l']['req_list'],))
        #sys.stderr.write("ddict['l'] (%s)\n" % (ddict['l'],))
        if not ddict['l'].has_key('nodecount'):
            ddict['l']['req_list'].append("nodes=1:ppn=16:%s" % queueproperty)
            ddict['l']['nodecount'] = 1
            sys.stderr.write("Failed to find -l nodes, setting node request to %s\n" % ('nodes=1:ppn=32',))
            changel = 1
        if not ddict['l'].has_key('totalwall'):
            ddict['l']['req_list'].append("walltime=01:00:00")
            ddict['l']['totalwall'] = 3600
            changel = 1
            #sys.stderr.write("Failed to find -l walltime, setting walltime request to %s\n" % ('walltime=01:00:00',))
        #if MEMORYLIMIT == 1 and not ddict['l'].has_key('totalmem') and not ddict['l'].has_key('pmem'):
        if MEMORYLIMIT == 1 and (not ddict['l'].has_key('totalmem') and not usagevalue == 'exclusive'):
            changel = 1
            #if MACHINE == 'gordon':
            #    mempercpu = 3.8
            #else:
            #    mempercpu = 1.8
            #sys.stderr.write("failed to find mem or pmem limit.  Setting to 2gb * cpu\n")
            #sys.stderr.write("failed to find mem or pmem limit.  Setting to %sgb * cpu\n" % mempercpu)
            # FIXME need to test to make sure this works.
            #if queuename == 'vsmp':
            #    memcount = DEFAULTPMEMMB * proccount
            #    if ddict['l']['source'] == 'commandline':
            #        sys.stderr.write("failed to find mem limit. example: -l ...,mem=%smb\n" % memcount)
            #        sys.exit(1)
            #    else:
            #        sys.stderr.write("failed to find mem limit. Setting to %smb * cpu\n" % DEFAULTPMEMMB)
            #        ddict['l']['req_list'].append("mem=%smb" % memcount)
            #        ddict['l']['totalmem'] = "%smb" % memcount
    if not changel == None:
        # change -l 
        ddict['l']['value'] = ','.join(ddict['l']['req_list'])
        #sys.stderr.write("l value req_list (%s)\n" % (ddict['l']['req_list'],))
        #sys.stderr.write("l value (%s)\n" % (ddict['l']['value'],))
        # comment out old -l lines
        for line_index, line in llines_list:
            newreqline = '#' + joblines_list[line_index]
            joblines_list[line_index] = newreqline
        llines_list = []
        llines_list = [(lastdirective_index + 1, ddict['l']['value'])]
        ddict['l']['linenum']  = lastdirective_index + 1
        newjoblines_list = joblines_list[:lastdirective_index+1] + ['#PBS -l ' + ddict['l']['value'] + "\n",] + joblines_list[lastdirective_index+1:]
        joblines_list = copy.deepcopy(newjoblines_list)
        lastdirective_index = lastdirective_index + 1

queuename = ddict['q']['value']
nodecount = ddict['l']['nodecount']
#sys.stderr.write("final -1 nodecount (%s)\n" % (nodecount,))
totalwall = ddict['l']['totalwall']
account = ddict['A']['value']

# special check for hvd107.  they may be submitting many two-week
# jobs.  we want to run these in QOS 5, to limit running job
# count to 512.
#twoweeks = 14 * 24 * 3600
#twodays = 2 * 24 * 3600
#if account in ['hvd107','use300'] and totalwall > twodays:
#    # change QOS to 5
#    changeqos = 1
#    QOS = 5

if not ddict.has_key('v'):
    # construct -v line
    # set bogus reservation binding for shared jobs, so catalina does
    # not schedule them; use pbs_sched instead.
    newreq_list = []
    if MACHINE == 'gordon':
        if ddict['q']['value'] in ['vsmp','ionode']:
            # set QOS according to queueqos_dict
            changeqos = 1
            QOS = joblimits.queueqos_dict[ddict['q']['value']][0]
            #sys.stderr.write("2. QOS (%s)\n" % QOS)
        
    if ddict['q']['value'] == 'shared':
        #newreq_list.append("Catalina_do_not_start=1")
        #newreq_list.append("Catalina_do_not_cancel=1")
        newreq_list.append("Catalina_node_usage=shared")
    else:
        #sys.stderr.write("appending exclusive in not found v found usage section\n")
        newreq_list.append("Catalina_node_usage=exclusive")
    #if joblimits.userqos_dict.has_key(username):
    #    newreq_list.append("QOS=%s" % joblimits.userqos_dict[username][0])
    #else:
    #    newreq_list.append("QOS=%s" % joblimits.userqos_dict['DEFAULT'][0])
    if changeqos == 1:
        newreq_list.append("QOS=%s" % QOS)
        defaultqos = QOS
        #sys.stderr.write("3. QOS (%s)\n" % QOS)
    else:
        if joblimits.userqos_dict.has_key(username):
            newreq_list.append("QOS=%s" % joblimits.userqos_dict[username][0])
            defaultqos = joblimits.userqos_dict[username][0]
        elif joblimits.__dict__.has_key('queueqos_dict') and joblimits.queueqos_dict.has_key(ddict['q']['value']):
            queueqos = joblimits.queueqos_dict[ddict['q']['value']][0]
            #sys.stderr.write("no -v setting queueqos to (%s)\n" % queueqos)
            newreq_list.append("QOS=%s" % queueqos)
            defaultqos = queueqos
        else:
            newreq_list.append("QOS=%s" % joblimits.userqos_dict['DEFAULT'][0])
            defaultqos = joblimits.userqos_dict['DEFAULT'][0]
    if MACHINE == 'gordon':
        if re.search(r"bigflash",ddict['l']['value']) == None and ddict['l']['nodecount'] <= 16:
            #sys.stderr.write("Catalina_maxhops not found, setting max_hops to 0\n")
            newreq_list.append("Catalina_maxhops=0")
        else:
            #sys.stderr.write("Catalina_maxhops not found, setting max_hops to None\n")
            newreq_list.append("Catalina_maxhops=None")
    #nodecount = ddict['l']['nodecount']
    #newjoblines_list = joblines_list[:lastdirective_index] + ['#PBS -v ' + ','.join(newreq_list) + "\n",] + joblines_list[lastdirective_index:]
    #joblines_list = copy.deepcopy(newjoblines_list)
    ddict['v'] = { 'value' : ','.join(newreq_list),
                   'source' : 'default',
                   'req_list' : newreq_list,
                   'linenum' : lastdirective_index + 1,
                   'QOS': defaultqos,
                 }
    #sys.stderr.write("Failed to find -v, setting -v to %s\n" % (ddict['v']['value'],))
    newjoblines_list = joblines_list[:lastdirective_index+1] + ['#PBS -v ' + ddict['v']['value'] + "\n",] + joblines_list[lastdirective_index+1:]
    joblines_list = copy.deepcopy(newjoblines_list)
    lastdirective_index = lastdirective_index + 1
else:
    usageelementfound = 0
    qoselementfound = 0
    maxhopselementfound = 0
    for req in ddict['v']['req_list']:
        usage_mo = usage_reo.match(req)
        qos_mo = qos_reo.match(req)
        maxhops_mo = maxhops_reo.match(req)
        if usage_mo != None:
            usageelementfound = 1
            usagevalue = usage_mo.group('value')
        if qos_mo != None:
            qoselementfound = 1
            if changeqos != 1:
                #if joblimits.queueqos_dict.has_key(qos_mo.group('value')):
                if qos_mo.group('value') in joblimits.queueqos_dict[queuename]:
                    QOS = qos_mo.group('value')
                    ddict['v']['QOS'] = QOS
                    #sys.stderr.write("setting QOS (%s)\n" % (QOS,))
                else:
                    sys.stderr.write("queuename (%s)  does not have access to QOS (%s)\n" % (queuename, QOS))
                    sys.exit(1)
            #QOS = qos_mo.group('value')
        if maxhops_mo != None:
            maxhopselementfound = 1
            maxhops = maxhops_mo.group('value')
    #if usageelementfound == 0:
    #    if queuename == 'shared':
    #        ddict['v']['req_list'].append("Catalina_node_usage=shared")
    #    else:
    #        ddict['v']['req_list'].append("Catalina_node_usage=exclusive")
    #else:
    #    if queuename == 'normal':
    #        newreq_list = []
    #        for req in ddict['v']['req_list']:
    #        ddict['v']['req_list'].append("Catalina_node_usage=exclusive")

    if qoselementfound == 0:
        if changeqos == 1:
            ddict['v']['req_list'].append("QOS=%s" % QOS)
            ddict['v']['QOS'] = QOS
        elif joblimits.userqos_dict.has_key(username):
            ddict['v']['req_list'].append("QOS=%s" % joblimits.userqos_dict[username][0])
            ddict['v']['QOS'] = joblimits.userqos_dict[username][0]
        elif joblimits.__dict__.has_key('queueqos_dict') and joblimits.queueqos_dict.has_key(ddict['q']['value']):
            queueqos = joblimits.queueqos_dict[ddict['q']['value']][0]
            #sys.stderr.write("found -v setting queueqos to (%s)\n" % queueqos)
            ddict['v']['req_list'].append("QOS=%s" % queueqos)
            ddict['v']['QOS'] = queueqos
        else:
            ddict['v']['req_list'].append("QOS=%s" % joblimits.userqos_dict['DEFAULT'][0])
            ddict['v']['QOS'] = joblimits.userqos_dict['DEFAULT'][0]
    #if maxhopselementfound == 0:
    #    if MACHINE == 'gordon':
    #        if ddict['l']['nodecount'] <= 16:
    #            sys.stderr.write("Catalina_maxhops not found, setting max_hops to 0\n")
    #            ddict['v']['req_list'].append("Catalina_maxhops=0")
    #        else:
    #            sys.stderr.write("Catalina_maxhops not found, setting max_hops to None\n")
    #            ddict['v']['req_list'].append("Catalina_maxhops=None")

queuename = ddict['q']['value']
nodecount = ddict['l']['nodecount']
totalwall = ddict['l']['totalwall']
account = ddict['A']['value']
if ddict['v'].has_key('QOS') and ddict['v']['QOS'] != None:
    if changeqos != 1:
        QOS = ddict['v']['QOS']
        #sys.stderr.write("setting QOS (%s)\n" % QOS)
else:
    QOS = None

# check ACLs
if nodecount == None or nodecount == 0:
    #sys.stderr.write("nodecount (%s)\n" % (nodecount,))
    sys.stderr.write("failed to find node count\n")
    sys.exit(1)
if totalwall == None:
    sys.stderr.write("failed to find wallclock limit\n")
    sys.exit(1)
if account == None:
    sys.stderr.write("failed to find -A <account>\n")
    sys.exit(1)
else:
    #cmd_list = [ACCOUNTFILTER] + [" -A ", account, " -u ", username] + sys.argv[1:]
    if ACCOUNTFILTER != None:
        cmd_list = [ACCOUNTFILTER] + ["-A", account, "-u", username]
        #sys.stderr.write("%s\n" % (cmd_list,))
        #sys.stderr.write("%s\n" % (sys.argv,))
        af_obj = subprocess.Popen(cmd_list ,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        stdoutdata, stderrdata = af_obj.communicate(input=''.join(aflines_list))
        if af_obj.returncode != 0:
            sys.stderr.write(stderrdata + "\n")
            sys.exit(af_obj.returncode)
        #joblines_list = re.findall(r"(.*\n*)", stdoutdata)

if QOS != None and changeqos == 0:
    # QOS allowed to this account?
    if not QOS in joblimits.accountqos_dict['DEFAULT']:
        if not joblimits.accountqos_dict.has_key(account) or \
          not QOS in joblimits.accountqos_dict[account]:
            # QOS access for this account not found,
            # look for user access to this QOS
            if not QOS in joblimits.userqos_dict['DEFAULT']:
                if not joblimits.userqos_dict.has_key(username) or \
                  not QOS in joblimits.userqos_dict[username]:
                    sys.stderr.write("user (%s), account (%s) does not have access to QOS (%s)\n" % (username, account, QOS))
                    sys.exit(1)
    # QOS allowed for the queuename?
    if not QOS in joblimits.queueqos_dict[queuename]:
        sys.stderr.write("queuename (%s)  does not have access to QOS (%s)\n" % (queuename, QOS))
        sys.exit(1)

# check joblimits
if not joblimits.queuenode_dict.has_key(queuename):
    sys.stderr.write("queue (%s) not recognized by jobfilter.py\n" % (queuename,))
    sys.exit(1)

# for vsmp, check proccount modulo 16
if queuename == 'vsmp':
    #sys.stderr.write("proccount (%s)\n" % (proccount, ))
    quotient, remainder = divmod(proccount,16)
    if not remainder == 0:
        sys.stderr.write("-q vsmp requires ppn in multiples of 16\n")
        sys.exit(1)

#sys.stderr.write("ddict['q'] (%s)\n" % (ddict['q'],))
#if queuename == 'normal' and not changequeue == None:
if not changequeue == None:
    #sys.stderr.write("queuename == normal, changequeue (%s)\n" % changequeue)
    line_index = ddict['q']['linenum']

    #newjoblines_list = joblines_list[:lastdirective_index+1] + ['#PBS -v ' + ddict['v']['value'] + "\n",] + joblines_list[lastdirective_index+1:]
    newjoblines_list = joblines_list[:line_index] + ["#PBS -q " + changequeue + "\n",] + joblines_list[line_index+1:]
    #sys.stderr.write("newjoblines_list (%s)\n" % (newjoblines_list,))
    joblines_list = copy.deepcopy(newjoblines_list)
    #sys.stderr.write("joblines_list (%s)\n" % (joblines_list,))
    
#sys.stderr.write("final nodecount (%s)\n" % (nodecount,))
if nodecount > joblimits.queuenode_dict[queuename]:
    if not joblimits.usernode_dict.has_key(username):
        sys.stderr.write("node count (%s) exceeds queue (%s) limit (%s)\n" % \
          (nodecount, queuename, joblimits.queuenode_dict[queuename]))
        sys.exit(1)
    else:
        if nodecount > joblimits.usernode_dict[username]:
            sys.stderr.write("node count (%s) exceeds user (%s) limit (%s)\n" % \
              (nodecount, username, joblimits.usernode_dict[username]))
            sys.exit(1)
if totalwall <= 0:
    sys.stderr.write("walltime must be greater than 00:00:00!\n")
    sys.exit(1)
if totalwall > joblimits.queuewall_dict[queuename]:
    if not joblimits.userwall_dict.has_key(username):
        sys.stderr.write("wallclock limit (%s) exceeds queue (%s) limit (%s)\n" % \
          (totalwall, queuename, joblimits.queuewall_dict[queuename]))
        sys.exit(1)
    else:
        if totalwall > joblimits.userwall_dict[username]:
            sys.stderr.write("wallclock limit (%s) exceeds user (%s) limit (%s)\n" % \
              (totalwall, username, joblimits.userwall_dict[username]))
            sys.exit(1)

# change/add
# queue and node properties
#if clnodes == 0:
#    #line_index = nodes_tuple[0]
#    if ddict['l'].has_key('linenum') and ddict['l']['linenum'] != None:
#        line_index = int(ddict['l']['linenum'])
#    else:
#        sys.stderr.write("failed to find line number of -l\n")
#        sys.exit(1)
#    pbs_mo = None
#    pbs_mo = pbs_reo.match(joblines_list[line_index])
#    # skip, if nodes were specified on command line
#    if pbs_mo != None and clnodes == 0:
#        new_req_list = []
#        #req_list = pbs_mo.group('body').split(',')
#        req_list = ddict['l']['value'].split(',')
#        for req in req_list:
#            nodes_mo = None
#            nodes_mo = nodes_reo.match(req)
#            if nodes_mo != None:
#                if nodes_mo.groupdict()['nodespec'] != None:
#                    new_nodespec_list = []
#                    nodespec_list = nodes_mo.group('nodespec').split('+')
#                    for nodespec in nodespec_list:
#                        if queuename == 'shared':
#                            #newnodespec = changeaddprops(['exclusive',],['shared',],nodespec)
#                            #new_nodespec_list.append(newnodespec)
#                            new_nodespec_list.append(nodespec)
#                        elif queuename == 'normal':
#                            #newnodespec = changeaddprops(['shared',],['exclusive',],nodespec)
#                            #new_nodespec_list.append(newnodespec)
#                            new_nodespec_list.append(nodespec)
#                        else:
#                            sys.stderr.write("failed to find queue (%s)\n" % (queuename,))
#                            sys.exit(1)
#                    newreq = 'nodes=' + '+'.join(new_nodespec_list)
#            else:
#                newreq = req
#            new_req_list.append(newreq)
#        joblines_list[line_index] = '#PBS -l ' + ','.join(new_req_list) + "\n"
#    else:
#        if clnodes == 0:
#            sys.stderr.write("failed to parse -l line (%s)\n" % (joblines_list[line_index],))
#            sys.exit(1)

# adjust variables (-v ....) qsub seems to only take the last -v line...
# triton_submitfilter.pl only gives last -v line...
if foundvariables == 1 and ddict['v'].has_key('linenum') and ddict['v']['linenum'] != None:
    line_index = ddict['v']['linenum']
    newreq_list = []
    req_list = ddict['v']['value'].split(',')
    qoselementfound = 0
    bindelementfound = 0
    cancelelementfound = 0
    usageelementfound = 0
    hopselementfound = 0
    for req in req_list:
        #if re.match(r"Catalina_do_not_start=.*",req):
        #    bindelementfound = 1
        #    if queuename == 'shared':
        #        newreq_list.append("Catalina_do_not_start=1")
        #    else:
        #        newreq_list.append(req)
        #if re.match(r"Catalina_do_not_cancel=.*",req):
        #    cancelelementfound = 1
        #    if queuename == 'shared':
        #        newreq_list.append("Catalina_do_not_cancel=1")
        #    else:
        #        # skip do_not_cancel directive
        #        sys.stderr.write("not using (%s) for queue (%s)\n" % (req, queuename))
        if re.match(r"Catalina_node_usage=.*",req):
            usageelementfound = 1
            #if queuename == 'shared' and (QOS == None or QOS != '4'):
            #    newreq_list.append("Catalina_node_usage=shared")
            #else:
            #    newreq_list.append(req)
            if queuename in ['vsmp','ionode']:
                newreq_list.append("Catalina_node_usage=exclusive")
                #newreq_list.append(req)
            if queuename in ['shared',]:
                newreq_list.append("Catalina_node_usage=shared")
            else:
                #sys.stderr.write("appending exclusive in found v found usage section\n")
                newreq_list.append("Catalina_node_usage=exclusive")
        elif re.match(r"QOS=.*",req) and changeqos == 1:
            # do not add old one
            pass
        elif re.match(r"QOS=.*",req):
            if changeqos == 1:
                # do not add the old one to req_list
                pass
            else:
                # add the old one
                qoselementfound = 1
                newreq_list.append(req)
        elif re.match(r"Catalina_maxhops=.*",req):
            hopselementfound = 1
            newreq_list.append(req)
        #elif re.match(r"Catalina_local_admin_priority=.*",req):
        #    pass
        else:
            newreq_list.append(req)
    #if bindelementfound == 0:
    #    if queuename == 'shared':
    #        newreq_list.append("Catalina_do_not_start=1")
    #if cancelelementfound == 0:
    #    if queuename == 'shared':
    #        newreq_list.append("Catalina_do_not_cancel=1")
    if usageelementfound == 0:
        if queuename == 'shared':
            newreq_list.append("Catalina_node_usage=shared")
        elif queuename == 'normal':
            newreq_list.append("Catalina_node_usage=exclusive")
        elif queuename == 'vsmp':
            newreq_list.append("Catalina_node_usage=exclusive")
        elif queuename == 'ionode':
            newreq_list.append("Catalina_node_usage=exclusive")
            #newreq_list.append(req)
    #else:
    #    newreq_list.append("Catalina_node_usage=exclusive")

    if changeqos == 1:
        newreq_list.append("QOS=%s" % QOS)
        #print "QOS (%s)" % QOS
    elif qoselementfound == 0:
        #if joblimits.userqos_dict.has_key(username):
        #    newreq_list.append("QOS=%s" % joblimits.userqos_dict[username][0])
        #else:
        #    newreq_list.append("QOS=%s" % joblimits.userqos_dict['DEFAULT'][0])
       newreq_list.append("QOS=%s" % QOS)
    if hopselementfound == 0 and MACHINE == 'gordon':
        if re.search(r"bigflash",ddict['l']['value']) == None and nodecount <= 16:
            #sys.stderr.write("(%s) Catalina_maxhops not found, setting max_hops to 0\n" % (ddict['l']['value'],))
            newreq_list.append("Catalina_maxhops=0")
        else:
            #sys.stderr.write("Catalina_maxhops not found, setting max_hops to None\n")
            newreq_list.append("Catalina_maxhops=None")
    joblines_list[line_index] = '#PBS -v ' + ','.join(newreq_list) + "\n"

# got to the end, so assume good
#sys.stderr.write("joblines_list (%s)\n" % (joblines_list,))
for jobline in joblines_list:
    sys.stdout.write(jobline)
sys.exit(0)
