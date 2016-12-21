#!/usr/bin/env python3
import time

PREFIX = "/ff/"

DEFLON = 13.054457
DEFLAT = 52.389375

DEFQUERYFIELDS = ["hostname","sysinfo.location","sysinfo.mail","interface_config.addr","routes"]

FFNETS = ["10.22.", "6."]
PRIVNETS = ["10.","192.168.","172.16.","172.17.","172.18.","172.19.","172.20.","172.21.","172.22.",
    "172.23.","172.24.","172.25.","172.26.","172.27.","172.28.","172.29.","172.30.","172.31."]

FFNETSORT = ["10.22.254.", "10.22.255.", "10.22.250.", "10.22.", "6."]

LINKCOLORS = { 0: '#00CC00', 2: '#FFCB05', 4: '#FF6600', 10: '#BB3333' }

NODEUNREACHCOLOR = '#AAAAFF'
BGCOLORS = {
    "***"   :{ "color":"#AAAAAA", "mapcolor":"#555555", "last_ts":7 * 24 * 60 * 60,"opt":["del"]},
    "**"    :{ "color":"#FFAAAA", "mapcolor":"#FF0000", "last_ts":1 * 24 * 60 * 60 },
    "*"     :{ "color":"#FFFFAA", "mapcolor":"#FFFF00", "last_ts":     3 * 60 * 60 },
}

from helpers import *

def mkrouteinfo(d):
    s = ""
    dist = 0
    for i in range(1,len(d["c"])):
        dist += 1000 * haversine(d["c"][i-1][0],d["c"][i-1][1],d["c"][i][0],d["c"][i][1])
    dist = formatValue( dist, 1000, ["m", "km"] )
    s += "<tr><th>Total ETX:</th><th>%s</th></tr>\n" % round(d["etx"],3)
    s += "<tr><th>Total Distance:</th><td>%.1f %s</td></tr>\n" % ( dist[0], dist[1] )
    s += "<tr><th>Start:</th><td>%s</td></tr>\n" % d["start"]
    first = True
    for v in d["via"]:
        if first:
            s += "<tr><th rowspan='%d'>Via:</th><td>%s</td></tr>\n" % (len(d["via"]),v)
            first = False
        else:
            s += "<tr><td>%s</td></tr>\n" % v
    s += "<tr><th>Target:</th><td>%s</td></tr>\n" % d["target"]
    return "<table class='linkinfo'>\n%s</table>" % s

def mklinkinfo(d,etxbase=24):
    s = ""
    dist = formatValue(1000 * haversine(d["c"][0][0],d["c"][0][1],d["c"][1][0],d["c"][1][1]), 1000, ["m", "km"])
    l,r = d["left"],d["right"]
    s += ("<tr><th colspan='2'></th><th><h3>%s</h3></th><th style='text-align: right' colspan='2'>%s</th></tr>\n") % \
        (round(d["etx%d" % etxbase],3),grafanalinklinkperf(d["h"+l],d["h"+r]))
    s += "<tr><th colspan='2'>%s</th><td>%.1f %s</td><th colspan='2'>%s</th></tr>\n" % (
        d["h"+l], 
        dist[0],
        dist[1],
        d["h"+r]
    )
    for link in d["l"]:
        s += "<tr style='border-top: 1px solid;'>"
        s += "<th rowspan='3'>%s</th><td>%s</td><th>ETX</th><td>%s</td><th rowspan='3'>%s</th></tr>\n" % (
            link[l]["ip"], 
            tryround(link[l].get("etx%d" % etxbase,""),3), 
            tryround(link[r].get("etx%d" % etxbase,""),3), 
            link[r]["ip"],
        )
        s += "<tr><td>%s</td><th>LQ</th><td>%s</td></tr>\n" % (
            tryround(link[l].get("lq%d" % etxbase,""),2), 
            tryround(link[r].get("lq%d" % etxbase,""),2),
        )
        s += "<tr><td>%s</td><th>NLQ</th><td>%s</td></tr>\n" % (
            tryround(link[l].get("nlq%d" % etxbase,""),2),
            tryround(link[r].get("nlq%d" % etxbase,""),2),
        )
    return "<table class='linkinfo'>\n%s</table>" % s

def extract_style(d): 
    since_last_ts = int(time.time() - d["last_ts"])
    cs = list(BGCOLORS.values())
    cs.sort(key=lambda x: x["last_ts"],reverse=True)
    for c in cs:
        if since_last_ts > c["last_ts"]:
            return "background-color: %s" % c["color"]
    return ""

def extract_ips(d):
    ips = []
    try:
        d["interface_config"] = list(d["interface_config"].values())
    except:
        pass
    for i in d["interface_config"]:
        if isffip(i.get("addr","None")):
            ips.append(i.get("addr","None"))
    return "<br>".join(ffip2link(ffipsort(ips)))

def extract_contact(d):
    m = d.get("sysinfo",{}).get("mail","").strip()
    m = link("mailto:%s" % m,m) if "@" in m else m
    n = d.get("sysinfo",{}).get("note","").strip()
    return m + ("<br>" if len(n)>0 else "" ) + n

def extract_links1(d):
    links = [owmlink(d),grafanalinkoverwiew(d)]
    since_last_ts = int(time.time() - d["last_ts"])
    cs = list(BGCOLORS.values())
    cs.sort(key=lambda x: x["last_ts"],reverse=True)
    for c in cs:
        if since_last_ts > c["last_ts"]:
            if "del" in c.get("opt",[]):
                if d.get("delete",False):
                    links.append(img("%sdelgrey.png" % PREFIX,"Zum L&ouml;schen markiert","24px","24px"))
                else:
                    links.append(link("%sapdelete?hostname=%s" % (PREFIX,d["hostname"]), 
                        img("%sdel.png" % PREFIX,"Zum L&ouml;schen markieren","24px","24px")) )
            break
    return " ".join(links)

