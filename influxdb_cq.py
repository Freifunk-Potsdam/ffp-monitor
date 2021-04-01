#!/usr/bin/env python3

rqs_hourly = [
    ("oneyear","10m","3h"),
]
rqs_daily = [
    ("oneyear","10m","48h"),
    ("fiveyear","1h","3d"),
    ("forever","1d","7d"),
]
agr_stat = ["min","max","mean","median"]

config = {
    "router_count":{
        "base":["twodays","router_count","count"],
        "agr":["max"],
        "hourly":[
            ("oneyear","1h","1d"),
        ],
        "daily":[
            ("oneyear","1h","3d"),
            ("forever" ,"1d","7d"),
        ]
    },
    "traffic_tx":{
        "base":["network","tx_bytes"],
        "tags":["device","hostname"],
        "agr_first":[("last","non_negative_derivative")],
        "agr":["sum"],
        "hourly":rqs_hourly,
        "daily": rqs_daily,
    },
    "traffic_rx":{
        "base":["network","rx_bytes"],
        "tags":["device","hostname"],
        "agr_first":[("last","non_negative_derivative")],
        "agr":["sum"],
        "hourly":rqs_hourly,
        "daily": rqs_daily,
    },
    "links":{
        "base":[{"linkQuality":"lq","neighborLinkQuality":"nlq"}],
        "tags":["localIP","remoteIP","remoteHostname","hostname"],
        "agr":agr_stat,
        "hourly":rqs_hourly,
        "daily": rqs_daily,
    },
    "dhcp":{
        "base":["leases"],
        "tags":["network","hostname"],
        "agr":agr_stat,
        "hourly":rqs_hourly,
        "daily": rqs_daily,
    },
    "wireless":{
        "base":["assoc"],
        "tags":["device","essid","hostname"],
        "agr":agr_stat,
        "hourly":rqs_hourly,
        "daily": rqs_daily,
    },
}

def generate_queries(cfg,tint):
    for dst_meas,dcfg in cfg.items():
        if len(dcfg["base"]) < 1:
            print("%s: no base config" % dst_meas)
            continue
        fields = dcfg["base"][-1]
        src_meas = dcfg["base"][-2] if len(dcfg["base"]) >= 2 else dst_meas
        src_rp =   dcfg["base"][-3] if len(dcfg["base"]) >= 3 else None
        if isinstance(fields,dict):
            src_fields = []
            dst_fields = []
            for s,d in fields.items():
                src_fields.append(s)
                dst_fields.append(d)
        elif isinstance(fields,list) or isinstance(fields,tuple):
            src_fields = fields
            dst_fields = fields
        else:
            src_fields = [ fields ]
            dst_fields = [ fields ]
        if tint in dcfg:
            first = True
            for dst_rp,t_group,t_range in dcfg[tint]:
                sel = []
                for sf,df in zip( src_fields, dst_fields ):
                    agrcfg = dcfg["agr_first"] if "agr_first" in dcfg and first else dcfg["agr"]
                    for agr in agrcfg:
                        if isinstance(agr,list) or isinstance(agr,tuple):
                            agrn = "_".join(agr)
                        else:
                            agrn = agr
                        if len(dcfg["agr"]) == 1:
                            n = df
                        elif len(src_fields) == 1:
                            n = agrn
                        else:
                            n = '%s_%s' % (df,agrn)
                        if not first:
                            sf = n
                        if isinstance(agr,list) or isinstance(agr,tuple):
                            s = '"%s"' % sf
                            for a in agr:
                                s = '%s(%s)' % (a,s)
                        else:
                            s = '%s("%s")' % (agr,sf)
                        s += ' AS "%s"' % n
                        sel.append( s )
                q = 'SELECT %s INTO "%s"."%s" FROM ' % ( ",".join(sel), dst_rp, dst_meas )
                if src_rp:
                    q += '"%s".' % src_rp
                q += '"%s" ' % src_meas
                q += 'WHERE time > NOW() - %s ' % t_range
                q += 'GROUP BY %s fill(none)' % (",".join( ['time(%s)' % t_group] + dcfg.get("tags",[]) ))
                yield q
                first = False
                src_rp = dst_rp
                src_meas = dst_meas
        else:
            print("%s: No config for %s" % (dst_meas,tint))

import sys
import subprocess
if __name__ == "__main__" and len(sys.argv) > 1:
    if len(sys.argv) > 2:
        config = { sys.argv[2]: config[sys.argv[2]] } if sys.argv[2] in config else {}
    for q in generate_queries( config, sys.argv[1] ):
        print(q)
        sys.stdout.flush()
        if len(sys.argv) <= 3:
            p = subprocess.run(["influx","-host","influxdb","-database","freifunk","-execute",q],stderr=subprocess.STDOUT)
        print()
