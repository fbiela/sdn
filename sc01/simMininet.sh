#!/bin/bash
#
# After start 
#
# h1
# ip addr del 10.0.0.1/8 dev h1-eth0
# ip link add link h1-eth0 name h1-eth0.2 type vlan id 2
# ip addr add 10.0.0.1/8 dev h1-eth0.2
# ip link set dev h1-eth0.2 up
#
# h2
# ip addr del 10.0.0.2/8 dev h1-eth0
# ip link add link h2-eth0 name h2-eth0.2 type vlan id 2
# ip addr add 10.0.0.1/8 dev h2-eth0.2
# ip link set dev h2-eth0.2 up
#
# h3
# ip addr del 10.0.0.3/8 dev h3-eth0
# ip link add link h3-eth0 name h3-eth0.110 type vlan id 110
# ip addr add 10.0.0.1/8 dev h3-eth0.110
# ip link set dev h3-eth0.110 up
#
#
# h4
# ip addr del 10.0.0.4/8 dev h4-eth0
# ip link add link h4-eth0 name h4-eth0.110 type vlan id 110
# ip addr add 10.0.0.1/8 dev h4-eth0.110
# ip link set dev h4-eth0.110 up
#
# 
#
sudo mn -c;
clear;
sudo mn --topo single,4 --mac --switch ovsk --controller remote -x

