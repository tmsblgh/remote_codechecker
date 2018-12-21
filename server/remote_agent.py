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
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from thrift.server import TServer

sys.path.append('../gen-py')
from remote_analyze_api import RemoteAnalyze

LOGGER = logging.getLogger('CLIENT')
LOGGER.setLevel(logging.INFO)
fh.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.ERROR)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
fh.setFormatter(formatter)
LOGGER.addHandler(ch)
LOGGER.addHandler(fh)


class Analysis(object):
    def __init__(self, id, state, container_id=None):
        self.id = id
        self.state = state
        self.container_id = container_id


class RemoteAnalyzeHandler:
    def __init__(self):
        self.log = {}

    def getId(self):
        logger.info('Provide an id for the analysis')

        newAnalysisId = str(uuid.uuid4())
        newAnalysisState = 'ID PROVIDED'

        newAnalysis = Analysis(newAnalysisId, newAnalysisState)

        analyses.append(newAnalysis)

        os.mkdir(newAnalysisId)

        return newAnalysisId

    def analyze(self, analysisId, zip_file):
        logger.info('Store sources for analysis %s' , analysisId)

        source_path = os.path.join(analysisId, 'source.zip')

        with open(source_path, 'wb') as source:
            try:
                source.write(zip_file)
                # change analysis state to COMPLETED, just for testing
                for analysis in analyses:
                    if analysis.id == analysisId:
                        analysis.state = 'COMPLETED'
            except Exception:
                logger.error("Failed to store received ZIP.")

    def getStatus(self, analysisId):
        logger.info('Get status of analysis %s', analysisId)

        dataOfAnalysis = None

        for analysis in analyses:
            if analysis.id == analysisId:
                dataOfAnalysis = analysis
                break

        if dataOfAnalysis is None:
            return ('Not found.')

        return (dataOfAnalysis.state)

    def getResults(self, analysisId):
        for analysis in analyses:
            if analysis.id == analysisId:
                if analysis.state == 'COMPLETED':
                    result_path = os.path.join(analysis.id, 'result.zip')

                    with open(result_path, 'rb') as result:
                        response = result.read()

                    return response


if __name__ == '__main__':
    HANDLER = RemoteAnalyzeHandler()
    PROCESSOR = RemoteAnalyze.Processor(HANDLER)
    TRANSPORT = TSocket.TServerSocket(host='0.0.0.0', port=9090)
    T_FACTORY = TTransport.TBufferedTransportFactory()
    P_FACTORY = TBinaryProtocol.TBinaryProtocolFactory()

    SERVER = TServer.TSimpleServer(PROCESSOR, TRANSPORT, T_FACTORY, P_FACTORY)

    LOGGER.info('Starting the server...')
    SERVER.serve()
    LOGGER.info('Server stopped.')
