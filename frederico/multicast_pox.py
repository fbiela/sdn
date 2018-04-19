#!/usr/bin/env python
# POX Multicast
#
from groupflow_shared import *
from mininet.net import *
from mininet.node import OVSSwitch, UserSwitch
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.node import Node, RemoteController
from scipy.stats import truncnorm
from numpy.random import randint, uniform
from subprocess import *
import sys
import signal
from time import sleep, time
from datetime import datetime
from multiprocessing import Process, Pipe
import numpy as np

ENABLE_FIXED_GROUP_SIZE = True
FIXED_GROUP_SIZE = 4

def mcastTest(topo, interactive = False, hosts = [], log_file_name = 'test_log.log', util_link_weight = 10, link_weight_type = 'linear', replacement_mode='none', pipe = None):
    membership_mean = 0.1
    membership_std_dev = 0.25
    membership_avg_bound = float(len(hosts)) / 8.0
    test_groups = []
    test_group_launch_times = []
    test_success = True
    

    # Launch the external controller
    pox_arguments = []
    if 'periodic' in replacement_mode:
        pox_arguments = ['pox.py', 'log', '--file=pox.log,w', 'openflow.discovery', '--link_timeout=30', 'openflow.keepalive',
                'openflow.flow_tracker', '--query_interval=1', '--link_max_bw=19', '--link_cong_threshold=13', '--avg_smooth_factor=0.5', '--log_peak_usage=True',
                'misc.benchmark_terminator', 'openflow.igmp_manager', 'misc.groupflow_event_tracer',
                'openflow.groupflow', '--util_link_weight=' + str(util_link_weight), '--link_weight_type=' + link_weight_type, '--flow_replacement_mode=' + replacement_mode,
                '--flow_replacement_interval=15',
                'log.level', '--WARNING', '--openflow.flow_tracker=INFO']
    else:
        pox_arguments = ['pox.py', 'log', '--file=pox.log,w', 'openflow.discovery', '--link_timeout=30', 'openflow.keepalive',
                'openflow.flow_tracker', '--query_interval=1', '--link_max_bw=19', '--link_cong_threshold=13', '--avg_smooth_factor=0.5', '--log_peak_usage=True',
                'misc.benchmark_terminator', 'openflow.igmp_manager', 'misc.groupflow_event_tracer',
                'openflow.groupflow', '--util_link_weight=' + str(util_link_weight), '--link_weight_type=' + link_weight_type, '--flow_replacement_mode=' + replacement_mode,
                '--flow_replacement_interval=15',
                'log.level', '--WARNING', '--openflow.flow_tracker=INFO']
    print 'Launching external controller: ' + str(pox_arguments[0])
    print 'Launch arguments:'
    print ' '.join(pox_arguments)
    
    with open(os.devnull, "w") as fnull:
        pox_process = Popen(pox_arguments, stdout=fnull, stderr=fnull, shell=False, close_fds=True)
        # Allow time for the log file to be generated
        sleep(1)
    
    # Determine the flow tracker log file
    pox_log_file = open('./pox.log', 'r')
    flow_log_path = None
    event_log_path = None
    got_flow_log_path = False
    got_event_log_path = False
    while (not got_flow_log_path) or (not got_event_log_path):
        pox_log = pox_log_file.readline()

        if 'Writing flow tracker info to file:' in pox_log:
            pox_log_split = pox_log.split()
            flow_log_path = pox_log_split[-1]
            got_flow_log_path = True
        
        if 'Writing event trace info to file:' in pox_log:
            pox_log_split = pox_log.split()
            event_log_path = pox_log_split[-1]
            got_event_log_path = True
            
            
    print 'Got flow tracker log file: ' + str(flow_log_path)
    print 'Got event trace log file: ' + str(event_log_path)
    print 'Controller initialized'
    pox_log_offset = pox_log_file.tell()
    pox_log_file.close()
    
    # External controller
    net = Mininet(topo, controller=RemoteController, switch=OVSSwitch, link=TCLink, build=False, autoSetMacs=True)
    # pox = RemoteController('pox', '127.0.0.1', 6633)
    net.addController('pox', RemoteController, ip = '127.0.0.1', port = 6633)
    net.start()
    for switch_name in topo.get_switch_list():
        #print switch_name + ' route add -host 127.0.0.1 dev lo'
        net.get(switch_name).controlIntf = net.get(switch_name).intf('lo')
        net.get(switch_name).cmd('route add -host 127.0.0.1 dev lo')
        #print 'pox' + ' route add -host ' + net.get(switch_name).IP() + ' dev lo'
        net.get('pox').cmd('route add -host ' + net.get(switch_name).IP() + ' dev lo')
        #print net.get(switch_name).cmd('ifconfig')
        
    topo.mcastConfig(net)
    
    #print 'Controller network configuration:'
    #print net.get('pox').cmd('ifconfig')
    #print net.get('pox').cmd('route')
    
    sleep_time = 8 + (float(len(hosts))/8)
    print 'Waiting ' + str(sleep_time) + ' seconds to allow for controller topology discovery'
    sleep(sleep_time)   # Allow time for the controller to detect the topology
    
    try:
        if interactive:
            CLI(net)
        else:
            mcast_group_last_octet = 1
            mcast_port = 5010
            rand_seed = int(time())
            print 'Using random seed: ' + str(rand_seed)
            np.random.seed(rand_seed)
            host_join_probabilities = generate_group_membership_probabilities(hosts, membership_mean, membership_std_dev, membership_avg_bound)
            print 'Host join probabilities: ' + ', '.join(str(p) for p in host_join_probabilities)
            host_join_sum = sum(p[1] for p in host_join_probabilities)
            print 'Measured mean join probability: ' + str(host_join_sum / len(host_join_probabilities))
            print 'Predicted average group size: ' + str(host_join_sum)
            i = 1
            congested_switch_num_links = 0
            
            while True:                
                print 'Generating multicast group #' + str(i)
                # Choose a sending host using a uniform random distribution
                sender_index = randint(0,len(hosts))
                sender_host = hosts[sender_index]
                
                receivers = []
                if ENABLE_FIXED_GROUP_SIZE:
                    while len(receivers) < FIXED_GROUP_SIZE:
                        receiver_index = randint(0,len(hosts))
                        if receiver_index == sender_index:
                            continue
                        receivers.append(hosts[receiver_index])
                        receivers = list(set(receivers))
                else:
                    # Choose a random number of receivers by comparing a uniform random variable
                    # against the previously generated group membership probabilities
                    for host_prob in host_join_probabilities:
                        p = uniform(0, 1)
                        if p <= host_prob[1]:
                            receivers.append(host_prob[0])

                # Initialize the group
                # Note - This method of group IP generation will need to be modified slightly to support more than
                # 255 groups
                mcast_ip = '224.1.1.{last_octet}'.format(last_octet = str(mcast_group_last_octet))
                test_groups.append(StaticMulticastGroupDefinition(sender_host, receivers, mcast_ip, mcast_port, mcast_port + 1))
                launch_time = time()
                test_group_launch_times.append(launch_time)
                print 'Launching multicast group #' + str(i) + ' at time: ' + str(launch_time)
                print 'Sender: ' + str(sender_host)
                print 'Receivers: ' + str(receivers)
                test_groups[-1].launch_mcast_applications(net)
                mcast_group_last_octet = mcast_group_last_octet + 1
                mcast_port = mcast_port + 2
                i += 1
                wait_time = 5 + uniform(0, 5)
                
                # Read from the log file to determine if a link has become overloaded, and cease generating new groups if so
                print 'Check for congested link...'
                congested_link = False
                pox_log_file = open('./pox.log', 'r')
                pox_log_file.seek(pox_log_offset)
                done_reading = False
                while not done_reading:
                    line = pox_log_file.readline()
     
                    if 'Network peak link throughput (Mbps):' in line:
                        line_split = line.split(' ')
                        print 'Peak Usage (Mbps): ' + line_split[-1],
                    if 'Network avg link throughput (Mbps):' in line:
                        line_split = line.split(' ')
                        print 'Mean Usage (Mbps): ' + line_split[-1],
                    if 'FlowStats: Fully utilized link detected!' in line:
                        line_split = line.split(' ')
                        congested_link = True
                        done_reading = True
                    if 'Multicast topology changed, recalculating all paths' in line or 'Path could not be determined for receiver' in line:
                        print 'ERROR: Network topology changed unexpectedly.'
                        print line
                        test_success =  False
                        done_reading = True
                    
                    if time() - launch_time > wait_time:
                        done_reading = True
                        
                pox_log_offset = pox_log_file.tell()
                pox_log_file.close()
                if congested_link:
                    print 'Detected fully utilized link, terminating simulation.'
                    break
                if not test_success:
                    print 'Detected network connectivity error, terminating simulation.'
                    break
                else:
                    print 'No congestion detected.'
        
        recv_packets = 0
        lost_packets = 0
        print 'Terminating network applications'
        for group in test_groups:
            group.terminate_mcast_applications()
        print 'Terminating controller'
        pox_process.send_signal(signal.SIGINT)
        sleep(1)
        print 'Waiting for network application termination...'
        for group in test_groups:
            group.wait_for_application_termination()
        print 'Network applications terminated'
        print 'Waiting for controller termination...'
        pox_process.send_signal(signal.SIGKILL)
        pox_process.wait()
        print 'Controller terminated'
        pox_process = None
        net.stop()

        if not interactive and test_success:
            write_final_stats_log(log_file_name, flow_log_path, event_log_path, membership_mean, membership_std_dev, membership_avg_bound, test_groups, test_group_launch_times, topo)
        
        if not test_success:
            call('rm -rfv ' + str(flow_log_path), shell=True)
        call('rm -rfv ' + str(event_log_path), shell=True)
        
    except BaseException as e:
        print str(e)
        test_success = False
    
    if pipe is not None:
        pipe.send(test_success)
        pipe.close()

