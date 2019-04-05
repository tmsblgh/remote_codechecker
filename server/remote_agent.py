#!/usr/bin/env python3

"""
Server for handling remote analyze requests with CodeChecker.
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import uuid
import zipfile
from enum import Enum
from random import randint

import redis
from thrift.protocol import TBinaryProtocol
from thrift.server import TServer
from thrift.transport import TSocket, TTransport

from remote_analyze_api import RemoteAnalyze
from remote_analyze_api.ttypes import InvalidOperation

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
    Enums to represents state of analysis.
    """

    ID_PROVIDED = "ID_PROVIDED"
    QUEUED = "QUEUED"
    ANALYZE_IN_PROGRESS = "ANALYZE_IN_PROGRESS"
    ANALYZE_COMPLETED = "ANALYZE_COMPLETED"


class RemoteAnalyzeHandler:
    def __init__(self):
        self.log = {}

    def getId(self):
        LOG.info("Provide an id for the analysis")

        # 8 chars should be unique enough
        new_analyze_id = str(uuid.uuid4())[:8]

        REDIS_DATABASE.hset(new_analyze_id, "state",
                            AnalyzeStatus.ID_PROVIDED.name)

        REDIS_DATABASE.hset(new_analyze_id, "completed_parts", 0)

        new_analyze_dir = os.path.abspath(
            os.path.join(WORKSPACE, new_analyze_id))
        if not os.path.exists(new_analyze_dir):
            os.makedirs(new_analyze_dir)

        return new_analyze_id

    def check_uploaded_files(self, file_hashes):
        LOG.info("Check missing files")

        missing_files = []
        for hash in file_hashes:
            if REDIS_DATABASE.get(hash) is None:
                missing_files.append(hash)

        return missing_files

    def analyze(self, analyze_id, zip_file):
        LOG.info("Store new part sources for analysis %s", analyze_id)

        file_name = "source"
        part_number = 1
        file_extension = ".zip"

        file_path = os.path.join(
            WORKSPACE, analyze_id, file_name + "_" +
            str(part_number) + file_extension
        )

        if os.path.isfile(file_path):
            while True:
                part_number += 1
                new_file_path = os.path.join(WORKSPACE,
                                             analyze_id,
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
                source.write(zip_file)
            except Exception:
                LOG.error("Failed to store received ZIP.")

        REDIS_DATABASE.hset(analyze_id, "state", AnalyzeStatus.QUEUED.name)
        REDIS_DATABASE.hincrby(analyze_id, "parts", 1)
        REDIS_DATABASE.rpush(
            "ANALYSES_QUEUE", analyze_id + "-" + str(part_number))
        LOG.info("Part %s is %s for analyze %s.",
                 part_number,
                 AnalyzeStatus.QUEUED.name,
                 analyze_id)

    def getStatus(self, analyze_id):
        LOG.info("Get status of analysis %s", analyze_id)

        analysis_state = REDIS_DATABASE.hget(analyze_id, "state").decode('utf-8')

        if analysis_state is None:
            return "Not found."

        return analysis_state

    def getResults(self, analyze_id):
        analysis_state = REDIS_DATABASE.hget(analyze_id, "state").decode('utf-8')

        if analysis_state == AnalyzeStatus.ANALYZE_COMPLETED.name:
            result_path = os.path.join(WORKSPACE, analyze_id, "output.zip")

            with open(result_path, "rb") as result:
                response = result.read()

            return response


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=".....")

    parser.add_argument(
        "-w", "--workspace", type=str, dest="workspace", default="workspace", help="..."
    )

    args = parser.parse_args()

    WORKSPACE = args.workspace

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
