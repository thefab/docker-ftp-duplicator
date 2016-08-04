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
import fnmatch
import time

def now():
    return(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time())))

def signalHandler(signum, frame):
    print "%s : sprinkler.py receive signal %d" % (now(), signum)
    print "%s : Stop watching %s" % (now(), args.Incoming_directory)
    wm.rm_watch(wdd.values())
    notifier.stop()
    sys.exit()

def duplicate_file(str):
    for pattern in Exclude:
        if fnmatch.fnmatch(str, pattern):
            return
    for dir in args.Outcoming_directories:
        if dir != 'Trash':
            if Log_Level == 'verbose' or Log_Level =='debug':
                print "%s : Duplicate %s to %s/%s" % (now(), str, dir,
                                                      os.path.basename(str))
            os.link(str, "%s/%s" % (dir, os.path.basename(str)))
    if Log_Level == 'verbose' or Log_Level =='debug':
        print "%s : Unlink %s" % (now(), str)
    os.unlink(str)

parser = argparse.ArgumentParser(
    "Duplicate one incoming directory in several outcoming directories")
parser.add_argument('Incoming_directory', type=str, help='Incoming directory')
parser.add_argument('Consul_index_md5', type=str, help='Consul md5 index')
parser.add_argument('Outcoming_directories', type=str, nargs='+',
                    help='Outcoming directories')

args = parser.parse_args()

signal.signal(signal.SIGTERM, signalHandler)
signal.signal(signal.SIGHUP, signalHandler)
signal.signal(signal.SIGINT, signalHandler)

# Parametres
Max_Age = int(os.environ.get("DUPLICATORFTP_WATCHER_MAX_AGE"))
Log_Level = os.environ.get("DUPLICATORFTP_LOG_LEVEL")

Consul = os.environ.get("DUPLICATORFTP_CONSUL")
# Url pour requeter consul (fichier settings de la voie)
url = "http://%s/v1/kv/ftp_duplicator/incoming_directories/%s/settings" \
    % (Consul, os.path.basename(args.Incoming_directory))
reply = requests.get(url)
if reply.status_code != 200:
    print "%s : Error : Consul return code %d" % (now(), reply.status_code)
result = reply.json()
settings = json.loads(base64.b64decode(result[0]['Value']))
Exclude = settings['exclude']

# Creation eventuelle des repertoires output
for dir in args.Outcoming_directories:
    if dir != 'Trash' and not os.path.isdir(dir):
        print "%s : Directory %s created" % (now(), dir)
        os.mkdir(dir)

wm = pyinotify.WatchManager()

mask = pyinotify.IN_CREATE | pyinotify.IN_MOVED_TO | \
       pyinotify.IN_MOVE_SELF | pyinotify.IN_DELETE_SELF

class Monitor(pyinotify.ProcessEvent):

    def process_IN_CREATE(self, event):
        if Log_Level == 'verbose' or Log_Level =='debug':
            print "%s : File %s created" % (now(), event.pathname)
        duplicate_file(event.pathname)

    def process_IN_MOVED_TO(self, event):
        if Log_Level == 'verbose' or Log_Level =='debug':
            print "%s : File move to: %s" % (now(), event.pathname)
        duplicate_file(event.pathname)

    def process_IN_MOVE_SELF(self, event):
        print "%s : Directory: %s moved" % (now(), event.pathname)
        print "%s : Stop watching %s" % (now(), args.Incoming_directory)
        wm.rm_watch(args.Incoming_directory)
        notifier.stop()

    def process_IN_DELETE_SELF(self, event):
        print "%s : Directory: %s removed" % (now(), event.pathname)

notifier = pyinotify.Notifier(wm, Monitor(), timeout=1000) #timeout de 1000ms sur le check-events()

wdd = wm.add_watch(args.Incoming_directory, mask)
print "%s : Start watching %s" % (now(), args.Incoming_directory)

# Recuperation des fichiers presents sur le repertoire a surveiller
list_files = os.listdir(args.Incoming_directory)
for file in list_files:
    file_path = "%s/%s" % (args.Incoming_directory, file)
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

