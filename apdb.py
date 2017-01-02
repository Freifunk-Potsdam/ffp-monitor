#!/usr/bin/env python3
from base import *
import shlex
import ips
import random

DEFQUERYFIELDS = ["hostname","sysinfo.location","sysinfo.mail","ifc.addr","routes"]
QQUERIES = {
    "***": {"state":{"$in":["dead"]}},
    "**" : {"state":{"$in":["dead","offline"]}},
    "*"  : {"state":{"$in":["dead","offline","late"]}},
}

DEFLON = 13.054457
DEFLAT = 52.389375

def buildquery(q,over={}):
    if q in QQUERIES:
         return QQUERIES[q]
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

class ApDb:
    def get_aps(self, q = {}, sort = None):
        now = time.time()
        for ap in self._mdb["nodes"].find( q, sort = sort ):
            ap["delay"] = now - ap["last_ts"] if "last_ts" in ap else None
            yield ap

    def gen_apdb_json(self,aps,cols):
        now = time.time()
        data = []
        for ap in aps:
            adata = []
            for c in cols:
                tpl = self.get_tpl( "apdb/%s.html" % c[0] )
                if tpl is None:
                    v = ap.get( c[0], None )
                    t = c[2]["type"] if len(c) > 2 and "type" in c[2] else "string"
                    if t == "string":
                        adata.append( str( v ) )
                    elif t == "number":
                        adata.append({ "v": floatdef(v), "f": str(v) })
                    elif t == "duration":
                        adata.append({ "v": floatdef(v), "f": formatDuration( intdef(v) ) })
                    else:
                        adata.append( v )
                else:
                    adata.append( tpl.render( ap = ap, ips = ips ) )
            data.append(adata)
        res = { "data": data, "cols": []}
        for c in cols:
            col = { "label": c[1], "type": "string", "class":c[0] }
            if len(c) > 2:
                for k,v in c[2].items():
                    col[k] = v
            if col["type"] in ["duration"]:
                col["type"] = "number"
            res["cols"].append( col )
        return bytes(json.dumps( res ),"utf-8")

    @cherrypy.expose
    def apdb(self):
        return self.serve_site("apdb", cssprefix = "apdb", jsonurl = "apdb.json" )

    @cherrypy.expose
    def apdb_json(self,q=""):
        aps = self.get_aps( buildquery(q) )
        cols = [
            ["state","style",{"role":"style"}],
            ["hostname","Hostname"],
            ["ips","IP(s)"],
            ["routes","Gateways"],
            ["location","Standort"],
            ["uptime","Uptime",{"type":"duration"}],
            ["device","Gerät"],
            ["firmware","Firmware"],
            ["scriptver","Script"],
            ["contact","Kontakt"],
            ["delay","Letzte Daten",{"type":"duration"}],
            ["links","Links"],
        ]
        cherrypy.response.headers['Content-Type'] = 'application/json'
        return self.gen_apdb_json(aps,cols)

    def get_links(self, q = {}, sort = None):
        return self._mdb["linkperf"].find( q, sort = sort )

    def ap2gjs(self,ap):
        random.seed(ap["hostname"])
        f = { 
            "type": "Feature",
            "geometry": {
                "type": "Point", 
                "coordinates": [
                    floatdef(getelem(ap,"sysinfo.longitude"),DEFLON - 0.001 + random.random() * 0.002),
                    floatdef(getelem(ap,"sysinfo.latitude" ),DEFLAT - 0.001 + random.random() * 0.002),
                ]
            },
            "properties": {
                "popup": self.get_tpl( "apmap/popup.html" ).render( ap = ap, ips = ips ),
                "info":  self.get_tpl( "apmap/info.html"  ).render( ap = ap, ips = ips ),
                "state": ap["state"],
                "uplink": ips.anyextgateway( *ap.get("routes",[]) ),
            }
        }
        return f

    def link2gjs(self,l,etxbase="etx24"):
        l["length"] = 1000 * haversine(l["c"][0][0],l["c"][0][1],l["c"][1][0],l["c"][1][1])
        f = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": l["c"],
            },
            "properties": {
                "info":  self.get_tpl( "apmap/linkinfo.html"  ).render( 
                    link = l, 
                    etxbase = etxbase, 
                    lqbase =  {"etx3": "lq3","etx24": "lq24"}[etxbase],
                    nlqbase = {"etx3":"nlq3","etx24":"nlq24"}[etxbase],
                    ips = ips 
                    ),
                "etx":   l[etxbase],
            }
        }
        return f

    @cherrypy.expose
    def apmap(self):
        return self.serve_site("apmap", gjsurl = "apmap.geojson" )

    @cherrypy.expose
    def apmap_geojson(self,maxetx=None,etxbase=None):
        maxetx = floatdef(maxetx,10)
        etxbase = etxbase if etxbase in ["etx3","etx24"] else "etx24"
        gjs = { "type": "FeatureCollection","features": [] }
        
        for d in self.get_links( { etxbase: { "$lte": maxetx } }, sort = [(etxbase,-1)] ):
            gjs["features"].append( self.link2gjs(d,etxbase) )

        docs = self.get_aps( sort = [("last_ts",-1)] )
        for d in docs:
            gjs["features"].append( self.ap2gjs(d) )

        cherrypy.response.headers['Content-Type'] = 'application/json'
        return bytes(json.dumps(gjs),"utf-8")

    def get_routes(self, start):
        return self._mdb["routes"].find({"start":start},sort=[("etx",-1)])

    def route2gjs(self,l,maxetx):
        l["length"] = 0
        for i in range(1,len(l["c"])):
            l["length"] += 1000 * haversine(l["c"][i-1][0],l["c"][i-1][1],l["c"][i][0],l["c"][i][1])
        f = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": l["c"] 
            },
            "properties": {
                "info":  self.get_tpl( "apmap/routeinfo.html"  ).render( route = l, ips = ips ),
                "etx":   l["etx"],
                "maxetx":maxetx,
            }
        }
        return f

    @cherrypy.expose
    def apinfo(self,name,**kwargs):
        for ap in self.get_aps({"hostname": { "$regex": "^%s" % name }}):
            return self.serve_site("apinfomap", 
                ap = ap,
                gjsurl = "../aproutes.geojson?node=%s" % ap["hostname"],
                ips = ips,
                DEFLAT = DEFLAT,
                DEFLON = DEFLON,
                **kwargs
            )
        raise HTTPError(404)

    @cherrypy.expose
    def aproutes_geojson(self,node):
        gjs = { "type": "FeatureCollection","features": [] }

        reachable = [node]
        docs = list(self._mdb["routes"].find({"start":node},sort=[("etx",-1)]))
        if len(docs) > 0:
            maxetx = docs[0]["etx"]
            for d in docs:
                reachable.append(d["target"])
                gjs["features"].append( self.route2gjs(d,maxetx) )

        docs = self.get_aps( sort = [("last_ts",-1)] )
        for d in docs:
            if d["hostname"] not in reachable:
                d["state"] = "unreachable"
            elif d["hostname"] == node:
                d["state"] = "selected"
            gjs["features"].append( self.ap2gjs(d) )

        cherrypy.response.headers['Content-Type'] = 'application/json'
        return bytes(json.dumps(gjs),"utf-8")



