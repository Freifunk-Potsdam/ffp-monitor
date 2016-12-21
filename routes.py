#!/usr/bin/env python3
from base import *
from pprint import pprint
import time
from hashlib import md5
from defs import DEFLON,DEFLAT
from helpers import getelem,floatdef
from copy import deepcopy
from multiprocessing.pool import ThreadPool
from multiprocessing import Pool

nodes = {}
for h in mongodb["nodes"].distinct("hostname"):
    nodes[h] = {"l":{}}
    for l in mongodb["linkperf"].find({"etx3":{"$lt":10},"$or":[{"ha":h},{"hb":h}]}):
        if l["ha"] not in [h,None]:
            nodes[h]["l"][l["ha"]] = l["etx3"]
        if l["hb"] not in [h,None]:
            nodes[h]["l"][l["hb"]] = l["etx3"]

def findreachable(start,nodes,visited = []):
    reachable = []
    if start in nodes:
        for r in nodes[start]["l"].keys():
            if r not in visited:
                reachable.append(r)
                reachable.extend(findreachable(r,nodes,visited+[start]))
    return list(set(reachable))

def findroutes(start,nodes,visited = []):
    routes = {}
    if start in nodes:
        for n,etx in nodes[start]["l"].items():
            if n not in visited:
                if n not in routes or routes[n]["etx"] > etx:
                    routes[n] = {"etx":etx,"via":[]}
                for sn,r in findroutes(n,nodes,visited+[start]).items():
                    if sn not in routes or routes[sn]["etx"] > etx+r["etx"]:
                        routes[sn] = {"etx":etx+r["etx"],"via":[n]+r["via"]}
    return routes

groups = []
nn = list(nodes.keys())
while len(nn) > 0:
    groups.append({})
    group = findreachable(nn[0],nodes)
    group.append(nn[0])
    for n in group:
        groups[-1][n] = nodes[n]
        nn.remove(n)
t = time.time()
for g in groups:
    mongodb["nodegroups"].insert({"time":t,"members":list(g.keys())})
    for m in g.keys():
        for n,r in findroutes(m,g).items():
            r.update({"start":m,"target":n,"time":t})
            r["c"] = []
            for nn in [m] + r["via"] + [n]:
                node = mongodb["nodes"].find_one({"hostname":nn})
                r["c"].append([
                    floatdef(getelem(node,"sysinfo.longitude"),DEFLON),
                    floatdef(getelem(node,"sysinfo.latitude"),DEFLAT)
                ])
            mongodb["routes"].insert(r)
mongodb["nodegroups"].remove({"time":{"$lt":t}})
mongodb["routes"].remove({"time":{"$lt":t}})
