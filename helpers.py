#!/usr/bin/env python3
import shlex
import copy
from math import radians, cos, sin, asin, sqrt
from defs import FFNETSORT,FFNETS,LINKCOLORS,PRIVNETS

def intdef(s,default=0):
    try:
        return int(s)
    except:
        return default

def floatdef(s,default=0.0):
    try:
        return float(s)
    except:
        return default

def tryround(n,d=0):
    return round(n,d) if isinstance(n,float) else n

def getelem(data,elem,default=None):
    name,_,elem = elem.partition(".")
    if name in data:
        data = data[name]
        if elem == "":
            return data
        else:
            return getelem(data,elem,default)
    else:
        return default

def calcnet(ip,mask):
    ip = [int(x) for x in ip.split(".")]
    mask = [int(x) for x in mask.split(".")]
    ipn = 0
    for i in ip:
        ipn = ipn * 256 + i
    maskn = 0
    for i in mask:
        maskn = maskn * 256 + i
    bits = 0
    for i in range(31,-1,-1):
        if maskn & (2**i) == 0:
            break
        bits += 1
    netn = ipn & ~(2**(32-bits) - 1)
    net = []
    for i in range(4):
        net.insert(0,netn % 256)
        netn = netn // 256
    return ".".join([str(x) for x in net]), bits

def etx2color(etx):
    es = list(LINKCOLORS.keys())
    es.sort(reverse=True)
    for e in es:
        if etx >= e:
            return LINKCOLORS[e]
    return LINKCOLORS[es[-1]]

def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    km = 6367 * c
    return km

def link(href,text,target=""):
    return "<a target='%s' href='%s'>%s</a>" % (target,href,text)

def img(src,title="",width="",height=""):
    return "<img title='%s' src='%s' width='%s' height='%s'>" % (title,src,width,height)

def dict2str(d, pad=0):
    s = ""
    for k,v in d.items():
        if type(v) == dict:
            s += ("    " * pad) + "%s = {\n" % k
            s += dict2str(v, pad + 1)
            s += ("    " * pad) + "}\n"
        else:
            s += ("    " * pad) + "%s = %s\n" % (k,str(v))
    return s

def dict2html(d):
    s = "<ul>"
    for k,v in d.items():
        if type(v) == dict:
            s += "<li>%s = {<br>" % k
            s += dict2html(v)
            s += "}</li>"
        else:
            s += "<li>%s = %s</li>" % (k,str(v))
    s += "</ul>"
    return s

def formatValue( value, fact, suffixes ):
    n = 0
    formattedVal = value
    while abs(formattedVal) >= fact:
        formattedVal /= fact
        n += 1
    if n < len(suffixes):
        suffix = suffixes[n]
    else:
        suffix = suffixes[-1]
        while n >= len(suffixes):
            formattedVal *= fact
            n -= 1
    formattedVal = round(formattedVal * 10) / 10
    return formattedVal, suffix

def formatDuration(v):
    res = ""
    v,s = divmod(v,60)
    v,m = divmod(v,60)
    d,h = divmod(v,24)
    if (d > 0):
        res += "%dd " % d;
    if (h > 0):
        res += "%dh " % h;
    if (m > 0):
        res += "%dm " % m;
    return res.strip()

def isffip(ip):
    for n in FFNETS:
        if ip.startswith(n):
            return True
    return False

def isextip(ip):
    for n in FFNETS+PRIVNETS:
        if ip.startswith(n):
            return False
    return True

def ffipsort(l):
    l = list(set(l))
    rl = []
    for s in FFNETSORT:
        tl = []
        i = 0
        while i < len(l):
            if l[i].startswith(s):
                tl.append(l[i])
                del l[i]
            else:
                i += 1
        tl.sort()
        rl += tl
    return rl + l

def ffip2link(l):
    if not isinstance(l,list):
        return ffip2link([l])[0]
    l = copy.copy(l)
    for i in range(len(l)):
        if isffip(l[i]):
            l[i] = link("http://%s/" % l[i],l[i],"_blank")
    return l

def hideextip(l,host):
    if not isinstance(l,list):
        return hideextip([l],host)[0]
    for i in range(len(l)):
        if isextip(l[i]):
            l[i] = link("showwanipof/%s" % host,"[hidden]","_blank")
    return l

def hasextroute(d):
    for r in d.get("routes",[]):
        if not isffip(r):
            return True
    return False
