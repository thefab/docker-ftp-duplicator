#!/bin/env python
# -*- coding: utf-8 -*-
#
import argparse
import signal
import os
import sys
import time
import pyinotify
import requests
import base64
import json
import ftplib

def now():
    return(time.strftime("%Y%m%d %H%M", time.localtime(time.time())))

def signalHandler(signum, frame):
    print "%s : carrier.py receive signal %d" % (now(), signum)
    print "%s : Stop watching %s" % (now(), args.directory)
    wm.rm_watch(wdd.values())
    notifier.stop()
    sys.exit()

def transfer_file(str):
    if settings['mode'] == 'http':
        with open(str, 'r') as f:
            url = "http://%s:%s/%s/%s" % (settings['host'], settings['port'],
                                          settings['directory'], 
                                          os.path.basename(str))
            if Log_Level == 'verbose' or Log_Level == 'debug':
                print "%s : Http transfer %s to %s" % (now(), str, url)
            reply = requests.put(url, data=f.read(), timeout=30)
            if reply.status_code < 200 or reply.status_code >= 300:
                print "%s : Error : http transfer return code %d" % (now(),
                    reply.status_code)
            else:
                if Log_Level == 'verbose' or Log_Level == 'debug':
                    print "%s : Unlink %s" % (now(), str)
                os.unlink(str) 

    elif settings['mode'] == 'ftp':
        if Log_Level == 'verbose' or Log_Level == 'debug':
            print "%s : Ftp transfer %s on %s" % (now(), str, settings['host'])
        try:
            ftp = ftplib.FTP(host=settings['host'], user=settings['user'],
                             passwd=settings['password'], timeout=30)
            if settings['directory'] != '.':
                ftp.cwd(settings['directory'])
            tmp_stor = os.path.basename(str) + settings['tmp_suff']
            ftp.storbinary("STOR %s" % tmp_stor, open(str, "r"))
            ftp.rename(tmp_stor, os.path.basename(str))
        except:
            print "%s : Transfer Ftp error %s on %s" % (now(), str,
                                                        settings['host'])
            # On ne supprime pas le fichier
            return
        if Log_Level == 'verbose' or Log_Level == 'debug':
            print "%s : Unlink %s" % (now(), str)
        os.unlink(str) 
        

parser = argparse.ArgumentParser(
    "Transfer files in specified directory to a Consul subscriber")
parser.add_argument('consul_id', type=str, help='Consul md5 index')
parser.add_argument('consul_kv', type=str,
                    help='Consul kv with transfer information')
parser.add_argument('directory', type=str,
                    help='Directory with files to be transferred')
parser.add_argument('--force_host', type=str, help='Forced host (optional)')
parser.add_argument('--force_port', type=str, help='Forced port (optional)')

args = parser.parse_args()

signal.signal(signal.SIGTERM, signalHandler)
signal.signal(signal.SIGHUP, signalHandler)
signal.signal(signal.SIGINT, signalHandler)

# Parametres
Max_Age = int(os.environ.get("DUPLICATORFTP_CARRIER_MAX_AGE"))

Log_Level = os.environ.get("DUPLICATORFTP_LOG_LEVEL")

Consul = os.environ.get("DUPLICATORFTP_CONSUL")
# Url pour requeter consul (fichier de config du subscriber)
url = "http://%s/v1/kv/%s" % (Consul, args.consul_kv)
reply = requests.get(url)
if reply.status_code != 200:
    print "%s : Error : Consul return code %d" % (now(), reply.status_code)
result = reply.json()
settings = json.loads(base64.b64decode(result[0]['Value']))

# Positionnement defauts ftp
if settings['mode'] == 'ftp':
    if not settings.has_key('directory'):
        settings['directory'] = '.'
    if not settings.has_key('tmp_suff'):
        settings['tmp_suff'] = '.t'

# Cas d'un service consul (port et host hors consul)
if settings.has_key('consul_service'):
    settings['port'] = args.force_port
    settings['host'] = args.force_host
    if not settings.has_key('directory'):
        settings['directory'] = '.'
 
wm = pyinotify.WatchManager()

mask = pyinotify.IN_CREATE | pyinotify.IN_MOVED_TO | \
       pyinotify.IN_MOVE_SELF | pyinotify.IN_DELETE_SELF #watched events

class Monitor(pyinotify.ProcessEvent):

    def process_IN_CREATE(self, event):
        if Log_Level == 'verbose' or Log_Level == 'debug':
            print "%s : File %s created" % (now(), event.pathname)
        transfer_file(event.pathname)

    def process_IN_MOVED_TO(self, event):
        if Log_Level == 'verbose' or Log_Level == 'debug':
            print "%s : File moved to %s" % (now(), event.pathname)
        transfer_file(event.pathname)

    def process_IN_MOVE_SELF(self, event):
        print "%s : Directory %s moved" % (now(), event.pathname)
        print "%s : Stop watching %s" % (now(), args.directory)
        wm.rm_watch(args.directory)
        notifier.stop()

    def process_IN_DELETE_SELF(self, event):
        print "%s : Directory %s removed" % (now(), os.path.join(event.path,
                                                                 event.name))
# Creation eventuelle du repertoire a surveiller
if not os.path.isdir(args.directory):
    print "%s : Directory %s created" % (now(), args.directory)
    os.mkdir(args.directory)

notifier = pyinotify.Notifier(wm, Monitor(), timeout=1000) #timeout de 1000ms sur le check-events()

wdd = wm.add_watch(args.directory, mask)
print "%s : Start watching %s" % (now(), args.directory)

# Recuperation des fichiers presents sur le repertoire a surveiller
list_files = os.listdir(args.directory)
for file in list_files:
    file_path = "%s/%s" % (args.directory, file)
    age = int(time.time() - os.stat(file_path).st_mtime)
    if age > Max_Age:
        # Fichier trop vieux : on le supprime
        print "%s : File %s : abort transfer and remove" % (now(), file)
        os.unlink(file_path)
    else:
        # On genere un evenement IN_MOVE par un double deplacement 
        os.rename(file_path, "/data/tmp/%s" % file)
        os.rename("/data/tmp/%s" % file, file_path)

while True:
    try:
        # process the queue of events as explained above
        notifier.process_events()
        if notifier.check_events():
            # read notified events and enqeue them
            notifier.read_events()
        # you can do some tasks here...
    except KeyboardInterrupt:
        # destroy the inotify's instance on this interrupt (stop monitoring)
        notifier.stop()
        break
