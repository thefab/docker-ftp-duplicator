# Documentation technique du container ftp-duplicator
Auteur : Jean-Baptiste Veslin, email :  <jean-baptiste.veslin@meteo.fr>
(in french, to be translated...)

## Introduction
ftp-duplicator est une image docker permettant de dupliquer des fichiers arrivant par ftp sur des répertoires (voies ftp, appelées incoming_directories) vers d'autres containers ou machines abonnés (subscribers).

La configuration des incoming_directories et des subscribers est faite via l'outil [Consul](https://www.consul.io/intro/) qui permet de configurer des services sur une architecture. On peut ajouter des voies, des subscribers, en supprimer, en modifier, "à la volée", les modifications sont prises en compte dans la minute qui suit.

La diffusion vers les subscribers est faite soit en mode ftp, soit en mode http.

## Fonctionnement
### Héritage docker
Le container ftp-duplicator "hérite" du container "autoclean-vsftpd", container héritant lui-même, en y ajoutant un serveur ftp, du container "centos-opinionated" correspondant à un système centos6 64 bits "léger", 2 containers écrits par Fabien Marty.
### Circus
Le container démarre un daemon [Circus](https://circus.readthedocs.io/en/latest/), un outil permettant de monitorer et contrôler des process (watchers dans la nomenclature circus) et des sockets.

### manage_duplicator_ftp.py
Le fonctionnement est piloté par le shell python manage_duplicator_ftp.py, croné toutes les minutes, qui effectue à chaque exécution les tâches suivantes :
* Lecture de la configuration des voies ftp et de leurs subscribers dans Consul (lecture initiale ou mise à jour)
* Création des users et home directory correspondant à chaque voie ftp, sur /data (répertoire accessible depuis l'extérieur du container)
* Fabrication (ou mise à jour) "à la volée" du fichier circus.ini permettant de configurer le lancement par Circus d'un "watcher" par voie ftp (shell sprinkler.py) et pour chaque voie d'un watcher par subscriber (shell carrier.py).
* Rechargement du fichier circus.ini (circusctl reloadconfig) : lancement des nouveaux watchers (nouvelles voie ftp ou nouveaux subscribers), arrêt de ceux qui ne sont plus pertinents, relance de ceux pour lesquels la configuration consul a été modifiée (via l'utilisation d'une clef dans la commande de lancement du watcher)
* Si la variable DUPLICATORFTP_CONSUL_COLLECTD_SERVICE (identification d'un service collectd dans Consul) est renseignée, on lance (ou relance) le service collectd pour logger des informations sur les fichiers présents dans les arborescences traitées par les différents watchers (sprinklers et carriers), via le plugin filecount de collectd
* Exemple de fichier circus.ini
```
[circus]
statsd = False
check_delay = 5
endpoint = tcp://127.0.0.1:5555
pubsub_endpoint = tcp://127.0.0.1:5556

[watcher:sprinkler_transmet_alpha]
cmd = /usr/local/bin/sprinkler.py /data/transmet_alpha a7e253cd8dd95da3e20daf45519a8dc2 Trash
numprocesses = 1
stdout_stream.class = FileStream
stdout_stream.filename = /var/log/sprinkler_transmet_alpha.stdout
stderr_stream.class = FileStream
stderr_stream.filename = /var/log/sprinkler_transmet_alpha.stderr
copy_env = True
graceful_timeout = 30
max_age = 310
max_age_variance = 30

[watcher:sprinkler_transmet_fac]
cmd = /usr/local/bin/sprinkler.py /data/transmet_fac 7de802f4a710bbcde8eb971a3cf5e811 /data/transmet_fac-autoclean-webdav-137.129.47.64:32797 /data/transmet_fac-autoclean-webdav-137.129.47.64:32798 /data/transmet_fac-meaux
numprocesses = 1
stdout_stream.class = FileStream
stdout_stream.filename = /var/log/sprinkler_transmet_fac.stdout
stderr_stream.class = FileStream
stderr_stream.filename = /var/log/sprinkler_transmet_fac.stderr
copy_env = True
graceful_timeout = 30
max_age = 310
max_age_variance = 30

[watcher:carrier_transmet_fac-autoclean-webdav-137.129.47.64:32797]
cmd = /usr/local/bin/carrier.py 83750 ftp_duplicator/incoming_directories/transmet_fac/subscribers/autoclean-webdav /data/transmet_fac-autoclean-webdav-137.129.47.64:32797 --force_host=137.129.47.64 --force_port=32797
numprocesses = 1
stdout_stream.class = FileStream
stdout_stream.filename = /var/log/carrier_transmet_fac-autoclean-webdav-137.129.47.64:32797.stdout
stderr_stream.class = FileStream
stderr_stream.filename = /var/log/carrier_transmet_fac-autoclean-webdav-137.129.47.64:32797.stderr
copy_env = True
graceful_timeout = 30
max_age = 310
max_age_variance = 30

[watcher:carrier_transmet_fac-autoclean-webdav-137.129.47.64:32798]
cmd = /usr/local/bin/carrier.py 84379 ftp_duplicator/incoming_directories/transmet_fac/subscribers/autoclean-webdav /data/transmet_fac-autoclean-webdav-137.129.47.64:32798 --force_host=137.129.47.64 --force_port=32798
numprocesses = 1
stdout_stream.class = FileStream
stdout_stream.filename = /var/log/carrier_transmet_fac-autoclean-webdav-137.129.47.64:32798.stdout
stderr_stream.class = FileStream
stderr_stream.filename = /var/log/carrier_transmet_fac-autoclean-webdav-137.129.47.64:32798.stderr
copy_env = True
graceful_timeout = 30
max_age = 310
max_age_variance = 30

[watcher:carrier_transmet_fac-meaux]
cmd = /usr/local/bin/carrier.py 64286 ftp_duplicator/incoming_directories/transmet_fac/subscribers/meaux /data/transmet_fac-meaux
numprocesses = 1
stdout_stream.class = FileStream
stdout_stream.filename = /var/log/carrier_transmet_fac-meaux.stdout
stderr_stream.class = FileStream
stderr_stream.filename = /var/log/carrier_transmet_fac-meaux.stderr
copy_env = True
graceful_timeout = 30
max_age = 310
max_age_variance = 30
```

### watcher sprinkler.py
* Il y a lancement d'un watcher sprinkler.py par voie ftp. Chacun scrute le répertoire de dépôt ftp correspondant, par utilisation du module python pyinotify.
* Les fichiers correspondants (à l'exclusion des fichiers à exclure, information lue dans Consul) sont dupliqués par lien physique sur autant de répertoires que de subscribers de la voie ftp. Le fichier d'origine est supprimé (c'est la seule action quand il n'y a aucun subscriber pour une voie ftp).
* Les sprinkler sont relancés en cas de changement dans la configuration Consul et au plus tard au bout d'une durée fixe en paramètre du container.

### watcher carrier.py
* Il y a lancement d'un watcher carrier.py par subscriber à chaque voie ftp. Dans le cas où un subscriber est un service consul, il correspond en principe à plusieurs containers et il y a lancement d'un carrier pour chacun d'entre eux.
* Chaque carrier scrute le répertoire correspondant où les fichiers ont été déposés par un sprinkler, par utilisation du module python pyinotify.
* En fonction de la configuration du subscriber lue dans Consul, il pousse chaque fichier vers le subscriber par ftp ou http.
* Les carrier sont relancés en cas de changement dans la configuration Consul et au plus tard au bout d'une durée fixe en paramètre du container.
* En cas d'échec du transfert ftp ou http, les fichiers correspondant sont laissés en place et traités à la relance suivante du watcher, cela jusqu'à expiration d'un délai en paramètre du container. En cas de succès ils sont supprimés.

## Configuration par Consul
La configuration de ftp-duplicator est basée sur l'utilisation d'un serveur Consul présent dans l'architecture, dont l'url (http://adresse_ip:port) est un des paramètres du container (voir la section Paramètres), par exemple : [syndrome4](<http://137.129.47.64:80>)

Dans la section [Key/Value](http://137.129.47.64/ui/#/dc1/kv/ftp_duplicator/) est définie une arborescence [ftp_duplicator/incoming_directories/](http://137.129.47.64/ui/#/dc1/kv/ftp_duplicator/incoming_directories/)
avec un sous-niveau d'arborescence par voie ftp, exemple [ftp_duplicator/incoming_directories/transmet_fac/](http://137.129.47.64/ui/#/dc1/kv/ftp_duplicator/incoming_directories/transmet_fac/)

A ce niveau existent :
* un fichier [settings](http://137.129.47.64/ui/#/dc1/kv/ftp_duplicator/incoming_directories/transmet_fac/settings/edit) de configuration de la voie ftp, qui a la forme d'un dictionnaire python définissant le paramétrage de la voie ftp
* un sous-niveau d'arborescence [subscribers](http://137.129.47.64/ui/#/dc1/kv/ftp_duplicator/incoming_directories/transmet_fac/subscribers/) contenant lui-même un fichier de configuration par subscriber

On a ainsi par exemple l'arborescence suivante :

    ftp_duplicator/
    |   incoming_directories/
    |   |   transmet_fac/
    |   |   |   settings
    |   |   |   subscribers/
    |   |   |   |   subscriber1
    |   |   |   |   subscriber2
    |   |   |   |   [....]
    |   |   transmet_alpha/
    |   |   |   settings
    |   |   |   subscribers/
    |   |   |   |   subscriber3
    |   |   |   |   [....]
    |   |   [....]
    
Les fichiers settings et de description des subscribers ont la forme de dictionnaires python.

### Fichiers settings (configuration des voies ftp)

Les clefs sont les suivantes :
* "user" : user utilisé pour déposer les fichiers par ftp
* "password" : le mot de passe
* "uid" : l'uid du user correspondant à créer
* "lifetime" : durée de vie des fichiers avant suppression (en cas de non consommation)
* "exclude" : liste des fichiers à exclure (correspondant typiquement aux fichiers en cours de transfert)

Exemple (dictionnaire python) :

`{"exclude":["*.t", "*.f"], "user":"transmet_fac", "password":"xxxxxx", "uid":501, "lifetime":60}`
    
### Fichiers de configuration des subscribers

Il y a 3 cas, selon que les transferts sont à faire en http ou ftp et que le subscriber est une machine "seule" ou un "service consul" correspondant a priori à plusieurs containers.

#### 1. ftp (machine seule)
Les clefs à utiliser sont les suivantes :
* "mode" : "ftp"
* "host" : nom de machine ou hostid
* "user" : user à utiliser pour le transfert ftp
* "passwd" : le mot de passe
* "directory" : le répertoire sur lequel déposer ("." par défaut)
* "tmp_suff" : suffixe en cours de transfert (".t" par défaut)

#### 2. http (machine seule)
Les clefs à utiliser sont les suivantes :
* "mode" : "http"
* "host" : nom de machine ou hostid
* "port": port à utiliser pour le transfert http
* "directory" : le répertoire sur lequel déposer ("." par défaut)

#### 3. http (service consul)
Les clefs à utiliser sont les suivantes :
* "mode" : "http"
* "service_consul" : le service consul concerné (les hosts et ports correspondants seront récupérés dans Consul)
* "directory" : le répertoire sur lequel déposer ("." par défaut)

Exemples :

`{"consul_service":"autoclean-webdav", "mode":"http", "directory":"racine/data/"}`

`{"host":"meaux", "user":"baptiste", "password":"xxxxxx", "mode":"ftp", "directory":"textes", "tmp_suff":".f"}`

## Paramètres
Le container définit plusieurs variables d'environnement (modifiables au lancement du container)
* DUPLICATORFTP_CONSUL : url d'accès à Consul (nécessaire)
* DUPLICATORFTP_CIRCUS_LEVEL : niveau de log dans circus
* DUPLICATORFTP_CIRCUS_MAX_AGE, DUPLICATORFTP_MAX_AGE_VARIANCE et DUPLICATORFTP_GRACEFUL_TIMEOUT : paramètres circus pour piloter la relance des watchers
* DUPLICATORFTP_CARRIER_MAX_AGE : durée avant abandon de la tentative de transfert d'un fichier
* DUPLICATORFTP_LOG_LEVEL : niveau de log
* DUPLICATORFTP_CONSUL_COLLECTD_SERVICE (optionnel) : identification du service collectd dans Consul
* DUPLICATORFTP_HOSTNAME : (optionnel, en lien avec le précédent) : identification du hostname qui sera transmis à collectd (a priori le CONTAINER_NAME du container ftp_duplicator)
* AUTOCLEANFTP_USERS, AUTOCLEANFTP_PASSWORDS, AUTOCLEANFTP_UIDS, AUTOCLEANFTP_LIFETIMES : doivent être vides au lancement, ne pas les modifier (mise à jour des variables d'environnement du container thefab/autoclean-vsftpd dont hérite ftpduplicator, ces variables seront modifiées "à la volée" au fonctionnement)
* AUTOCLEANFTP_PASV_ADDRESS : à positionner à `hostname -i` (ip de la machine sur laquelle on lance le container ftpduplicator)
* AUTOCLEANFTP_LEVEL=silent et AUTOCLEANFTP_SYSLOG=0 : ne pas modifier a priori
* PYTHONUNBUFFERED=1 : nécessaire pour les watchers circus

## Fichiers de log
(sur /var/log, avec historisation sur 7 jours)
* circus.log : log circus
* manage_duplicator_ftp.log : log du manager
* sprinkler_*.stderr et sprinkler_*.stdout : logs des sprinklers
* carrier_*.stderr et carrier_*.stdout : logs des carriers

## Lancement
* Définir CONTAINER_NAME et SERVICE_NAME
* IMAGE_NAME=ftp-duplicator:latest
* Définir CONSUL
* Définir éventuellement CONSUL_COLLECTD_SERVICE
* Définir éventuellement des volumes (-v xxxx:yyyy)
docker run -d --restart=always -p 20:20 -p 21:21 -p 21100-21110:21100-21110 --name=${CONTAINER_NAME} -e SERVICE_NAME=${SERVICE_NAME} -e DUPLICATORFTP_CONSUL=${CONSUL} -e AUTOCLEANFTP_PASV_ADDRESS=`hostname -i` [-e DUPLICATORFTP_HOSTNAME=${CONTAINER_NAME} -e DUPLICATORFTP_CONSUL_COLLECTD_SERVICE=${CONSUL_COLLECTD_SERVICE}] [volumes] ${IMAGE_NAME}


