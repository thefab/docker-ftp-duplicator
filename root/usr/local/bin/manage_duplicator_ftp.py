#!/bin/env python
# -*- coding: utf-8 -*-
#
#Il ne faudra pas oublier de croner ce shell. Frequence ?
import os
import filecmp
import shutil
import subprocess
import requests
import base64
import json
import hashlib
import fnmatch
import time

# Il faudra mettre des securites partout (consul qui repond pas, etc...)

def now():
    return(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time())))

def add_voie():
    prog = "/usr/local/bin/sprinkler.py"
    dir_voie = "/data/%s" % voie
    cmd = "%s %s" % (prog, dir_voie)
    sub_index = "%d" % setting_index
    if len(subscribers) != 0:
        sub_list = "%s" % subscribers[0]['Directory']
        for subscr in subscribers[1:]:
            sub_list = "%s %s" % (sub_list, subscr['Directory'])
        for subscr in subscribers:
            sub_index = "%s-%d" % (sub_index, subscr['Modify_index'])
        cmd = "%s %s %s" % (cmd, hashlib.md5(sub_index).hexdigest(), sub_list)
    else:
        cmd = "%s %s Trash" % (cmd, hashlib.md5("Trash").hexdigest())
    if settings != {}:
        voies.append({'Name':voie,
                      'Setting_index':setting_index,
                      'Settings':settings,
                      'Subscribers':subscribers,
                      'Circus_status':"None",
                      'Cmd':cmd})
        watched_directories.append(voie)

# Parametres circus
Max_Age = int(os.environ.get("DUPLICATORFTP_CIRCUS_MAX_AGE"))
Max_Age_Variance = int(os.environ.get("DUPLICATORFTP_CIRCUS_MAX_AGE_VARIANCE"))
Graceful_Timeout = int(os.environ.get("DUPLICATORFTP_CIRCUS_GRACEFUL_TIMEOUT"))

# Url pour requeter consul
Consul = os.environ.get("DUPLICATORFTP_CONSUL")
if Consul == None:
    print "%s : Fatal Error : Environment variable " % now() \
          +"DUPLICATORFTP_CONSUL not defined"
    exit(1)

url = "http://%s/v1/kv/ftp_duplicator/?recurse" % Consul
reply = requests.get(url)
if reply.status_code != 200:
    print "%s : Fatal Error : Consul return code %d" % (now(),
                                                        reply.status_code)
    print "     You may need to create url http://%s/v1/kv/ftp_duplicator/" \
          % Consul

    exit(1)

result = reply.json()

# Recuperation des voies a manager et des abonnements dans Consul
voie = ''
voies = []
carriers = []
watched_directories = []
settings = {}
for res in result:
    if res['Key'].startswith('ftp_duplicator/incoming_directories/'):
        lsplit = res['Key'].split('/')
        if lsplit[2] != voie:
            if voie != '' and settings != {}:
                add_voie()
            # Ajout nouvelle voie
            voie = lsplit[2]
        if len(lsplit) == 4 and lsplit[3] == '':
            setting_index = -9999
            subscribers = []
            settings = {}
        if len(lsplit) == 4 and lsplit[3] == 'settings':
            setting_index = res['ModifyIndex']
            if res['Value'] != None:
                settings = json.loads(base64.b64decode(res['Value']))
        if len(lsplit) == 5 and lsplit[4] != '':
            if res['Value'] != None:
                subscr = json.loads(base64.b64decode(res['Value']))
                subscr['Consul_kv'] = res['Key']
                prog2 = "/usr/local/bin/carrier.py"
                if subscr.has_key('consul_service'):
                    # Cas d'un service Consul correspondant a plusieurs machines
                    url = "http://%s/v1/health/service/%s" \
                          % (Consul, subscr['consul_service'])
                    reply2 = requests.get(url)
                    if reply2.status_code != 200:
                        print "%s : Error : Consul return code %d" % (now(),
                              reply2.status_code)
                    result2 = reply2.json()
                    for res2 in result2:
                        subscr2 = subscr.copy()
                        subscr2['HostId'] = res2['Service']['Address']
                        subscr2['Port'] = res2['Service']['Port']
                        subscr2['Name'] = "%s-%s-%s:%d" % (voie, lsplit[4],
                                                           subscr2['HostId'],
                                                           subscr2['Port'])
                        subscr2['Modify_index'] = \
                            res2['Service']['ModifyIndex'] + res['ModifyIndex']
                        subscr2['Directory'] = "/data/%s" % subscr2['Name']
                        cmd = "%s %s %s %s --force_host=%s --force_port=%d" \
                              % (prog2, subscr2['Modify_index'],
                                 subscr2['Consul_kv'], subscr2['Directory'],
                                 subscr2['HostId'], subscr2['Port'])
                        subscr2['Cmd'] = cmd
                        subscribers.append(subscr2.copy())
                        carriers.append(subscr2.copy())
                        watched_directories.append(subscr2['Name'])
                else:
                    subscr['HostId'] = ''
                    subscr['Port'] = ''
                    subscr['Name'] = "%s-%s" %(voie, lsplit[4])
                    subscr['Modify_index'] = res['ModifyIndex']
                    subscr['Directory'] = "/data/%s" % subscr['Name']
                    cmd = "%s %s %s %s" \
                              % (prog2, subscr['Modify_index'],
                                 subscr['Consul_kv'], subscr['Directory'])
                    subscr['Cmd'] = cmd
                    subscribers.append(subscr)
                    carriers.append(subscr)
                    watched_directories.append(subscr['Name'])

