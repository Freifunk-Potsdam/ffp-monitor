#!/usr/bin/env python3

import sys
if sys.version_info[0]<3:
    print ("At least Python Version 3 is needed.")
    sys.exit(3)

import cherrypy
from cherrypy import HTTPError
from cherrypy._cperror import HTTPRedirect
from cherrypy.lib.static import serve_fileobj, serve_file
import logging
import os
import json
from bson.objectid import ObjectId
from pymongo import MongoClient
import influx

logging.basicConfig(level=logging.WARNING)

cherrypy.config.update({
    'environment': 'embedded',
})

class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return json.JSONEncoder.default(self, o)

mongodbe = MongoClient()
mongodb = mongodbe["freifunk"]
influxdb = influx.InfluxDB("localhost",8086,"freifunk","freifunk","freifunk",debug=False)

def startapp(app):
    return cherrypy.Application( app( mongodb, influxdb ) , script_name=None, config=None)

class DbOwner():
    def __init__(self,mdb,idb):
        self._mdb = mdb
        self._idb = idb

    @cherrypy.expose
    def default(self,name):
        tpldir = os.path.join(os.path.dirname(os.path.realpath(__file__)),"htdocs")
        fname = os.path.abspath(os.path.join(tpldir,name))
        print(fname)
        if os.path.commonprefix([fname,tpldir]) == tpldir and os.path.exists(fname):
            return serve_file(os.path.join(fname))
        raise HTTPError(404)

    def getip(self):
        if "X-Forwarded-For" in cherrypy.request.headers:
            return cherrypy.request.headers["X-Forwarded-For"]
        else:
            return cherrypy.request.remote.ip


