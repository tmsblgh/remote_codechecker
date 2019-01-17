#!/usr/bin/env python3

"""
Server for handling remote analyze requests with CodeChecker.
"""

import os
import sys
import uuid
import argparse
import subprocess
import logging
import zipfile
import argparse
import docker
import redis

from enum import Enum
from random import randint

from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from thrift.server import TServer

sys.path.append('../gen-py')
from remote_analyze_api import RemoteAnalyze
from remote_analyze_api.ttypes import InvalidOperation

LOGGER = logging.getLogger('SERVER')
LOGGER.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
LOGGER.addHandler(ch)


class AnalyzeStatus(Enum):
    ID_PROVIDED = 'ID_PROVIDED'
    IN_PROGRESS = 'IN_PROGRESS'
    COMPLETED = 'COMPLETED'


class RemoteAnalyzeHandler:
    def __init__(self):
        self.log = {}

    def getId(self):
        LOGGER.info('Provide an id for the analysis')

        new_analyze_id = str(uuid.uuid4())

        REDIS_DATABASE.hset(new_analyze_id, 'state', AnalyzeStatus.ID_PROVIDED.name)

        new_analyze_dir = os.path.abspath(os.path.join(WORKSPACE, new_analyze_id))
        if not os.path.exists(new_analyze_dir):
            os.makedirs(new_analyze_dir)

        return new_analyze_id

    def analyze(self, analyze_id, zip_file):
        LOGGER.info('Store sources for analysis %s', analyze_id)

        file_name = 'source'
        file_extension = '.zip'

        file_path = os.path.join(WORKSPACE, analyze_id, file_name + file_extension)

        if os.path.isfile(file_path):
            expand = 1
            while True:
                expand += 1
                new_file_path = file_path.split(file_extension)[0] + '_' + str(expand) + file_extension
                if os.path.isfile(new_file_path):
                    continue
                else:
                    file_path = new_file_path
                    break

        with open(file_path, 'wb') as source:
            try:
                source.write(zip_file)
                # change analysis state to COMPLETED, just for testing
                REDIS_DATABASE.hset(analyze_id, 'state', AnalyzeStatus.COMPLETED.name)
            except Exception:
                LOGGER.error("Failed to store received ZIP.")

        client = docker.from_env()

        listOfContainers = client.containers.list(
            all=True, filters={'ancestor': 'codechecker', 'status': 'running'})

        if len(listOfContainers) == 0:
            LOGGER.error('There is no running CodeChecker container')
            return None

        LOGGER.info(listOfContainers)

        # random select container just for testing
        random_index = randint(0, len(listOfContainers) - 1)
        chosed_container = listOfContainers[random_index]

        REDIS_DATABASE.hset(analyze_id, 'container', chosed_container.id)

        LOGGER.info('Data stored in Redis for analysis %s: %s' % (analyze_id, str(REDIS_DATABASE.hgetall(analyze_id))))

        # send the id to the container to trigger analyze
        chosed_container.exec_run(['sh', '-c', 'python remote/analyze_handler.py', analyze_id])

    def getStatus(self, analyze_id):
        LOGGER.info('Get status of analysis %s', analyze_id)

        analysis_state = REDIS_DATABASE.hget(analyze_id, 'state')

        if analysis_state is None:
            return ('Not found.')

        return analysis_state

    def getResults(self, analyze_id):
        analysis_state = REDIS_DATABASE.hget(analyze_id, 'state')

        if analysis_state == AnalyzeStatus.COMPLETED.name:
            result_path = os.path.join(WORKSPACE, analyze_id, 'result.zip')

            with open(result_path, 'rb') as result:
                response = result.read()

            return response


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=".....")

    parser.add_argument('-w', '--workspace', type=str, dest='workspace',
                        default='workspace', help="...")

    args = parser.parse_args()

    WORKSPACE = args.workspace

    HANDLER = RemoteAnalyzeHandler()
    PROCESSOR = RemoteAnalyze.Processor(HANDLER)
    TRANSPORT = TSocket.TServerSocket(host='0.0.0.0', port=9090)
    T_FACTORY = TTransport.TBufferedTransportFactory()
    P_FACTORY = TBinaryProtocol.TBinaryProtocolFactory()

    SERVER = TServer.TSimpleServer(PROCESSOR, TRANSPORT, T_FACTORY, P_FACTORY)

    REDIS_DATABASE = redis.Redis(host='redis', port=6379, db=0, charset="utf-8", decode_responses=True)

    LOGGER.info('Starting the server...')
    SERVER.serve()
    LOGGER.info('Server stopped.')