# Ajout derniere voie
if voie != '':
    add_voie()

# Creation des users
users = ''
passwords = ''
uids = ''
lifetimes = ''
for voie in voies:
    if users == '':
        users = voie['Settings']['user']
        passwords = voie['Settings']['password']
        uids = str(voie['Settings']['uid'])
        lifetimes = str(voie['Settings']['lifetime'])
    else:
        users = "%s,%s" % (users, voie['Settings']['user'])
        passwords = "%s,%s" % (passwords, voie['Settings']['password'])
        uids = "%s,%s" % (uids, str(voie['Settings']['uid']))
        lifetimes = "%s,%s" % (lifetimes, str(voie['Settings']['lifetime']))

os.environ["AUTOCLEANFTP_USERS"] = users
os.environ["AUTOCLEANFTP_PASSWORDS"] = passwords
os.environ["AUTOCLEANFTP_UIDS"] = uids
os.environ["AUTOCLEANFTP_LIFETIMES"] = lifetimes

os.system("/usr/local/bin/make_users_and_cron.py")

# Creation eventuelle du repertoire /data/tmp
if not os.path.isdir("/data/tmp"):
    print "%s : Directory /data/tmp created" % now()
    os.mkdir("/data/tmp")

# Fabrication du nouveau fichier circus.ini
with open('/tmp/circus.ini', 'w') as new_circus:
    # section [circus]
    new_circus.write("[circus]\n")
    new_circus.write("statsd = False\n")
    new_circus.write("check_delay = 5\n")
    new_circus.write("endpoint = tcp://127.0.0.1:5555\n")
    new_circus.write("pubsub_endpoint = tcp://127.0.0.1:5556\n")
    new_circus.write("\n")
    # ajout des watchers (sprinklers)
    for v in voies:
        new_circus.write("[watcher:sprinkler_%s]\n" % v['Name'])
        new_circus.write("cmd = %s\n" % v['Cmd'])
        new_circus.write("numprocesses = 1\n")
        new_circus.write("stdout_stream.class = FileStream\n")
        new_circus.write("stdout_stream.filename = " + \
                         "/var/log/sprinkler_%s.stdout\n" % v['Name'])
        new_circus.write("stderr_stream.class = FileStream\n")
        new_circus.write("stderr_stream.filename = " + \
                         "/var/log/sprinkler_%s.stderr\n" % v['Name'])
        new_circus.write("copy_env = True\n")
        new_circus.write("graceful_timeout = %d\n" % Graceful_Timeout)
        new_circus.write("max_age = %d\n" % Max_Age)
        new_circus.write("max_age_variance = %d\n" % Max_Age_Variance)
        new_circus.write("\n")
    # ajout des watchers (carriers)
    for c in carriers:
        new_circus.write("[watcher:carrier_%s]\n" % c['Name'])
        new_circus.write("cmd = %s\n" % c['Cmd'])
        new_circus.write("numprocesses = 1\n")
        new_circus.write("stdout_stream.class = FileStream\n")
        new_circus.write("stdout_stream.filename = " + \
                         "/var/log/carrier_%s.stdout\n" % c['Name'])
        new_circus.write("stderr_stream.class = FileStream\n")
        new_circus.write("stderr_stream.filename = " + \
                         "/var/log/carrier_%s.stderr\n" % c['Name'])
        new_circus.write("copy_env = True\n")
        new_circus.write("graceful_timeout = %d\n" % Graceful_Timeout)
        new_circus.write("max_age = %d\n" % Max_Age)
        new_circus.write("max_age_variance = %d\n" % Max_Age_Variance)
        new_circus.write("\n")

# Si le nouveau fichier circus.ini est different du precedent,
# on fait un reloadconfig dans circus
if filecmp.cmp('/tmp/circus.ini', '/etc/circus.ini') == False:
    shutil.move('/tmp/circus.ini', '/etc/circus.ini')
    os.system("/usr/bin/circusctl reloadconfig")

# Nettoyage des users (sprinklers) et repertoires (sprinklers et carriers)
# devenus obsoletes
list_dir = os.listdir("/data")
for dir in list_dir:
    if dir != 'tmp':
        if dir.rfind('-') >= 0:
            # Repertoire correspondant a un carrier
            # On le supprime s'il ne correspond a aucun carrier
            if dir not in watched_directories:
                shutil.rmtree("/data/%s" % dir, ignore_errors=True)
                print "%s : Directory /data/%s removed" % (now(), dir)
        else:
            # Repertoire correspondant a un sprinkler
            # On supprime le user et son arborescence s'il ne correspond a
            # aucun sprinkler
            if dir not in watched_directories:
                os.system("/usr/sbin/userdel -r %s" % dir)
                print "%s : User %s and Directory /data/%s removed" % (now(),
                      dir, dir)

