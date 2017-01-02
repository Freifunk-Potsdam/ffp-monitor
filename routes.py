#!/usr/bin/env python3
from base import *
from pprint import pprint
import time
from apdb import DEFLON,DEFLAT
from copy import deepcopy
from multiprocessing.pool import ThreadPool
from multiprocessing import Pool
import sys

print("Searching 1st Hop Naighbors...")
nodes = {}
for h in mongodb["nodes"].distinct("hostname"):
    nodes[h] = {"l":{}}
    for l in mongodb["linkperf"].find({"etx24":{"$lt":10},"$or":[{"ha":h},{"hb":h}]}):
        if l["ha"] not in [h,None]:
            nodes[h]["l"][l["ha"]] = l["etx24"]
        if l["hb"] not in [h,None]:
            nodes[h]["l"][l["hb"]] = l["etx24"]

def findreachable(start,nodes,visited = []):
    reachable = []
    if start in nodes:
        visited.append(start)
        for r in nodes[start]["l"].keys():
            if r not in visited:
                reachable.append(r)
                reachable.extend(findreachable(r,nodes,visited))
    return list(set(reachable))

groups = []
nn = list(nodes.keys())
while len(nn) > 0:
    groups.append({})
    print("Searching all reachable nodes from %s..." % nn[0], end="")
    sys.stdout.flush()
    group = findreachable(nn[0],nodes)
    group.append(nn[0])
    for n in group:
        groups[-1][n] = nodes[n]
        nn.remove(n)
    print(" %d nodes, %d nodes left." % ( len(group), len(nn) ))

class Node:
    def __init__(self,group,name=None,creator=None):
        self.group = group
        if name is None:
            creator = None
            name = list(group.keys())[0]
        self.name = name
        if creator is None:
            self.allnodes = {self.name:self}
            self.onames = list(filter(lambda x: x != name, group.keys() ))
            for oname in self.onames:
                Node( self.group, oname, self )
        else:
            self.allnodes = creator.allnodes
            self.allnodes[ self.name ] = self
            self.onames = list(filter(lambda x: x != name, creator.onames ))
        self.neighetx = {}
        self.routes = {}
    
    def get_node(self,name):
        return self.allnodes[name]

    def get_route(self,target):
        if target in self.routes:
            return self.routes[target]

    def get_all_routes(self):
        for nn,n in self.allnodes.items():
            for t,r in n.routes.items():
                yield {"target":t, "start":nn, "etx": r["etx"], "via": r["via"]}

    def find_routes1(self,other = True):
        if other:
            for o in self.allnodes.values():
                o.find_routes1(False)
        else:
            for n,etx in self.group[self.name]["l"].items():
                self.neighetx[n] = etx
                if n not in self.routes or etx < self.routes[n]["etx"]:
                    self.routes[n] = {"etx":etx,"via":[]}

    def find_routesN(self,other=True):
        changed = False
        if other:
            for o in self.allnodes.values():
                changed |= o.find_routesN(False)
        else:
            for n,etx in self.neighetx.items():
                for target,r in self.allnodes[n].routes.items():
                    if target != self.name and ( target not in self.routes or (r["etx"] + etx) < self.routes[target]["etx"] ):
                        self.routes[target] = { "etx": r["etx"] + etx, "via": [n] + r["via"] }
                        changed = True
        return changed

t = time.time()
for g in groups:
    n = Node(g)
    n.find_routes1()
    c = 0
    while n.find_routesN():
        c += 1
    routes = list( n.get_all_routes() )
    print("Found %d routes between %d nodes in %d cycles." % (len(routes),len(g),c))
    mongodb["nodegroups"].insert({"time":t,"members":list(g.keys())})
    for r in routes:
        r.update({"time":t})
        r["c"] = []
        for nn in [r["start"]] + r["via"] + [r["target"]]:
            node = mongodb["nodes"].find_one({"hostname":nn})
            r["c"].append([
                floatdef(getelem(node,"sysinfo.longitude"),DEFLON),
                floatdef(getelem(node,"sysinfo.latitude"),DEFLAT)
            ])
        mongodb["routes"].insert(r)

mongodb["nodegroups"].remove({"time":{"$lt":t}})
mongodb["routes"].remove({"time":{"$lt":t}})
