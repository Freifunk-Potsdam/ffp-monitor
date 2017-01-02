FFNETS = ["10.22.", "6."]
PRIVNETS = [
    "10.",
    "192.168.",
    "172.16.","172.17.","172.18.","172.19.","172.20.","172.21.","172.22.","172.23.","172.24.","172.25.","172.26.","172.27.","172.28.","172.29.","172.30.","172.31.",
]

FFNETSORT = ["10.22.254.", "10.22.255.", "10.22.250.", "10.22.", "6."]

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

