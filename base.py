#!/usr/bin/env python3

import sys
if sys.version_info[0]<3:
    print ("At least Python Version 3 is needed.")
    sys.exit(3)

import cherrypy
from cherrypy import HTTPError
from cherrypy._cperror import HTTPRedirect
from cherrypy.lib.static import serve_fileobj, serve_file
import logging
import os
import json
import jinja2
from bson.objectid import ObjectId
from pymongo import MongoClient
import influx
import time
from math import radians, cos, sin, asin, sqrt

logging.basicConfig(level=logging.WARNING)

cherrypy.config.update({
    'environment': 'embedded',
})

mongodbe = MongoClient()
mongodb = mongodbe["freifunk"]
influxdb = influx.InfluxDB("localhost",8086,"freifunk","freifunk","freifunk",debug=False)
influxdb_archive = influx.InfluxDB("localhost",8086,"ffarchive","freifunk","freifunk",debug=False)

def startapp(app):
    return cherrypy.Application( app( mongodb, influxdb ) , script_name=None, config=None)

def intdef(s,default=0):
    try:
        return int(s)
    except:
        return default

def floatdef(s,default=0.0):
    try:
        return float(s)
    except:
        return default

def tryround(n,d=0):
    return round(n,d) if isinstance(n,float) else n

def getelem(data,elem,default=None):
    name,_,elem = elem.partition(".")
    if name in data:
        data = data[name]
        if elem == "":
            return data
        else:
            return getelem(data,elem,default)
    else:
        return default

def formatDuration(v):
    res = ""
    v,s = divmod(v,60)
    v,m = divmod(v,60)
    d,h = divmod(v,24)
    if (d > 0):
        res += "%dd " % d;
    if (h > 0):
        res += "%dh " % h;
    if (m > 0):
        res += "%dm " % m;
    return res.strip()

def formatGen(val, fact, pre, r=0):
    i = 0
    while i < len(pre) and val > fact:
        val /= fact
        i += 1
    return str(round(val,r)) + pre[i]

def formatSI(val,r=1):
    return formatGen(val, 1000, [""," k"," M"," G"," T"," P"," E"],r)

def formatBytes(val,r=1):
    return formatGen(val, 1024, [" Bytes"," KiB"," MiB"," GiB"," TiB"," PiB"," EiB"],r)

def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    km = 6367 * c
    return km

