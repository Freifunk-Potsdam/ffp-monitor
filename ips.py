from base import *

FFNETS = ["10.22.", "6.", "172.22.25"]
PRIVNETS = [
    "10.",
    "192.168.",
] + [ "172.%d." % x for x in filter(lambda x: x!=22, range(16,32)) ]

FFNETMESH = [ "10.22.253.", "10.22.254.", "10.22.16." ]
FFNETKK = [ "10.22.255.", "10.22.31." ]
FFNETBB = [ "10.22.250.", "10.22.251." ]
FFNETVPN = [ "172.22.25" ]
FFNETDHCP32 = [ "10.22.%d." % x for x in range(64,128) ]
FFNETDHCP64 = [ "10.22.%d." % x for x in range(128,160) ]
FFNETDHCP128 = [ "10.22.%d." % x for x in range(160,192) ]
FFNETDHCP256 = [ "10.22.%d." % x for x in range(192,250) ]
FFNETDHCPEXT = [ "10.22.%d." % x for x in range(17,31) ]
FFNETDHCP = FFNETDHCP32 + FFNETDHCP64 + FFNETDHCP128 + FFNETDHCP256 + FFNETDHCPEXT
FFNETSERVICE = [ "6." ]

FFNETSORT = [ "10.22.254.", "10.22.255.", "10.22.250.", "10.22.", "6.", "172.22.25" ]

def ffhostname(ip):
    r = mongodb["names"].find_one({"localIP":ip})
    return None if r is None else r.get("hostname",None)

def isinnets(ip,nets):
    for n in nets:
        if ip.startswith(n):
            return True
    return False

def isffip(ip):
    for n in FFNETS:
        if ip.startswith(n):
            return True
    return False

def isffvpn(ip):
    for n in FFNETVPN:
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

def anyextgateway(*gateways):
    for r in gateways:
        if not isffip(r):
            return True
    return False

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

