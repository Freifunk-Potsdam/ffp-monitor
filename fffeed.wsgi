#!/usr/bin/env python3
import sys
sys.stdout = sys.stderr

import atexit
import gzip
import hashlib
import cherrypy
from cherrypy import HTTPError
from cherrypy._cperror import HTTPRedirect
from cherrypy.lib.static import serve_fileobj, serve_file
import logging
import os
import time

logger=logging.getLogger("Root")

if cherrypy.__version__.startswith('3.0') and cherrypy.engine.state == 0:
    cherrypy.engine.start(blocking=False)
    atexit.register(cherrypy.engine.stop)

class Root():
    @cherrypy.expose
    @cherrypy.tools.allow(methods=['POST'])
    def feed(self,f):
        ip = self.getip()
        if type(f) is cherrypy._cpreqbody.Part and f.file:
            data = f.file.read()
            try:
                data = gzip.decompress(data)
            except OSError:
                pass
            h = hashlib.md5(data).hexdigest()
            out = open(os.path.join("/var/ffdata","%s_%d_%s.xml" % (ip,time.time(),h)),"wb")
            out.write(data)
            out.close()
            return "success"
        raise HTTPError("400 No file")

    def getip(self):
        if "X-Forwarded-For" in cherrypy.request.headers:
            return cherrypy.request.headers["X-Forwarded-For"]
        else:
            return cherrypy.request.remote.ip

application = cherrypy.Application( Root() , script_name=None, config=None)