topos = { 'mcast_test': ( lambda: MulticastTestTopo() ) }

def print_usage_text():
    print 'GroupFlow Multicast Testing with Mininet'
    print 'Usage:'
    print '1) No arguments:'
    print '> mininet_multicast_pox'
    print 'If no arguments are provided, the script will launch a hard-coded test topology with Mininet in interactive mode.'
    print ''
    print '2) Custom topology:'
    print '> mininet_multicast_pox <topology_path>'
    print 'topology_path: If a single argument is given, the argument will be interpreted as a path to a BRITE topology. Otherwise, this functions identically to the no argument mode.'
    print ''
    print '3) Automated benchmarking:'
    print '> mininet_multicast_pox <topology_path> <iterations_to_run> <log_file_prefix> <index_of_first_log_file> <parameter_sets (number is variable and unlimited)>'
    print 'Parameter sets have the form: flow_replacement_mode,link_weight_type,util_link_weight'
    print 'The topology path "manhattan" is currently hardcoded to generate a 20 Mbps, 5x5 Manhattan grid topology'

if __name__ == '__main__':
    setLogLevel( 'info' )
    if len(sys.argv) >= 2:
        if '-h' in str(sys.argv[1]) or 'help' in str(sys.argv[1]):
            print_usage_text()
            sys.exit()
    
    if len(sys.argv) >= 6:
        # Automated simulations - Differing link usage weights in Groupflow Module
        log_prefix = sys.argv[3]
        num_iterations = int(sys.argv[2])
        first_index = int(sys.argv[4])
        util_params = []
        for param_index in range(5, len(sys.argv)):
            param_split = sys.argv[param_index].split(',')
            util_params.append((param_split[0], param_split[1], float(param_split[2])))
        topo = None
        if 'manhattan' in sys.argv[1]:
            print 'Generating Manhattan Grid Topology'
            topo = ManhattanGridTopo(5, 5, 20, 1, True)
        else:
            print 'Generating BRITE Specified Topology'
            topo = BriteTopo(sys.argv[1])
        hosts = topo.get_host_list()
        start_time = time()
        num_success = 0
        num_failure = 0
        print 'Simulations started at: ' + str(datetime.now())
        for i in range(0,num_iterations):
            for util_param in util_params:
                test_success = False
                while not test_success:
                    parent_pipe, child_pipe = Pipe()
                    p = Process(target=mcastTest, args=(topo, False, hosts, log_prefix + '_' + ','.join([util_param[0], util_param[1], str(util_param[2])]) + '_' + str(i + first_index) + '.log', util_param[2], util_param[1], util_param[0], child_pipe))
                    sim_start_time = time()
                    p.start()
                    p.join()
                    sim_end_time = time()
                    
                    # Make extra sure the network terminated cleanly
                    call(['python', 'kill_running_test.py'])
                    
                    test_success = parent_pipe.recv()
                    parent_pipe.close()
                    print 'Test Success: ' + str(test_success)
                    if test_success:
                        num_success += 1
                    else:
                        num_failure += 1
                print 'Simulation ' + str(i+1) + '_' + ','.join([util_param[0], util_param[1], str(util_param[2])]) + ' completed at: ' + str(datetime.now()) + ' (runtime: ' + str(sim_end_time - sim_start_time) + ' seconds)'
                
        end_time = time()
        print ' '
        print 'Simulations completed at: ' + str(datetime.now())
        print 'Total runtime: ' + str(end_time - start_time) + ' seconds'
        print 'Average runtime per sim: ' + str((end_time - start_time) / (num_iterations * len(util_params))) + ' seconds'
        print 'Number of failed sims: ' + str(num_failure)
        print 'Number of successful sims: ' + str(num_success)
        
    elif len(sys.argv) >= 2:
        # Interactive mode - configures POX and multicast routes, but no automatic traffic generation
        print 'Launching BRITE defined multicast test topology'
        topo = BriteTopo(sys.argv[1])
        hosts = topo.get_host_list()
        mcastTest(topo, True, hosts)
        
    else:
        # Interactive mode with barebones topology
        print 'Launching default multicast test topology'
        topo = MulticastTestTopo()
        hosts = topo.get_host_list()
        mcastTest(topo, True, hosts)