def extract_links2(d):
    links = [owmlink(d),grafanalinkoverwiew(d)]
    since_last_ts = int(time.time() - d["last_ts"])
    cs = list(BGCOLORS.values())
    cs.sort(key=lambda x: x["last_ts"],reverse=True)
    for c in cs:
        if since_last_ts > c["last_ts"]:
            if "del" in c.get("opt",[]):
                links.append(link("%sapdeletereal?hostname=%s" % (PREFIX,d["hostname"]), 
                    img("%sdel.png" % PREFIX,"L&ouml;schen","24px","24px")) )
                links.append(link("%sapdelete?delete=false&redir=apdel&hostname=%s" % (PREFIX,d["hostname"]),
                    img("%sdelgrey.png" %PREFIX,"L&ouml;schmarkierung aufheben","24px","24px")) )
            break
    return " ".join(links)

def extract_gjscolor(d): 
    since_last_ts = int(time.time() - d["last_ts"])
    cs = list(BGCOLORS.values())
    cs.sort(key=lambda x: x["last_ts"],reverse=True)
    for c in cs:
        if since_last_ts > c["last_ts"]:
            return c["mapcolor"]
    return '#00EE00'

COLDEFS = {
    "style":{
        "def":{"type":"string","role":"style"},
        "ext":extract_style,
    },
    "hostname":{
        "def":{"type":"string","label":"Hostname"},
        "ext":lambda d: d["hostname"],
    },
    "ips":{
        "def":{"type":"string","label":"IP(s)"},
        "ext":extract_ips,
    },
    "gateways":{
        "def":{"type":"string","label":"Gateway(s)"},
        "ext":lambda d: "<br>".join(ffip2link(d.get("routes",[]))),
    },
    "wanip":{
        "def":{"type":"string","label":"WAN-IP"},
        "ext":lambda d: ffip2link(hideextip(d["last_ip"],d["hostname"])),
    },
    "location":{
        "def":{"type":"string","label":"Standort"},
        "ext":lambda d: d.get("sysinfo",{}).get("location",""),
    },
    "uptime":{
        "def":{"type":"duration","label":"Uptime"},
        "ext":lambda d: d.get("uptime",0),
    },
    "fuptime":{
        "def":{"type":"duration","label":"Uptime"},
        "ext":lambda d: formatDuration(d.get("uptime",0)),
    },
    "device":{
        "def":{"type":"string","label":"Gerät"},
        "ext":lambda d: "%s<br>(%s)" % (d.get("sysinfo",{}).get("machine",""),d.get("sysinfo",{}).get("system type","")),
    },
    "firmware":{
        "def":{"type":"string","label":"Firmware"},
        "ext":lambda d: d.get("sysinfo",{}).get("firmware",""),
    },
    "scriptver":{
        "def":{"type":"string","label":"Script"},
        "ext":lambda d: "v"+d.get("sysinfo",{}).get("script",""),
    },
    "contact":{
        "def":{"type":"string","label":"Kontakt / Notizen"},
        "ext":extract_contact,
    },
    "lastdata":{
        "def":{"type":"duration","label":"Letzte Daten"},
        "ext":lambda d: int(time.time() - d["last_ts"]),
    },
    "flastdata":{
        "def":{"type":"duration","label":"Letzte Daten"},
        "ext":lambda d: formatDuration(int(time.time() - d["last_ts"])),
    },
    "links1":{
        "def":{"type":"string","label":"Links"},
        "ext":extract_links1,
    },
    "links2":{
        "def":{"type":"string","label":"Links"},
        "ext":extract_links2,
    },
}

def owmlink(d):
    return link("https://openwifimap.net/#detail?node=%s.olsr" % d["hostname"],
        img("%sowm.png" % PREFIX,"OpenWifiMap","24px","24px"),"_blank")

def grafanalinkoverwiew(d):
    return link("https://monitor.freifunk-potsdam.de/grafana/dashboard/db/node-overview?var-hostname=%s" % d["hostname"],
        img("%sgrafana.svg" % PREFIX,"Grafana","24px","24px"),"_blank")

def grafanalinklinkperf(ha,hb):
    return link("https://monitor.freifunk-potsdam.de/grafana/dashboard/db/link-performance?var-hostname=%s&var-remotehost=%s" % \
        (ha,hb),img("%sgrafana.svg" % PREFIX,"Grafana","24px","24px"),"_blank")

def extract_gjsinfo(d):
    s = ""
    rows = ["hostname","ips","gateways","location","fuptime",
        "device","firmware","scriptver","contact","flastdata","links1"]
    for r in rows:
        s += "<tr><th>%s</th><td>%s</td></tr>\n" % (COLDEFS[r]["def"]["label"],COLDEFS[r]["ext"](d))
    return "<table>\n%s</table>" % s

COLDEFS["gjscolor"] = {
    "gjsname":"color",
    "ext":extract_gjscolor,
}
COLDEFS["gjspopup"] = {
    "gjsname":"popup",
    "ext":lambda d: "<b>%s</b>" % d["hostname"],
}
COLDEFS["gjsinfo"] = {
    "gjsname":"info",
    "ext":extract_gjsinfo,
}
