#!/usr/bin/env python3
from base import *
import time
import sys
from pprint import pprint

allhosts = set( mongodb["nodes"].distinct("hostname") + mongodb["tmpnodeinfo"].distinct("host") )
for host in allhosts:
    old = mongodb["nodes"].find_one({ "hostname": host })
    last_ts = 0 if old is None else old.get( "last_ts", 0 )
    new = list( mongodb["tmpnodeinfo"].find({ "host": host, "time": { "$gt": last_ts } }, sort = [("time",1)] ) )
    if len(new) > 0:
        if old is None:
            print("New Host %s" % host)
            mongodb["changes"].insert({ "host": host, "time": time.time(), "ctime": t, "param": "hostname", "new": host, "old": None })
            old = {}
        for n in new:
            n.pop("_id")
            n.pop("host")
            t = n.pop("time")
            nifc = n.pop("ifc",None)
            if isinstance(nifc, dict):
                nifc.pop("tunl0",None)
                for k,v in nifc.items():
                    v.pop("assoc",None)
                    v.pop("rx_packets",None)
                    v.pop("tx_packets",None)
                    v.pop("rx_bytes",None)
                    v.pop("tx_bytes",None)
                n["ifc"] = nifc
            for a,newv in list(n.items()):
                oldv = old.get(a,None)
                if newv != oldv:
                    mongodb["changes"].insert({ "host": host, "time":time.time(), "ctime": t, "param": a, "new": newv, "old": oldv })
                else:
                    n.pop(a)
            q = {   
                "$setOnInsert": { "hostname": host },
                "$max": { "last_ts": t },
            }
            if len(n) > 0:
                q["$set"] = n
            mongodb["nodes"].update( {"hostname": host}, q, upsert = True )
            old.update(n)

now = time.time()
# find state changes
for host in mongodb["nodes"].find():
    old = host.get("state",None)
    delay = now - host.get("last_ts",0)
    new = "online"
    if delay > 7 * 24 * 60 * 60:
        new = "dead"
    elif delay > 24 * 60 * 60:
        new = "offline"
    elif delay > 3 * 60 * 60:
        new = "late"
    if new != old:
        mongodb["changes"].insert({
            "host": host["hostname"],
            "time":now,
            "ctime": now,
            "param": "state",
            "new": new,
            "old": old,
        })
        mongodb["nodes"].update({"hostname":host["hostname"]},{"$set":{"state":new}})

mongodb["tmpnodeinfo"].remove({ "time": { "$lt": now - 24 * 60 * 60 } })
mongodb["changes"].remove({ "time": { "$lt": now - 7 * 24 * 60 * 60 } })
# remove nodes, not seen for 35 days
for n in mongodb["nodes"].find({ "last_ts": { "$lt": now - 35 * 24 * 60 * 60 } }):
    mongodb["nodes"].remove(n["_id"])
    mongodb["changes"].insert({ "host": host, "time": time.time(), "ctime": time.time(), "param": "hostname", "new": None, "old": n["hostname"] })

# update uptimes
infq = 'SELECT last("uptime") AS "uptime" FROM "load" ' + \
    'WHERE time > NOW() - 24h AND time < NOW() GROUP BY ' + \
    'time(24h), "hostname" fill(none)'
idata = influxdb.query(infq)

mdata = {}
for r in idata.get('results',[]):
    for s in r.get('series',[]):
        d = s.get('tags',{})
        cols = s.get('columns',[])
        vals = s.get('values',[])
        if len(cols) * len(vals) > 0:
            vals.sort(key=lambda x: x[cols.index('time')])
            host = d["hostname"]
            uptime = int(vals[-1][cols.index('uptime')])
            mongodb["nodes"].update({"hostname":host},{"$set":{"uptime":uptime}})


