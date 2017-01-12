#!/usr/bin/env python3
from base import *
import ips

class Changes:
    @cherrypy.expose
    def changes(self, hosts="", params=""):
        return self.serve_site("changes", cssprefix = "changes", jsonurl = "/ff/changes.json?hosts=%s&params=%s" % (hosts,params) )

    @cherrypy.expose
    def changes_json(self, hosts = "", params = "", since = 0):
        now = time.time() - 5
        since = max( floatdef(since), now - 7 * 24 * 60 * 60)
        hosts = None if hosts == "" else hosts.split(",")
        params = None if params == "" else params.split(",")
        self._mdb["changes"].ensure_index("time")
        self._mdb["changes"].ensure_index("host")
        self._mdb["changes"].ensure_index("param")
        q = { "time": { "$gt": since } }
        if hosts is not None:
            q["host"] = { "$in": hosts }
        if params is not None:
            q["param"] = { "$in": params }
        changes = self._mdb["changes"].find( q, sort = [("time",1)], limit = 1000 )
        cols = [
            ["param","style",{"role":"style"}],
            ["ctime","Zeit",{"type":"time"}],
            ["host","Hostname"],
            ["param","Parameter"],
            ["old","Wert Vorher"],
            ["new","Wert Nachher"],
        ]
        cherrypy.response.headers['Content-Type'] = 'application/json'
        return self.gen_changes_json(changes,cols,since)

    def gen_changes_json(self,changes,cols,since):
        now = time.time()
        data = []
        last_ts = since
        for change in changes:
            last_ts = max(last_ts,change["time"])
            adata = []
            for c in cols:
                tpl = self.get_tpl( "changes/%s.html" % c[0] )
                if tpl is None:
                    v = change.get( c[0], None )
                    t = c[2]["type"] if len(c) > 2 and "type" in c[2] else "string"
                    if t == "string":
                        adata.append( str( v ) )
                    elif t == "number":
                        adata.append({ "v": floatdef(v), "f": str(v) })
                    elif t == "time":
                        adata.append({ "v": floatdef(v), "f": time.strftime( "%Y-%m-%d %H:%M:%S", time.localtime( intdef(v) ) ) })
                    else:
                        adata.append( v )
                else:
                    adata.append( tpl.render( change = change, ips = ips ) )
            data.append(adata)
        res = { "data": data, "cols": [], "last_ts": last_ts }
        for c in cols:
            col = { "label": c[1], "type": "string", "class":c[0] }
            if len(c) > 2:
                for k,v in c[2].items():
                    col[k] = v
            if col["type"] in ["time"]:
                col["type"] = "number"
            res["cols"].append( col )
        return bytes(json.dumps( res ),"utf-8")
