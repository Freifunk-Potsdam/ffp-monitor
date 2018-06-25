#!/usr/bin/env python3
import json
import time
import requests

def improve_str(s):
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    replace = "_"
    r = ""
    for c in s:
        r += c if c in chars else replace
    return r.strip(replace)

def str_replace(s,repl):
    for k,v in repl.items():
        s = s.replace(k,v)
    return s

class InfluxDBError(Exception):
    pass

class InfluxDB():
    BATCH_SIZE = 5000
    def __init__(self,host,port,name,user=None,password=None,debug=False):
        self.dbhost = host
        self.dbport = port
        self.dbname = name
        self.dbuser = user
        self.dbpass = password
        self.debug = debug

    def query(self,q):
        if self.dbuser is not None and self.dbpass is not None:
            a = requests.auth.HTTPBasicAuth(self.dbuser,self.dbpass)
            r = requests.get("http://%s:%d/query?db=%s" % (self.dbhost,self.dbport,self.dbname),auth=a,params={"q":q})
        else:
            r = requests.get("http://%s:%d/query?db=%s" % (self.dbhost,self.dbport,self.dbname),params={"q":q})
        return r.json()

    def measurements(self):
        meas = []
        r = self.query("SHOW MEASUREMENTS")
        for r in r.get("results",[]):
            for s in r.get("series",[]):
                for v in s.get("values",[]):
                    meas += v
        return meas

    def tag_keys(self, meas = None):
        keys = []
        q = "SHOW TAG KEYS"
        if meas is not None:
            q += " FROM \"%s\"" % meas
        r = self.query(q)
        for r in r.get("results",[]):
            for s in r.get("series",[]):
                for v in s.get("values",[]):
                    keys += v
        return keys

    def tag_values(self, tag, meas = None, **kwargs):
        vals = []
        q = "SHOW TAG VALUES"
        if meas is not None:
            q += " FROM \"%s\"" % meas
        q += " WITH KEY = \"%s\"" % tag
        if len(kwargs) > 0:
            q += " WHERE " + (" AND ".join(["\"%s\" = '%s'" % x for x in kwargs.items()]))
        r = self.query(q)
        for r in r.get("results",[]):
            for s in r.get("series",[]):
                for v in s.get("values",[]):
                    vals += v
        return vals

    def write_points(self,data):
        while len(data) > 0:
            s = ""
            for d in data[:self.BATCH_SIZE]:
                if "measurement" in d and "fields" in d:
                    s += d["measurement"]
                    if "tags" in d:
                        for k,v in d["tags"].items():
                            s += ",%s=%s" % (improve_str(k),str_replace(str(v),{"'":"",'"':"",",":"\,"," ":"\ "}))
                    s += " "
                    fs = []
                    for k,v in d["fields"].items():
                        f = "%s=" % improve_str(k)
                        if isinstance(v,str):
                            f += '"'+v.replace('"','\"')+'"'
                        elif isinstance(v,int):
                            f += str(v)+"i"
                        elif isinstance(v,float):
                            f += str(v)
                        elif isinstance(v,bool):
                            f += "True" if v else "False"
                        else:
                            break
                        fs.append(f)
                    s += ",".join(fs)
                    if "timestamp" in d:
                        s += " " + str(d["timestamp"])
                    s += "\n"
            if len(s) > 0:
                if self.debug:
                    f = open("/var/ffdata/influx_%d.log" % int(time.time()),"at")
                    f.write(s)
                    f.close()
                if self.dbuser is not None and self.dbpass is not None:
                    a = requests.auth.HTTPBasicAuth(self.dbuser,self.dbpass)
                    r = requests.post("http://%s:%d/write?db=%s" % (self.dbhost,self.dbport,self.dbname),auth=a,data=s)
                else:
                    r = requests.post("http://%s:%d/write?db=%s" % (self.dbhost,self.dbport,self.dbname),data=s)
                if r.status_code == 500 and r.json().get("error",None) == "timeout":
                    # Got timeout trying again after some seconds
                    time.sleep(3)
                    continue
                elif r.status_code != 204:
                    raise InfluxDBError(r.status_code,r.text)
            data = data[self.BATCH_SIZE:]

