#!/usr/bin/env python3
import sys
sys.stdout = sys.stderr

import atexit
import json
import calendar
import pprint
from base import *

logger=logging.getLogger("Root")

if cherrypy.__version__.startswith('3.0') and cherrypy.engine.state == 0:
    cherrypy.engine.start(blocking=False)
    atexit.register(cherrypy.engine.stop)

class Root():
    def __init__(self,mdb,idb):
        self._idb = influx.InfluxDB("localhost",8086,"lora","freifunk","freifunk",debug=False)

    @cherrypy.expose
    @cherrypy.tools.allow(methods=['POST'])
    def default(self,*args,**kwargs):
        js = json.loads( cherrypy.request.body.read().decode('utf-8') )
        tstr,_,nsec = js.get("metadata",{}).get("time").rpartition(".")
        ts = calendar.timegm( time.strptime(tstr,"%Y-%m-%dT%H:%M:%S") )
        nsec = int(nsec.rstrip("Z"))
        nts = ts * 1000000000 + nsec
        tags = {}
        for a in ["dev_id","app_id","hardware_serial"]:
            tags[a] = js.get(a)
        idps = []
        for k,v in js.get("payload_fields",{}).items():
            t = tags.copy()
            t["field"] = k
            idps.append({
                "measurement":  "lora",
                "timestamp":    nts,
                "tags":         t,
                "fields":       {"value":float(v)},
            })
        self._idb.write_points(idps)

application = startapp( Root )
