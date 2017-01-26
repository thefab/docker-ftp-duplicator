#!/bin/bash

mkdir -p /build

yum --enablerepo=epel install -y python-requests collectd
