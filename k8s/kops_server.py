#!/usr/bin/env python3

#  Copyright 2018 U.C. Berkeley RISE Lab
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from add_nodes import add_nodes
import logging
import os
from remove_node import remove_node
import subprocess
import util
import zmq

logging.basicConfig(filename='log.txt',level=logging.INFO)

def run():
    context = zmq.Context(1)
    restart_pull_socket = context.socket(zmq.REP)
    restart_pull_socket.bind('tcp://*:7000')

    churn_pull_socket = context.socket(zmq.PULL)
    churn_pull_socket.bind('tcp://*:7001')

    poller = zmq.Poller()
    poller.register(restart_pull_socket, zmq.POLLIN)
    poller.register(churn_pull_socket, zmq.POLLIN)

    # waits until the kubecfg file gets copied into the pod -- this might be
    # brittle if we try to move to a non-Ubuntu setting, but I'm not worried
    # about that for now
    while not os.path.isfile('/root/.kube/config'):
        pass

    client = util.init_k8s()

    while True:
        socks = dict(poller.poll())

        if churn_pull_socket in socks and socks[churn_pull_socket] == \
                zmq.POLLIN:

            msg = churn_pull_socket.recv_string()
            args = msg.split(':')

            if args[0] == 'add':
                num = int(args[1])
                ntype = args[2]
                logging.info('Adding %d new %s node(s)...' % (num, ntype))

                mon_ips = util.get_pod_ips(client, 'role=monitoring')
                route_ips = util.get_pod_ips(client, 'role=routing')

                add_nodes(client, [ntype], [num], mon_ips, route_ips)
                logging.info('Successfully added %d %s node(s).' % (num, ntype))
            elif args[0] == 'remove':
                ip = args[1]
                ntype = args[2]

                remove_node(ip, ntype)
                logging.info('Successfully removed node %s.' % (ip))
        if restart_pull_socket in socks and socks[restart_pull_socket] == \
                zmq.POLLIN:

            msg = restart_pull_socket.recv_string()
            args = msg.split(':')

            ip = args[1]
            pod = util.get_pod_from_ip(client, ip)

            count = str(pod.status.container_statuses[0].restart_count)

            logging.info('Returning restart count ' + count + ' for IP ' + ip + '.')
            restart_pull_socket.send_string(count)

if __name__ == '__main__':
    run()
