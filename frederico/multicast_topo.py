"""
Frederico Sales <frederico.sales@engenharia.ufjf.br>
Engenharia Computacional - 201765803B
Topicos de rede e processamento distribuido II
Prof. Dr. Alex Borges

run: sudo mn --custon multicast_topo.py --topo readTopo --switch ovsk --controller remote --mac --link tc

topo:
                    -- h1
           | -- s2 | 
c1 -- s1 --|        -- h2
           | -- s3 -- h3

"""

import sys, os, json
from mininet.topo import Topo 

def LoadTopo(file_name):
    """Load the topology."""

    # read file
    json_str = ''
    with open(file_name, "r") as file:
        for line in file:
            json_str += line.replace('\n', '').strip()
    
    # load JSON
    topo = json.loads(json_str)
    return topo

class readTopo(Topo):
    """Topology class"""

    def __init__(self):
        """Constructor."""

        # initialize topology
        Topo.__init__(self)

        # load the topology
        topo_data = LoadTopo("topo.json")

        # add hosts and switches
        node = {}
        for name in topo_data["node"]:
            if name[0] == 's':
                # switch
                node[name] = self.addSwitch(str(name))
            elif name[0] in {'c', 'h'}:
                # cam or host
                node[name] = self.addHost(str(name))

        # set links
        for link_obj in topo_data["link"]:
            # data mapping
            src = node[link_obj["src"]]
            dst = node[link_obj["dst"]]
            p1 = link_obj["p1"]
            p2 = link_obj["p2"]
            linkopts = dict(
                bw     = link_obj.setdefault('bw', 10),
                delay  = link_obj.setdefault('delay', '10ms'),
                jitter = link_obj.setdefault('jitter', '10ms'),
                loss   = link_obj.setdefault('loss', 1.5)
            )
        # set link
        self.addLink(src, dst, port=p1, port2=p2, **linkopts)

topos = { 'readTopo': ( lambda: readTopo() )}
