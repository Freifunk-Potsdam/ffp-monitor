#!/usr/bin/env python3
from base import *
from pprint import pprint
import time
from hashlib import md5
from defs import DEFLON,DEFLAT
from helpers import getelem,floatdef

def mean(l):
    while None in l:
        l.remove(None)
    return (sum(l) / len(l)) if len(l) > 0 else None

def median(l):
    while None in l:
        l.remove(None)
    l.sort()
    if len(l) == 0:
        return None
    elif len(l) % 2 == 1:
        return l[len(l) // 2]
    else:
        return (l[len(l) // 2 - 1] + l[len(l) // 2]) / 2

def calcetx(lq,nlq):
    lq = 0 if lq is None else lq
    nlq = 0 if nlq is None else nlq
    return 1 / (lq * nlq) if (lq * nlq) > 0 else 1000000

infq = 'SELECT median("linkQuality") AS lq,median("neighborLinkQuality") AS nlq FROM "links" ' + \
    'WHERE time > NOW() - 24h AND time < NOW() - 1m GROUP BY ' + \
    'time(1h), "localIP", "remoteIP", "remoteHostname", "hostname" fill(null)'
idata = influxdb.query(infq)

mdata = {}
for r in idata.get('results',[]):
    for s in r.get('series',[]):
        d = s.get('tags',{})
        cols = s.get('columns',[])
        vals = s.get('values',[])
        if len(cols) * len(vals) > 0:
            vals.sort(key=lambda x: x[cols.index('time')])
            for i in range(len(cols)):
                d[cols[i]] = vals[-1][i]
            d["lq3"] = median([x[cols.index("lq")] for x in vals[-3:]])
            d["lq24"] = median([x[cols.index("lq")] for x in vals[-24:]])
            d["nlq3"] = median([x[cols.index("nlq")] for x in vals[-3:]])
            d["nlq24"] = median([x[cols.index("nlq")] for x in vals[-24:]])
            if "hostname" in d and "remoteHostname" in d and "localIP" in d and "remoteIP" in d:
                _id = [d["hostname"],d["remoteHostname"]]
                _id.sort()
                _id = "_".join([md5(bytes(x,"utf-8")).hexdigest() for x in _id])
                if _id not in mdata:
                    mdata[_id] = {"_id":_id,"ha":d["hostname"],"hb":d["remoteHostname"],"l":{}}
                lid = [d["localIP"],d["remoteIP"]]
                lid.sort()
                lid = "_".join(lid)
                if lid not in mdata[_id]["l"]:
                    mdata[_id]["l"][lid] = {"a":{},"b":{}}
                l = {}
                if mdata[_id]["ha"] == d["hostname"]:
                    l = mdata[_id]["l"][lid]["a"]
                    ol = mdata[_id]["l"][lid]["b"]
                elif mdata[_id]["hb"] == d["hostname"]:
                    l = mdata[_id]["l"][lid]["b"]
                    ol = mdata[_id]["l"][lid]["a"]
                l["ip"] = d["localIP"]
                l["lq3"] = d.get("lq3",0)
                l["nlq3"] = d.get("nlq3",0)
                l["lq24"] = d.get("lq24",0)
                l["nlq24"] = d.get("nlq24",0)
                l["etx3"] = calcetx( l["lq3"],l["nlq3"] )
                l["etx24"] = calcetx( l["lq24"],l["nlq24"] )
                if "ip" not in ol:
                    ol["ip"] = d["remoteIP"]

t = time.time()
for d in mdata.values():
    ha = mongodb["nodes"].find_one({"hostname":d["ha"]})
    hb = mongodb["nodes"].find_one({"hostname":d["hb"]})
    if None not in [ha,hb]:
        d["c"] = [
            [floatdef(getelem(ha,"sysinfo.longitude"),DEFLON),floatdef(getelem(ha,"sysinfo.latitude"),DEFLAT)],
            [floatdef(getelem(hb,"sysinfo.longitude"),DEFLON),floatdef(getelem(hb,"sysinfo.latitude"),DEFLAT)]
        ]
        if d["c"][0][0] <= d["c"][1][0]:
            d["left"] = "a"
            d["right"] = "b"
        else:
            d["left"] = "b"
            d["right"] = "a"
        d["l"] = list(d["l"].values())
        for l in d["l"]:
            for etx in ["etx3","etx24"]:
                etxs = []
                if etx in l["a"]:
                    etxs.append(l["a"][etx])
                if etx in l["b"]:
                    etxs.append(l["b"][etx])
                l[etx] = sum(etxs) / len(etxs)
        for etx in ["etx3","etx24"]:
            d["l"].sort(key=lambda x: x[etx])
            d[etx] = d["l"][0][etx]
        d["time"] = t
        mongodb["linkperf"].remove(d["_id"])
        mongodb["linkperf"].insert(d)

mongodb["linkperf"].remove({"time":{"$lte":t-12*60*60}})
