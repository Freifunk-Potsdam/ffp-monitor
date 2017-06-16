#!/usr/bin/env python3
import sys
sys.stdout = sys.stderr

import atexit
import gzip
import hashlib
from base import *
from apdb import ApDb
from changes import Changes
import ips

logger=logging.getLogger("Root")

if cherrypy.__version__.startswith('3.0') and cherrypy.engine.state == 0:
    cherrypy.engine.start(blocking=False)
    atexit.register(cherrypy.engine.stop)

class Root(ApDb,Changes):
    def __init__(self,mdb,idb):
        self._mdb = mdb
        self._idb = idb
        self.htdir = os.path.join(os.path.dirname(os.path.realpath(__file__)),"htdocs")
        self.tpldir = os.path.join(os.path.dirname(os.path.realpath(__file__)),"tpl")
        self.tplenv = jinja2.Environment( 
            loader = jinja2.FileSystemLoader( self.tpldir ),
            trim_blocks = True,
            lstrip_blocks = True
        )
        self.tplenv.globals["ips"] = ips

    def get_tpl(self, *args):
        for t in args:
            try:
                return self.tplenv.get_template( t )
            except jinja2.exceptions.TemplateNotFound:
                pass

    def serve_site(self, tpl, **kwargs):
        if "myurl" not in kwargs:
            kwargs["myurl"] = tpl
        tpl = self.get_tpl( tpl, "%s.html" % tpl )
        if tpl is not None:
            return tpl.render( me = self, **kwargs )
        raise HTTPError(404,"Template not found.")

    def getip(self):
        if "X-Forwarded-For" in cherrypy.request.headers:
            return cherrypy.request.headers["X-Forwarded-For"]
        else:
            return cherrypy.request.remote.ip

    @cherrypy.expose
    def default(self,name):
        print("Looking for static site %s." % name)
        fname = os.path.abspath(os.path.join(self.htdir,name))
        if os.path.commonprefix([fname,self.htdir]) == self.htdir and os.path.exists(fname):
            return serve_file(os.path.join(fname))
        return self.serve_site( name )

    @cherrypy.expose
    def index(self):
        raise HTTPRedirect("apdb")

    @cherrypy.expose
    def grafana(self, dashboard, **kwargs):
        q = "&".join([ "var-%s=%s" % (k,v) for k,v in kwargs.items() ])
        if dashboard == "nov":
            raise HTTPRedirect( "https://monitor.freifunk-potsdam.de/grafana/dashboard/db/stat-node-overview?" + q )
        elif dashboard == "lp":
            raise HTTPRedirect( "https://monitor.freifunk-potsdam.de/grafana/dashboard/db/stat-link-performance?" + q )


application = startapp( Root )
