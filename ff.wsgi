#!/usr/bin/env python3
import sys
sys.stdout = sys.stderr

import atexit
import gzip
import hashlib
from base import *
from defs import *
from helpers2 import *

logger=logging.getLogger("Root")

if cherrypy.__version__.startswith('3.0') and cherrypy.engine.state == 0:
    cherrypy.engine.start(blocking=False)
    atexit.register(cherrypy.engine.stop)

class Root(DbOwner):
#    @cherrypy.expose
#    @cherrypy.tools.allow(methods=['POST'])
#    def feed(self,f):
#        ip = self.getip()
#        if type(f) is cherrypy._cpreqbody.Part and f.file:
#            data = f.file.read()
#            try:
#                data = gzip.decompress(data)
#            except OSError:
#                pass
#            h = hashlib.md5(data).hexdigest()
#            out = open(os.path.join("/var/ffdata","%s_%d_%s.xml" % (ip,time.time(),h)),"wb")
#            out.write(data)
#            out.close()
#            return "success"
#        raise HTTPError("400 No file")

    @cherrypy.expose
    def index(self):
        raise HTTPRedirect("apdb")

    @cherrypy.expose
    def showwanipof(self,hostname,password=""):
        if password == "#showitnow!":
            n = self._mdb["nodes"].find_one({"hostname":hostname})
            return n["last_ip"]
        else:
            return self.default("pwinput.html")


    @cherrypy.expose
    def apdeletereal(self,hostname,password=""):
        if password == "#justdoit!":
            if self._mdb["nodes"].find_one({"hostname":hostname,"delete":True}) is not None:
                self._mdb["nodes"].remove({"hostname":hostname,"delete":True})
                self._mdb["names"].remove({"hostname":hostname})
                self._mdb["networks"].remove({"hostname":hostname})
            raise HTTPRedirect("apdel")
        else:
            return self.default("pwinput.html")

    @cherrypy.expose
    def apdelete(self,hostname,delete="True",redir="apdb"):
        delete = delete.lower() in ("yes", "true", "t", "1")
        self._mdb["nodes"].update({"hostname":hostname},{"$set":{"delete":delete}})
        raise HTTPRedirect(redir)

    @cherrypy.expose
    def apdel(self,q="",fmt=None):
        if fmt is None:
            return self.default("apdb.html")
        docs = list(self._mdb["nodes"].find(buildquery(q,{"delete":True}),sort=[("hostname",1)]))
        cols = ["style","hostname","ips","gateways","location","uptime",
            "device","firmware","scriptver","contact","lastdata","links2"]
        return fmtout(genjsdata(docs,cols),fmt)
       
    @cherrypy.expose
    def apdb(self,q="",fmt=None):
        if fmt is None:
            return self.default("apdb.html")
        docs = list(self._mdb["nodes"].find(buildquery(q),sort=[("hostname",1)]))
        cols = ["style","hostname","ips","gateways","wanip","location","uptime",
            "device","firmware","scriptver","contact","lastdata","links1"]
        return fmtout(genjsdata(docs,cols),fmt)

    @cherrypy.expose
    def apmap(self,maxetx=None,etxbase=None,fmt=None):
        maxetx = floatdef(maxetx,10)
        etxbase = intdef(etxbase,24)
        etxbase = etxbase if etxbase in [3,24] else 24
        if fmt is None:
            return self.default("apmap.html")
        if fmt == "geojson":
            gjs = { "type": "FeatureCollection","features": [] }

            docs = list(self._mdb["linkperf"].find({"etx%d" % etxbase:{"$lte":maxetx}},sort=[("etx%d" % etxbase,-1)]))
            for d in docs:
                gjs["features"].append(link2gjs(d,etxbase))

            docs = list(self._mdb["nodes"].find({"delete":{"$ne":True}},sort=[("last_ts",-1)]))
            for d in docs:
                gjs["features"].append(node2gjs(d))

            cherrypy.response.headers['Content-Type'] = 'application/json'
            return bytes(json.dumps(gjs,cls=JSONEncoder),"utf-8")
        raise HTTPError("404 Not Found")

    @cherrypy.expose
    def aproutes(self,node,fmt=None):
        if fmt is None:
            return self.default("aproutes.html")
        if fmt == "geojson":
            gjs = { "type": "FeatureCollection","features": [] }

            reachable = [node]
            docs = list(self._mdb["routes"].find({"start":node},sort=[("etx",-1)]))
            if len(docs) > 0:
                maxetx = docs[0]["etx"]
                for d in docs:
                    reachable.append(d["target"])
                    gjs["features"].append(route2gjs(d,maxetx))

            docs = list(self._mdb["nodes"].find({},sort=[("last_ts",-1)]))
            for d in docs:
                if d["hostname"] in reachable:
                    gjs["features"].append(node2gjs(d))
                else:
                    gjs["features"].append(node2gjs(d,NODEUNREACHCOLOR))

            cherrypy.response.headers['Content-Type'] = 'application/json'
            return bytes(json.dumps(gjs,cls=JSONEncoder),"utf-8")
        raise HTTPError("404 Not Found")



application = startapp( Root )
