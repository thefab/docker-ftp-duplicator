#!/bin/bash

mkdir -p /build
rpm -qa --qf '%{name}\n' >/build/original_packages.list

yum install -y wget unzip gcc python-devel gcc-c++
#yum --enablerepo=epel install -y python-pip
