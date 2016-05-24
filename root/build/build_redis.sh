#!/bin/bash

ARCH=linux_amd64
BUILD_DIR=/build

mkdir -p ${BUILD_DIR}
mkdir -p ${DEST_DIR}

VERSION=3.0.7
NAME=redis
ARCHIVE_NAME=${NAME}-${VERSION}.tar.gz
ARCHIVE_URL=http://download.redis.io/releases/${ARCHIVE_NAME}

cd ${BUILD_DIR} || exit 1
wget -O ${ARCHIVE_NAME} ${ARCHIVE_URL}
tar xvfz ${ARCHIVE_NAME}
cd ${NAME}-${VERSION}
#Installation sur /usr/local/bin par defaut, sinon preciser PREFIX=
make
make install
