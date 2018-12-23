#!/usr/bin/env python3

"""
Server for handling remote analyze requests with CodeChecker.
"""

import os
import sys
import uuid
import subprocess
import logging
import zipfile
import docker
#just for testing
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


class Analysis(object):
    def __init__(self, state, container_id=None):
        self.state = state
        self.container_id = container_id


class RemoteAnalyzeHandler:
    def __init__(self):
        self.log = {}

    def getId(self):
        LOGGER.info('Provide an id for the analysis')

        newAnalysisId = str(uuid.uuid4())
        newAnalysisState = 'ID PROVIDED'

        newAnalysis = Analysis(newAnalysisId, newAnalysisState)

        analyses[newAnalysisId] = newAnalysis

        os.mkdir(os.path.join(WORKSPACE, newAnalysisId))

        return newAnalysisId

    def analyze(self, analysisId, zip_file):
        LOGGER.info('Store sources for analysis %s' , analysisId)

        source_path = os.path.join(analysisId, 'source.zip')

        with open(os.path.join(WORKSPACE, source_path), 'wb') as source:
            try:
                source.write(zip_file)
                # change analysis state to COMPLETED, just for testing
                analyses[analysisId].state = 'COMPLETED'
            except Exception:
                LOGGER.error("Failed to store received ZIP.")

        client = docker.from_env()

        listOfContainers = client.containers.list(all=True, filters={'ancestor':'remote_codechecker', 'status':'running'})

        if len(listOfContainers) == 0:
            LOGGER.error('There is no running CodeChecker container')
            return None

        LOGGER.info(listOfContainers)

        # random select container just for testing
        randomIndex = randint(0, len(listOfContainers) - 1)
        chosedContainer = listOfContainers[randomIndex]

        # send the id to the container to trigger analyze
        chosedContainer.exec_run(['sh', '-c', 'python test.py'])

    def getStatus(self, analysisId):
        LOGGER.info('Get status of analysis %s', analysisId)

        if analyses[analysisId] is None:
            return ('Not found.')

        return analyses[analysisId].state

    def getResults(self, analysisId):
        for analysis in analyses:
            if analyses[analysisId].state == 'COMPLETED':
                result_path = os.path.join(WORKSPACE, analysisId, 'result.zip')

                with open(result_path, 'rb') as result:
                    response = result.read()

                return response


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=".....")

    log_args = parser.add_argument_group("log arguments", """.....""")
    log_args = log_args.add_mutually_exclusive_group(required=True)

    log_args.add_argument('w', '--workspace', type=str,
                          dest='workspace', help="...")

    args = parser.parse_args()

    WORKSPACE = args.workspace

    HANDLER = RemoteAnalyzeHandler()
    PROCESSOR = RemoteAnalyze.Processor(HANDLER)
    TRANSPORT = TSocket.TServerSocket(host='0.0.0.0', port=9090)
    T_FACTORY = TTransport.TBufferedTransportFactory()
    P_FACTORY = TBinaryProtocol.TBinaryProtocolFactory()

    SERVER = TServer.TSimpleServer(PROCESSOR, TRANSPORT, T_FACTORY, P_FACTORY)

    analyses = dict()

    LOGGER.info('Starting the server...')
    SERVER.serve()
    LOGGER.info('Server stopped.')
