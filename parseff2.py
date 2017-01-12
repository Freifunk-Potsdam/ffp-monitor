#!/usr/bin/env python3
from base import *
import time
import sys
from pprint import pprint,pformat

allhosts = set( mongodb["nodes"].distinct("hostname") + mongodb["tmpnodeinfo"].distinct("host") )
for host in allhosts:
    old = mongodb["nodes"].find_one({ "hostname": host })
    last_ts = 0 if old is None else old.get( "last_ts", 0 )
    new = list( mongodb["tmpnodeinfo"].find({ "host": host, "time": { "$gt": last_ts } }, sort = [("time",1)] ) )
    if len(new) > 0:
        if old is None:
            mongodb["changes"].insert({ "host": host, "time": time.time(), "ctime": new[0]["time"], "param": "hostname", "new": host, "old": None })
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
                    if k.startswith("tnl_"):
                        v["mac"] = None
                n["ifc"] = nifc
            for a,newv in list(n.items()):
                oldv = old.get(a,None)
                changed = False
                detail = None
                if type(oldv) != type(newv):
                    changed = True
                elif isinstance(oldv,dict):
                    added = []
                    removed = []
                    modified = []
                    allkeys = set( oldv.keys() ) | set( newv.keys() )
                    for k in allkeys:
                        if k not in oldv:
                            added.append( k )
                        elif k not in newv:
                            removed.append( k )
                        elif oldv[k] != newv[k]:
                            modified.append( k )
                    if len(added+removed+modified) > 0:
                        detail = {"modified":modified,"added":added,"removed":removed,"old":oldv,"new":newv}
                        oldl = []
                        newl = []
                        for k in sorted(modified):
                            fmtol = [ "|" + l[1:] for l in pformat({k:oldv[k]})[:-1].split("\n") ]
                            fmtnl = [ "|" + l[1:] for l in pformat({k:newv[k]})[:-1].split("\n") ]
                            oldl.extend(fmtol)
                            newl.extend(fmtnl)
                        for k in sorted(removed):
                            fmtl = [ "-" + l[1:] for l in pformat({k:oldv[k]})[:-1].split("\n") ]
                            oldl.extend(fmtl)
                        for k in sorted(added):
                            fmtl = [ "+" + l[1:] for l in pformat({k:newv[k]})[:-1].split("\n") ]
                            newl.extend(fmtl)
                        oldv = "\n".join(oldl)
                        newv = "\n".join(newl)
                        changed = True
                else:
                    changed = oldv != newv
                if changed:
                    c = { "host": host, "time":time.time(), "ctime": t, "param": a, "new": newv, "old": oldv }
                    if detail is not None:
                        c["detail"] = detail
                    mongodb["changes"].insert( c )
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
            "time": now,
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
    mongodb["nodes"].delete_one( {"_id":n["_id"]} )
    mongodb["names"].delete_many( {"hostname":n["hostname"]} )
    mongodb["changes"].insert({ "host": n["hostname"], "time": time.time(), "ctime": time.time(), "param": "hostname", "new": None, "old": n["hostname"] })

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


