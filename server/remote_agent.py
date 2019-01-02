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

        newAnalysisId = str(uuid.uuid4())

        REDIS_DATABASE.hset(newAnalysisId, 'state', AnalyzeStatus.ID_PROVIDED.name)

        os.mkdir(os.path.join(WORKSPACE, newAnalysisId))

        return newAnalysisId

    def analyze(self, analysisId, zip_file):
        LOGGER.info('Store sources for analysis %s', analysisId)

        source_path = os.path.join(analysisId, 'source.zip')

        with open(os.path.join(WORKSPACE, source_path), 'wb') as source:
            try:
                source.write(zip_file)
                # change analysis state to COMPLETED, just for testing
                REDIS_DATABASE.hset(analysisId, 'state', AnalyzeStatus.COMPLETED.name)
            except Exception:
                LOGGER.error("Failed to store received ZIP.")

        client = docker.from_env()

        listOfContainers = client.containers.list(
            all=True, filters={'ancestor': 'remote_codechecker', 'status': 'running'})

        if len(listOfContainers) == 0:
            LOGGER.error('There is no running CodeChecker container')
            return None

        LOGGER.info(listOfContainers)

        # random select container just for testing
        randomIndex = randint(0, len(listOfContainers) - 1)
        chosedContainer = listOfContainers[randomIndex]

        REDIS_DATABASE.hset(analysisId, 'container', chosedContainer.id)

        LOGGER.info('Data stored in Redis for analysis %s: %s' % (analysisId, str(REDIS_DATABASE.hgetall(analysisId))))

        # send the id to the container to trigger analyze
        chosedContainer.exec_run(['sh', '-c', 'touch apple.txt'])

    def getStatus(self, analysisId):
        LOGGER.info('Get status of analysis %s', analysisId)

        analysisState = REDIS_DATABASE.hget(analysisId, 'state')

        if analysisState is None:
            return ('Not found.')

        return analysisState

    def getResults(self, analysisId):
        analysisState = REDIS_DATABASE.hget(analysisId, 'state')

        if analysisState == AnalyzeStatus.COMPLETED.name:
            result_path = os.path.join(WORKSPACE, analysisId, 'result.zip')

            with open(result_path, 'rb') as result:
                response = result.read()

            return response


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=".....")

    parser.add_argument('-w', '--workspace', type=str,
                          dest='workspace', help="...")

    args = parser.parse_args()

    WORKSPACE = args.workspace

    HANDLER = RemoteAnalyzeHandler()
    PROCESSOR = RemoteAnalyze.Processor(HANDLER)
    TRANSPORT = TSocket.TServerSocket(host='0.0.0.0', port=9090)
    T_FACTORY = TTransport.TBufferedTransportFactory()
    P_FACTORY = TBinaryProtocol.TBinaryProtocolFactory()

    SERVER = TServer.TSimpleServer(PROCESSOR, TRANSPORT, T_FACTORY, P_FACTORY)

    REDIS_DATABASE = redis.Redis(host='localhost', port=6379, db=0, charset="utf-8", decode_responses=True)

    LOGGER.info('Starting the server...')
    SERVER.serve()
    LOGGER.info('Server stopped.')
