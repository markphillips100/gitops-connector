# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from flask import Flask, request
import logging
import kopf
from timeloop import Timeloop
from datetime import timedelta
import atexit
import time
from threading import Thread
from configuration.gitops_config_operator import GitOpsConfigOperator

# Time in seconds between background PR cleanup jobs
PR_CLEANUP_INTERVAL = 1 * 30
DISABLE_POLLING_PR_TASK = False

logging.basicConfig(level=logging.DEBUG)

application = Flask(__name__)

gitops_config_operator = GitOpsConfigOperator()

@kopf.on.create('gitopsconfigs')  # Adjust the CRD name if necessary
def on_create(spec, name, **kwargs):
    gitops_config_operator.create_fn(spec, name, **kwargs)

@kopf.on.update('gitopsconfigs')  # Adjust the CRD name if necessary
def on_update(spec, name, **kwargs):
    gitops_config_operator.update_fn(spec, name, **kwargs)

@kopf.on.delete('gitopsconfigs')  # Adjust the CRD name if necessary
def on_delete(name, **kwargs):
    gitops_config_operator.delete_fn(name, **kwargs)


@application.route("/gitopsphase", methods=['POST'])
def gitopsphase():
    # Use per process timer to stash the time we got the request
    req_time = time.monotonic_ns()

    raw_data = request.data.decode('utf-8')  # Decode byte data to string
    logging.debug(f'Raw request data: {raw_data}')

    # Ensure the request is JSON
    if not request.is_json:
        return "Invalid content type. Expected application/json.", 400

    try:
        payload = request.get_json()
    except Exception as e:
        logging.error(f'Failed to parse JSON. Error: {e}')
        return "Malformed JSON data", 400

    logging.debug(f'GitOps phase: {payload}')

    gitops_connector_config_name = payload['gitops_connector_config_name']

    gitops_connector = gitops_config_operator.get_gitops_connector(gitops_connector_config_name)
    if gitops_connector != None:
        gitops_connector.process_gitops_phase(payload, req_time)

    return f'GitOps phase: {payload}', 200


# Periodic PR cleanup task
# cleanup_task = Timeloop()


# @cleanup_task.job(interval=timedelta(seconds=PR_CLEANUP_INTERVAL))
# def pr_polling_thread_worker():
#     logging.info("Starting periodic PR cleanup")
#     gitops_connector.notify_abandoned_pr_tasks()
#     logging.info(f'Finished PR cleanup, sleeping for {PR_CLEANUP_INTERVAL} seconds...')


# # Git status queue drain task
# def init_commit_status_thread():
#     logging.info("Starting commit status thread")
#     status_thread = Thread(target=gitops_connector.drain_commit_status_queue)
#     status_thread.start()

# Kopf operator task
def run_kopf_operator():
    logging.info("Starting Kopf operator thread")
    gitops_config_operator.run()  # Start the operator

def interrupt():
    if not DISABLE_POLLING_PR_TASK:
        gitops_config_operator.stop_all()
        # cleanup_task.stop()


if not DISABLE_POLLING_PR_TASK:
    # cleanup_task.start()
    # init_commit_status_thread()
    atexit.register(interrupt)

kopf_thread = Thread(target=run_kopf_operator)
kopf_thread.start()

if __name__ == "__main__":
    application.run(host='0.0.0.0')
