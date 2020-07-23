#!/usr/bin/env python3

"""
Server for handling remote analyze requests with CodeChecker.
"""

import argparse
import logging
import os
import uuid
from enum import Enum

import redis
from thrift.protocol import TBinaryProtocol
from thrift.server import TServer
from thrift.transport import TSocket, TTransport

from remote_analyze_api import RemoteAnalyze
from remote_analyze_api.ttypes import AnalysisNotFoundException
from remote_analyze_api.ttypes import AnalysisNotCompletedException

LOG = logging.getLogger("SERVER")
LOG.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
LOG.addHandler(ch)


class AnalyzeStatus(Enum):
    """
    Enums to represents states of the analysis.
    """

    ID_PROVIDED = "ID_PROVIDED"
    QUEUED = "QUEUED"
    ANALYZE_IN_PROGRESS = "ANALYZE_IN_PROGRESS"
    ANALYZE_COMPLETED = "ANALYZE_COMPLETED"


class RemoteAnalyzeHandler:
    def __init__(self):
        self.log = {}

    def getId(self):
        """
        Privides a uuid for the analysation.
        """

        LOG.info("Provide an id for the analysis")

        new_analyze_id = str(uuid.uuid4())

        REDIS_DATABASE.hset(new_analyze_id, "state",
                            AnalyzeStatus.ID_PROVIDED.name)

        REDIS_DATABASE.hset(new_analyze_id, "completed_parts", 0)

        new_analyze_dir = os.path.abspath(
            os.path.join(WORKSPACE, new_analyze_id))
        if not os.path.exists(new_analyze_dir):
            os.makedirs(new_analyze_dir)

        return new_analyze_id

    def checkUploadedFiles(self, fileHashes):
        """
        Returns which files are not available from the database.
        """

        LOG.info("Check missing files")

        missing_files = []
        for hash_value in fileHashes:
            if REDIS_DATABASE.get(hash_value) is None:
                missing_files.append(hash_value)

        return missing_files

    def analyze(self, analyzeId, zipFile):
        """
        Prepares the analysation step.
        """

        LOG.info("Store new part sources for analysis %s", analyzeId)

        file_name = "source"
        part_number = 1
        file_extension = ".zip"

        file_path = os.path.join(
            WORKSPACE, analyzeId, file_name + "_" +
            str(part_number) + file_extension
        )

        if os.path.isfile(file_path):
            while True:
                part_number += 1
                new_file_path = os.path.join(WORKSPACE,
                                             analyzeId,
                                             file_name + "_" +
                                             str(part_number) + file_extension,
                                             )
                if os.path.isfile(new_file_path):
                    continue
                else:
                    file_path = new_file_path
                    break

        with open(file_path, "wb") as source:
            try:
                source.write(zipFile)
            except Exception:
                LOG.error("Failed to store received ZIP.")

        REDIS_DATABASE.hset(analyzeId, "state", AnalyzeStatus.QUEUED.name)
        REDIS_DATABASE.hincrby(analyzeId, "parts", 1)
        REDIS_DATABASE.rpush(
            "ANALYSES_QUEUE", analyzeId + "_" + str(part_number))
        LOG.info("Part %s is %s for analyze %s.",
                 part_number,
                 AnalyzeStatus.QUEUED.name,
                 analyzeId)

    def getStatus(self, analyzeId):
        """
        Returns the status of the analysation.
        """
        LOG.info("Get status of analysis %s", analyzeId)

        analysis_state = REDIS_DATABASE.hget(analyzeId, "state")

        if analysis_state is not None:
            return analysis_state.decode('utf-8')
        else:
            LOG.info("Analysis with the provided id does not exist.")
            raise AnalysisNotFoundException("Analysis with the provided id does not exist.")


    def getResults(self, analyzeId):
        """
        Returns the results of the analysation.
        """
        LOG.info("Get results of analysis %s", analyzeId)

        analysis_state = REDIS_DATABASE.hget(analyzeId, "state")

        if analysis_state is not None:
            if analysis_state.decode('utf-8') == AnalyzeStatus.ANALYZE_COMPLETED.name:
                result_path = os.path.join(WORKSPACE, analyzeId, "output.zip")

                with open(result_path, "rb") as result:
                    response = result.read()

                return response
            else:
                LOG.info("Analysis with the provided id is not completed yet.")
                raise AnalysisNotCompletedException("Analysis with the provided id is not completed yet.")
        else:
            LOG.info("Analysis with the provided id does not exist.")
            raise AnalysisNotFoundException("Analysis with the provided id does not exist.")


if __name__ == "__main__":
    PARSER = argparse.ArgumentParser(description=".....")

    PARSER.add_argument(
        "-w", "--workspace", type=str, dest="workspace", default="workspace", help="..."
    )

    ARGUMENTS = PARSER.parse_args()

    WORKSPACE = ARGUMENTS.workspace

    HANDLER = RemoteAnalyzeHandler()
    PROCESSOR = RemoteAnalyze.Processor(HANDLER)
    TRANSPORT = TSocket.TServerSocket(host="0.0.0.0", port=9090)
    T_FACTORY = TTransport.TBufferedTransportFactory()
    P_FACTORY = TBinaryProtocol.TBinaryProtocolFactory()

    SERVER = TServer.TSimpleServer(PROCESSOR, TRANSPORT, T_FACTORY, P_FACTORY)

    REDIS_DATABASE = redis.Redis(host="redis", port=6379, db=0)

    LOG.info("Starting the server...")
    SERVER.serve()
    LOG.info("Server stopped.")
