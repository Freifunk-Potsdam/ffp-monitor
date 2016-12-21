#!/usr/bin/env python3
import time
import shlex
import random
import binascii
from defs import *
from base import *

def htmltable(jsdata):
    s = "<html><body><table style='width: 100%'><tr>"
    for c in jsdata["cols"][1:]:
        s += "<th>%s</th>" % c["label"]
    s += "</tr>"
    for d in jsdata["data"]:
        s += "<tr style='%s'>" % d[0]
        for c in d[1:]:
            if type(c) == dict:
                c = c["f"]
            s += "<td>%s</td>" % c
        s += "</tr>"
    s += "</table></body></html>"
    return s

def buildquery(q,over={}):
    if q in BGCOLORS:
         return {"last_ts":{"$lt":time.time()-BGCOLORS[q]["last_ts"]}}
    try:
        qs = shlex.split(q)
    except ValueError as ex:
        print(ex, q)
        qs = q.split()
    query = {}
    i = 0 
    while i < len(qs):
        if "=" in qs[i]:
            k,_,v = qs[i].partition("=")
            query[k] = v
            del qs[i]
        else:
            i += 1
    fields = DEFQUERYFIELDS
    ored = []
    for f in fields:
        anded = []
        for qa in qs:
            qa = {f:{"$regex":qa, "$options":"i"}}
            anded.append(qa)
        if len(anded) > 0:
            ored.append({"$and":anded})
    if len(ored)>0:
        query["$or"] = ored
    query.update(over)
    return query

def fmtout(jsdata,fmt):
    if fmt == "json":
        cherrypy.response.headers['Content-Type'] = 'application/json'
        return bytes(json.dumps(jsdata,cls=JSONEncoder),"utf-8")
    elif fmt == "html":
        return bytes(htmltable(jsdata),"utf-8")
    raise HTTPError("404 Not Found")

def route2gjs(l,maxetx):
    f = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": l["c"] 
        },
        "properties": {
            "info":  mkrouteinfo(l),
            "color": "#"+binascii.hexlify(bytes([
                int( (l["etx"] / maxetx) * 255), 
                int( 255 - (l["etx"] / maxetx) * 255),
                0
            ])).decode('ascii'),
            "etx":   l["etx"],
        }
    }
    return f

def link2gjs(l,etxbase=24):
    f = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": l["c"] 
        },
        "properties": {
            "info":  mklinkinfo(l),
            "color": etx2color(l["etx%d" % etxbase]),
            "etx":   l["etx%d" % etxbase],
        }
    }
    return f

def node2gjs(n,color=None):
    random.seed(n["hostname"])
    f = { 
        "type": "Feature",
        "geometry": {
            "type": "Point", 
            "coordinates": [
                floatdef(getelem(n,"sysinfo.longitude"),DEFLON - 0.001 + random.random() * 0.002),
                floatdef(getelem(n,"sysinfo.latitude" ),DEFLAT - 0.001 + random.random() * 0.002),
            ]
        },
        "properties": {
            "popup": COLDEFS["gjspopup"]["ext"](n),
            "info":  COLDEFS["gjsinfo"]["ext"](n),
            "color": COLDEFS["gjscolor"]["ext"](n) if color is None else color,
            "uplink": hasextroute(n),
        }
    }
    return f

def genjsdata(docs,cols):
    jsdata = {"cols":[],"data":[]}
    for c in cols:
        if c in COLDEFS:
            jsdata["cols"].append(COLDEFS[c]["def"])
        else:
            print("Unknown column %s" % c)
    for d in docs:
        row = []
        for c in cols:
            if c in COLDEFS:
                row.append(COLDEFS[c]["ext"](d))
        jsdata["data"].append(row)
    return jsdata

