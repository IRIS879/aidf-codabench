import asyncio
import csv
import datetime as dt
import glob
import hashlib
import json
import math
import os
import shutil
import signal
import socket
import tempfile
import time
import uuid
from shutil import make_archive
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import urlretrieve
from zipfile import ZipFile, BadZipFile
import docker
from rich.progress import Progress
from rich.pretty import pprint
import requests

import websockets
import yaml
from billiard.exceptions import SoftTimeLimitExceeded
from celery import Celery, shared_task, utils
from kombu import Queue, Exchange
from urllib3 import Retry

# This is only needed for the pytests to pass
import sys

sys.path.append("/app/src/settings/")

from celery import signals
import logging

logger = logging.getLogger(__name__)
from logs_loguru import configure_logging, colorize_run_args
import json
try:
    import pandas as pd
except Exception:
    pd = None


# -----------------------------------------------
# Logging
# -----------------------------------------------
configure_logging(
    os.environ.get("LOG_LEVEL", "INFO"), os.environ.get("SERIALIZED", "false")
)

# -----------------------------------------------
# Initialize Docker or Podman depending on .env
# -----------------------------------------------
if os.environ.get("USE_GPU", "false").lower() == "true":
    logger.info(
        "Using "
        + os.environ.get("CONTAINER_ENGINE_EXECUTABLE", "docker").upper()
        + "with GPU capabilites : "
        + os.environ.get("GPU_DEVICE", "nvidia.com/gpu=all")
    )
else:
    logger.info(
        "Using "
        + os.environ.get("CONTAINER_ENGINE_EXECUTABLE", "docker").upper()
        + " without GPU capabilities"
    )

if os.environ.get("CONTAINER_ENGINE_EXECUTABLE", "docker").lower() == "docker":
    client = docker.APIClient(
        base_url=os.environ.get("CONTAINER_SOCKET", "unix:///var/run/docker.sock"),
        version="auto",
    )
elif os.environ.get("CONTAINER_ENGINE_EXECUTABLE").lower() == "podman":
    client = docker.APIClient(
        base_url=os.environ.get(
            "CONTAINER_SOCKET", "unix:///run/user/1000/podman/podman.sock"
        ),
        version="auto",
    )


LEGACY_DEFAULT_RUNTIME_IMAGE = "codalab/codalab-legacy:py37"
# Prefer generic override name, keep LEGACY_PY37_RUNTIME_IMAGE for backward compatibility.
RUNTIME_IMAGE_OVERRIDE = (
    os.environ.get("SUBMISSION_RUNTIME_IMAGE_OVERRIDE", "").strip()
    or os.environ.get("LEGACY_PY37_RUNTIME_IMAGE", "").strip()
)


def resolve_submission_runtime_image(requested_image):
    """
    Allow local deployments to transparently override the legacy py37 runtime image
    with a patched local image while leaving competition metadata unchanged.
    """
    if requested_image == LEGACY_DEFAULT_RUNTIME_IMAGE and RUNTIME_IMAGE_OVERRIDE:
        logger.info(
            "Overriding submission runtime image from %s to %s",
            requested_image,
            RUNTIME_IMAGE_OVERRIDE,
        )
        return RUNTIME_IMAGE_OVERRIDE
    return requested_image


# -----------------------------------------------
# Show Progress bar on downloading images
# -----------------------------------------------
tasks = {}


def show_progress(line, progress):
    try:
        if "Status: Image is up to date" in line["status"]:
            logger.info(line["status"])

        completed = False
        if line["status"] == "Download complete":
            description = (
                f"[blue][Download complete, waiting for extraction  {line['id']}]"
            )
            completed = True
        elif line["status"] == "Downloading":
            description = f"[bold][Downloading {line['id']}]"
        elif line["status"] == "Pull complete":
            description = f"[green][Extraction complete  {line['id']}]"
            completed = True
        elif line["status"] == "Extracting":
            description = f"[blue][Extracting  {line['id']}]"

        else:
            # skip other statuses, but show extraction progress
            return

        task_id = line["id"]
        if task_id not in tasks.keys():
            if completed:
                # some layers are really small that they download immediately without showing
                # anything as Downloading in the stream.
                # For that case, show a completed progress bar
                tasks[task_id] = progress.add_task(
                    description, total=100, completed=100
                )
            else:
                tasks[task_id] = progress.add_task(
                    description, total=line["progressDetail"]["total"]
                )
        else:
            if completed:
                # due to the stream, the Download complete output can happen before the Downloading
                # bar outputs the 100%. So when we detect that the download is in fact complete,
                # update the progress bar to show 100%
                progress.update(
                    tasks[task_id], description=description, total=100, completed=100
                )
            else:
                progress.update(
                    tasks[task_id],
                    completed=line["progressDetail"]["current"],
                    total=line["progressDetail"]["total"],
                )
    except Exception as e:
        logger.error("There was an error showing the progress bar")
        logger.error(e)


# -----------------------------------------------
# Celery + Rabbit MQ
# -----------------------------------------------
@signals.setup_logging.connect
def setup_celery_logging(**kwargs):
    pass


# Init celery + rabbit queue definitions
app = Celery()
app.config_from_object("celery_config")  # grabs celery_config.py
QUEUE_STATIC = os.environ.get("QUEUE_STATIC", "compute-worker-static")
QUEUE_ROLLING = os.environ.get("QUEUE_ROLLING", "compute-worker-rolling")
app.conf.task_queues = [
    # Mostly defining queue here so we can set x-max-priority
    Queue(
        QUEUE_STATIC,
        Exchange(QUEUE_STATIC),
        routing_key=QUEUE_STATIC,
        queue_arguments={"x-max-priority": 10},
    ),
    Queue(
        QUEUE_ROLLING,
        Exchange(QUEUE_ROLLING),
        routing_key=QUEUE_ROLLING,
        queue_arguments={"x-max-priority": 10},
    ),
]
# -----------------------------------------------
# Directories
# -----------------------------------------------
# Setup base directories used by all submissions
# note: we need to pass this directory to docker/podman so it knows where to store things!
HOST_DIRECTORY = os.environ.get("HOST_DIRECTORY", "/tmp/codabench/")
BASE_DIR = "/codabench/"  # base directory inside the container
CACHE_DIR = os.path.join(BASE_DIR, "cache")
MAX_CACHE_DIR_SIZE_GB = float(os.environ.get("MAX_CACHE_DIR_SIZE_GB", 10))


# -----------------------------------------------
# Submission status
# -----------------------------------------------
# Status options for submissions
STATUS_NONE = "None"
STATUS_SUBMITTING = "Submitting"
STATUS_SUBMITTED = "Submitted"
STATUS_PREPARING = "Preparing"
STATUS_RUNNING = "Running"
STATUS_SCORING = "Scoring"
STATUS_FINISHED = "Finished"
STATUS_FAILED = "Failed"
AVAILABLE_STATUSES = (
    STATUS_NONE,
    STATUS_SUBMITTING,
    STATUS_SUBMITTED,
    STATUS_PREPARING,
    STATUS_RUNNING,
    STATUS_SCORING,
    STATUS_FINISHED,
    STATUS_FAILED,
)


# -----------------------------------------------
# Exceptions
# -----------------------------------------------
class SubmissionException(Exception):
    pass


class DockerImagePullException(Exception):
    pass


class ExecutionTimeLimitExceeded(Exception):
    pass


# -----------------------------------------------------------------------------
# The main compute worker entrypoint, this is how a job is ran at the highest
# level.
# -----------------------------------------------------------------------------
@shared_task(name="compute_worker_run")
def run_wrapper(run_args):
    job_id = run_args.get("id")
    competition_id = run_args.get("competition_id")
    training_mode = run_args.get("training_mode", "static")
    logger.info(
        "Worker accepted job_id=%s competition_id=%s training_mode=%s",
        job_id,
        competition_id,
        training_mode,
    )
    logger.info(f"Received run arguments: \n {colorize_run_args(json.dumps(run_args))}")
    run = Run(run_args)

    try:
        run.prepare()
        run.start()
        if run.is_scoring:
            run.push_scores()
        run.push_output()
    except DockerImagePullException as e:
        run._update_status(STATUS_FAILED, str(e))
    except SubmissionException as e:
        run._update_status(STATUS_FAILED, str(e))
    except SoftTimeLimitExceeded:
        run._update_status(STATUS_FAILED, "Soft time limit exceeded!")
    finally:
        run.clean_up()


def replace_legacy_metadata_command(
    command, kind, is_scoring, ingestion_only_during_scoring=False
):
    vars_to_replace = [
        ("$input", "/app/input_data" if kind == "ingestion" else "/app/input"),
        ("$output", "/app/output"),
        ("$program", "/app/program"),
        ("$ingestion_program", "/app/program"),
        ("$hidden", "/app/input/ref"),
        ("$shared", "/app/shared"),
        ("$submission_program", "/app/ingested_program"),
        # for v1.8 compatibility
        ("$tmp", "/app/output"),
        ("$predictions", "/app/input/res" if is_scoring else "/app/output"),
    ]
    for var_string, var_replacement in vars_to_replace:
        command = command.replace(var_string, var_replacement)
    return command


def md5(filename):
    """Given some file return its md5, works well on large files"""
    hash_md5 = hashlib.md5()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def get_folder_size_in_gb(folder):
    if not os.path.exists(folder):
        return 0
    total_size = os.path.getsize(folder)
    for item in os.listdir(folder):
        path = os.path.join(folder, item)
        if os.path.isfile(path):
            total_size += os.path.getsize(path)
        elif os.path.isdir(path):
            total_size += get_folder_size_in_gb(path)
    return total_size / 1000 / 1000 / 1000  # GB: decimal system (1000^3)


def delete_files_in_folder(folder):
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        if os.path.isfile(file_path) or os.path.islink(file_path):
            os.unlink(file_path)
        elif os.path.isdir(file_path):
            shutil.rmtree(file_path)


def is_valid_zip(zip_path):
    # Check zip integrity
    try:
        with ZipFile(zip_path, "r") as zf:
            return zf.testzip() is None
    except BadZipFile:
        return False


def alarm_handler(signum, frame):
    raise ExecutionTimeLimitExceeded


# -----------------------------------------------
# Class Run
# Responsible for running a submission inside a docker/podman container
# -----------------------------------------------
class Run:
    """A "Run" in Codabench is composed of some program, some data to work with, and some signed URLs to upload results
    to. There is also a secret key to do special commands for just this submission.

    Some example API's you can hit using this secret key are:

        push_scores

        (maybe later:
            get previous submission
            get sibling submission
            get top submission
            get some different dataset
            post results to twitter)
    """

    def __init__(self, run_args):
        # Directories for the run
        self.watch = True
        self.completed_program_counter = 0
        self.root_dir = tempfile.mkdtemp(dir=BASE_DIR)
        self.bundle_dir = os.path.join(self.root_dir, "bundles")
        self.input_dir = os.path.join(self.root_dir, "input")
        self.output_dir = os.path.join(self.root_dir, "output")
        self.data_dir = os.path.join(
            HOST_DIRECTORY, "data"
        )  # absolute path to data in the host
        self.logs = {}

        # Details for submission
        self.is_scoring = run_args["is_scoring"]
        self.user_pk = run_args["user_pk"]
        self.submission_id = run_args["id"]
        self.submissions_api_url = run_args["submissions_api_url"]
        self.requested_container_image = run_args["docker_image"]
        self.container_image = resolve_submission_runtime_image(
            self.requested_container_image
        )
        self.secret = run_args["secret"]
        self.prediction_result = run_args["prediction_result"]
        self.scoring_result = run_args.get("scoring_result")
        self.execution_time_limit = run_args["execution_time_limit"]
        # stdout and stderr
        self.stdout, self.stderr, self.ingestion_stdout, self.ingestion_stderr = (
            self._get_stdout_stderr_file_names(run_args)
        )
        self.ingestion_container_name = uuid.uuid4()
        self.program_container_name = uuid.uuid4()
        self.program_data = run_args.get("program_data")
        self.ingestion_program_data = run_args.get("ingestion_program")
        self.input_data = run_args.get("input_data")
        self.reference_data = run_args.get("reference_data")
        self.submission_data = run_args.get("submission_data")
        self.ingestion_only_during_scoring = run_args.get(
            "ingestion_only_during_scoring"
        )
        self.detailed_results_url = run_args.get("detailed_results_url")
        self.competition_id = run_args.get("competition_id")
        self.training_mode = run_args.get("training_mode", "static")
        self.rolling_enabled = self.training_mode == "rolling"
        self.rolling_start_year = run_args.get(
            "rolling_start_year", run_args.get("start_year", 2018)
        )
        self.rolling_end_year = run_args.get(
            "rolling_end_year", run_args.get("end_year", 2019)
        )
        self.rolling_window_size = int(
            run_args.get("window_size", run_args.get("rolling_window_size", 2))
        )
        self.rolling_period_col = run_args.get("period_col", run_args.get("year_col", "yyyy")) or "yyyy"
        self.rolling_start_period = run_args.get("rolling_start_period")
        self.rolling_end_period = run_args.get("rolling_end_period")
        static_split_column = run_args.get("static_split_column")
        static_split_value = run_args.get("static_split_value")
        self.static_split_column = str(static_split_column).strip() if static_split_column is not None else None
        self.static_split_value = str(static_split_value).strip() if static_split_value is not None else None
        if self.static_split_column == "":
            self.static_split_column = None
        if self.static_split_value == "":
            self.static_split_value = None
        self.period_sort_strategy = None
        self.period_key_to_label = {}
        self.period_keys_ordered = []

        # During prediction program will be the submission program, during scoring it will be the
        # scoring program
        self.program_exit_code = None
        self.ingestion_program_exit_code = None
        self.combined_scores = None

        self.program_elapsed_time = None
        self.ingestion_elapsed_time = None

        # Socket connection to stream output of submission
        submission_api_url_parsed = urlparse(self.submissions_api_url)
        websocket_host = submission_api_url_parsed.netloc
        websocket_scheme = "ws" if submission_api_url_parsed.scheme == "http" else "wss"
        self.websocket_url = f"{websocket_scheme}://{websocket_host}/submission_input/{self.user_pk}/{self.submission_id}/{self.secret}/"

        # Nice requests adapter with generous retries/etc.
        self.requests_session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            max_retries=Retry(
                total=3,
                backoff_factor=1,
            )
        )
        self.requests_session.mount("http://", adapter)
        self.requests_session.mount("https://", adapter)

    async def watch_detailed_results(self):
        """Watches files alongside scoring + program containers, currently only used
        for detailed_results.html"""
        if not self.detailed_results_url:
            return
        file_path = self.get_detailed_results_file_path()
        last_modified_time = None
        start = time.time()
        expiration_seconds = 60

        while self.watch and self.completed_program_counter < 2:
            if file_path:
                new_time = os.path.getmtime(file_path)
                if new_time != last_modified_time:
                    last_modified_time = new_time
                    await self.send_detailed_results(file_path)
            else:
                logger.info(time.time() - start)
                if time.time() - start > expiration_seconds:
                    timeout_error_message = (
                        "WARNING: Detailed results not written before the execution."
                    )
                    logger.warning(timeout_error_message)
            await asyncio.sleep(5)
            file_path = self.get_detailed_results_file_path()
        else:
            # make sure we always send the final version of the file
            if file_path:
                await self.send_detailed_results(file_path)

    def get_detailed_results_file_path(self):
        default_detailed_results_path = os.path.join(
            self.output_dir, "detailed_results.html"
        )
        if os.path.exists(default_detailed_results_path):
            return default_detailed_results_path
        else:
            # v1.5 compatibility - get the first html file if detailed_results.html doesn't exists
            html_files = glob.glob(os.path.join(self.output_dir, "*.html"))
            if html_files:
                return html_files[0]

    async def send_detailed_results(self, file_path):
        logger.info(
            f"Updating detailed results {file_path} - {self.detailed_results_url}"
        )
        self._put_file(
            self.detailed_results_url, file=file_path, content_type="text/html"
        )
        websocket_url = f"{self.websocket_url}?kind=detailed_results"
        logger.info(f"Connecting to {websocket_url} for detailed results")
        # Wrap this with a Try ... Except otherwise a failure here will make the submission get stuck on Running
        try:
            websocket = await asyncio.wait_for(
                websockets.connect(websocket_url), timeout=30.0
            )
            await websocket.send(
                json.dumps(
                    {
                        "kind": "detailed_result_update",
                    }
                )
            )
        except Exception as e:
            logger.error("This error might result in a Execution Time Exceeded error: " + str(e))
            if os.environ.get("LOG_LEVEL", "info").lower() == "debug":
                logger.exception(e)

    def _get_stdout_stderr_file_names(self, run_args):
        # run_args should be the run_args argument passed to __init__ from the run_wrapper.
        if not self.is_scoring:
            DETAILED_OUTPUT_NAMES = [
                "prediction_stdout",
                "prediction_stderr",
                "prediction_ingestion_stdout",
                "prediction_ingestion_stderr",
            ]
        else:
            DETAILED_OUTPUT_NAMES = [
                "scoring_stdout",
                "scoring_stderr",
                "scoring_ingestion_stdout",
                "scoring_ingestion_stderr",
            ]
        return [run_args[name] for name in DETAILED_OUTPUT_NAMES]

    def _update_submission(self, data):
        url = f"{self.submissions_api_url}/submissions/{self.submission_id}/"
        data["secret"] = self.secret

        logger.info(f"Updating submission @ {url} with data = {data}")

        resp = self.requests_session.patch(url, data, timeout=150)
        if resp.status_code == 200:
            logger.info("Submission updated successfully!")
        else:
            logger.error(
                f"Submission patch failed with status = {resp.status_code}, and response = \n{resp.content}"
            )
            raise SubmissionException("Failure updating submission data.")

    def _update_status(self, status, extra_information=None):
        if status not in AVAILABLE_STATUSES:
            raise SubmissionException(
                f"Status '{status}' is not in available statuses: {AVAILABLE_STATUSES}"
            )

        data = {
            "status": status,
            "status_details": extra_information,
        }

        # TODO: figure out if we should pull this task code later(submission.task should always be set)
        # When we start
        # if status == STATUS_SCORING:
        #     data.update({
        #         "task_pk": self.task_pk,
        #     })
        self._update_submission(data)

    def _get_container_image(self, image_name):
        try:
            local_image = client.inspect_image(image_name)
            logger.info(
                "Using existing local image for %s: %s",
                image_name,
                local_image.get("Id", "unknown"),
            )
            return
        except docker.errors.NotFound:
            logger.info("Local image not found for %s, attempting pull", image_name)
        except docker.errors.APIError as image_lookup_error:
            logger.warning(
                "Failed checking local image %s: %s. Falling back to pull.",
                image_name,
                image_lookup_error,
            )

        logger.info("Running pull for image: {}".format(image_name))
        retries, max_retries = (0, 3)
        while retries < max_retries:
            try:
                with Progress() as progress:
                    resp = client.pull(image_name, stream=True, decode=True)
                    for line in resp:
                        show_progress(line, progress)
                    break  # Break if the loop is successful to exit "with Progress() as progress"

            except (docker.errors.APIError, Exception) as pull_error:
                retries += 1
                if retries >= max_retries:
                    logger.error(
                        "There was a problem pulling the image : " + str(pull_error)
                    )
                    # Prepare data to be sent to submissions api
                    docker_pull_fail_data = {
                        "type": "Docker_Image_Pull_Fail",
                        "error_message": pull_error,
                        "is_scoring": self.is_scoring,
                    }
                    # Send data to be written to ingestion logs
                    self._update_submission(docker_pull_fail_data)
                    # Send error through web socket to the frontend
                    asyncio.run(self._send_data_through_socket(str(pull_error)))
                    raise DockerImagePullException(
                        f"Pull for {image_name} failed! Check the logs for more information"
                    )
                else:
                    logger.warning("Failed. Retrying in 5 seconds...")
                    time.sleep(5)  # Wait 5 seconds before retrying

    async def _send_data_through_socket(self, error_message):
        """
        This function gets an error messages and sends it through a web socket. This function is used for sending
        - Docker image pull failure logs
        - Execution time limit exceeded logs
        """
        # Create a unique websocket URL for error messages
        websocket_url = f"{self.websocket_url}?kind=error_logs"
        logger.info(f"Connecting to {websocket_url} to send error message")

        logger.info(f"Connecting to {websocket_url} to send docker image pull error")

        # connect to web socket
        websocket = await asyncio.wait_for(
            websockets.connect(websocket_url), timeout=10.0
        )

        # define websocket errors
        websocket_errors = (
            socket.gaierror,
            websockets.WebSocketException,
            websockets.ConnectionClosedError,
            ConnectionRefusedError,
        )

        try:
            # send message
            await websocket.send(
                json.dumps({"kind": "stderr", "message": error_message})
            )

        except websocket_errors:
            # handle websocket errors
            logger.error("Error sending failed through websocket")
            try:
                await websocket.close()
            except Exception as e:
                logger.error(e)
        else:
            # no error in websocket message sending
            logger.info("Error sent successfully through websocket")

        logger.info(f"Disconnecting from websocket {websocket_url}")

        # close websocket
        await websocket.close()

    def _get_bundle(self, url, destination, cache=True):
        """Downloads zip from url and unzips into destination. If cache=True then url is hashed and checked
        against existence in CACHE_DIR/<hashed_url> and only downloaded if needed. Cache size is checked
        during the prepare step and cleared if it's over MAX_CACHE_DIR_SIZE_GB.

        :returns zip file path"""
        logger.info(f"Getting bundle {url} to unpack @ {destination}")
        download_needed = True

        # Try to find the bundle in the cache of the worker
        if cache:
            # Hash url and download it if it doesn't exist
            url_without_params = url.split("?")[0]
            url_hash = hashlib.sha256(url_without_params.encode("utf8")).hexdigest()
            bundle_file = os.path.join(CACHE_DIR, url_hash)
            download_needed = not os.path.exists(bundle_file)
        else:
            if not os.path.exists(self.bundle_dir):
                os.mkdir(self.bundle_dir)
            bundle_file = tempfile.NamedTemporaryFile(
                dir=self.bundle_dir, delete=False
            ).name

        # Fetch and extract
        retries, max_retries = (0, 10)
        while retries < max_retries:
            if download_needed:
                try:
                    # Download the bundle
                    urlretrieve(url, bundle_file)
                except HTTPError:
                    raise SubmissionException(
                        f"Problem fetching {url} to put in {destination}"
                    )
            try:
                # Extract the contents to destination directory
                with ZipFile(bundle_file, "r") as z:
                    z.extractall(os.path.join(self.root_dir, destination))
                self._normalize_single_root_dir(os.path.join(self.root_dir, destination))
                break  # Break if the loop is successful
            except BadZipFile:
                retries += 1
                if retries >= max_retries:
                    raise  # Re-raise the last caught BadZipFile exception
                else:
                    logger.warning("Failed. Retrying in 60 seconds...")
                    time.sleep(60)  # Wait 60 seconds before retrying
        # Return the zip file path for other uses, e.g. for creating a MD5 hash to identify it
        return bundle_file

    def _is_ignored_bundle_entry(self, entry):
        return (
            entry == "__MACOSX"
            or entry == ".DS_Store"
            or entry.startswith("._")
        )

    def _normalize_single_root_dir(self, root_dir):
        if not os.path.isdir(root_dir):
            return
        entries = os.listdir(root_dir)
        if not entries:
            return
        entries_to_ignore = [
            entry for entry in entries if self._is_ignored_bundle_entry(entry)
        ]
        entries = [
            entry for entry in entries if not self._is_ignored_bundle_entry(entry)
        ]
        child_dirs = [
            entry
            for entry in entries
            if os.path.isdir(os.path.join(root_dir, entry))
        ]
        child_files = [
            entry
            for entry in entries
            if os.path.isfile(os.path.join(root_dir, entry))
        ]
        if len(child_dirs) != 1 or child_files:
            return
        single_dir = os.path.join(root_dir, child_dirs[0])
        for entry in os.listdir(single_dir):
            shutil.move(os.path.join(single_dir, entry), os.path.join(root_dir, entry))
        shutil.rmtree(single_dir)
        for entry in entries_to_ignore:
            path = os.path.join(root_dir, entry)
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.exists(path):
                os.remove(path)
        logger.info("Normalized single-root bundle directory: %s", root_dir)

    async def _run_container_engine_cmd(self, container, kind):
        """This runs a command and asynchronously writes the data to both a storage file
        and a socket

        :param engine_cmd: the list of container engine command arguments
        :param kind: either 'ingestion' or 'program'
        :return:
        """

        # Creating this and setting 2 values to None in case there is not enough time for the worker to get logs, otherwise we will have errors later on
        logs_Unified = [None, None]

        # Create a websocket to send the logs in real time to the codabench instance
        # We need to set a timeout for the websocket connection otherwise the program will get stuck if he websocket does not connect.
        try:
            websocket_url = f"{self.websocket_url}?kind={kind}"
            logger.debug(
                "Connecting to "
                + websocket_url
                + "for container "
                + str(container.get("Id"))
            )
            websocket = await asyncio.wait_for(
                websockets.connect(websocket_url), timeout=10.0
            )
            logger.debug(
                "connected to "
                + str(websocket_url)
                + "for container "
                + str(container.get("Id"))
            )
        except Exception as e:
            logger.error(
                "There was an error trying to connect to the websocket on the codabench instance: "
                + str(e)
            )
            if os.environ.get("LOG_LEVEL", "info").lower() == "debug":
                logger.exception(e)

        start = time.time()

        # Stream the logs of competition container while also sending them to the codabench instance
        try:
            logger.debug("Starting container " + container.get("Id"))
            client.start(container=container.get("Id"))
            logger.debug(
                "Attaching to started container to get the logs :" + container.get("Id")
            )
            container_LogsDemux = client.attach(
                container, demux=True, stream=True, logs=True
            )

            # If we enter the for loop after the container exited, the program will get stuck
            if (
                client.inspect_container(container)["State"]["Status"].lower()
                == "running"
            ):
                logger.debug(
                    "Show the logs and stream them to codabench " + container.get("Id")
                )
                for log in container_LogsDemux:
                    if str(log[0]) != "None":
                        logger.info(log[0].decode())
                        try:
                            await websocket.send(
                                json.dumps({"kind": kind, "message": log[0].decode()})
                            )
                        except Exception as e:
                            logger.error(e)

                    elif str(log[1]) != "None":
                        logger.error(log[1].decode())
                        try:
                            await websocket.send(
                                json.dumps({"kind": kind, "message": log[1].decode()})
                            )
                        except Exception as e:
                            logger.error(e)

        except (docker.errors.NotFound, docker.errors.APIError) as e:
            logger.error(e)
        except Exception as e:
            logger.error(
                "There was an error while starting the container and getting the logs"
                + e
            )
            if os.environ.get("LOG_LEVEL", "info").lower() == "debug":
                logger.exception(e)

        # Get the return code of the competition container once done
        try:
            # Gets the logs of the container, sperating stdout and stderr (first and second position) thanks for demux=True
            logs_Unified = client.attach(container, logs=True, demux=True)
            return_Code = client.wait(container)
            logger.debug(
                f"WORKER_MARKER: Disconnecting from {websocket_url}, program counter = {self.completed_program_counter}"
            )
            await websocket.close()
            client.remove_container(container, force=True)

            logger.debug(
                "Container "
                + container.get("Id")
                + "exited with status code : "
                + str(return_Code["StatusCode"])
            )

        except (
            requests.exceptions.ReadTimeout,
            docker.errors.APIError,
            Exception,
        ) as e:
            logger.error(e)
            return_Code = {"StatusCode": e}

        self.logs[kind] = {
            "returncode": return_Code["StatusCode"],
            "start": start,
            "end": None,
            "stdout": {
                "data": logs_Unified[0],
                "stream": logs_Unified[0],
                "continue": True,
                "location": self.stdout if kind == "program" else self.ingestion_stdout,
            },
            "stderr": {
                "data": logs_Unified[1],
                "stream": logs_Unified[1],
                "continue": True,
                "location": self.stderr if kind == "program" else self.ingestion_stderr,
            },
        }

        self.logs[kind]["end"] = time.time()

        # Communicate that the program is closing
        self.completed_program_counter += 1

    def _get_host_path(self, *paths):
        """Turns an absolute path inside our container, into what the path
        would be on the host machine. We also ensure that the directory exists,
        docker will create if necessary, but other container engines such as
        podman may not."""
        # Take our list of paths and smash 'em together
        path = os.path.join(*paths)

        # pull front of path, which points to the location inside the container
        path = path[len(BASE_DIR) :]

        # add host to front, so when we run commands in the container on the host they
        # can be seen properly
        path = os.path.join(HOST_DIRECTORY, path)

        # Create if necessary
        os.makedirs(path, exist_ok=True)

        return path

    async def _run_program_directory(
        self, program_dir, kind, input_data_dir=None, input_ref_dir=None
    ):
        """
        Function responsible for running program directory

        Args:
            - program_dir : can be either ingestion program or program/submission
            - kind : either `program` or `ingestion`
        """
        # If the directory doesn't even exist, move on
        if not os.path.exists(program_dir):
            logger.warning(f"{program_dir} not found, no program to execute")

            # Communicate that the program is closing
            self.completed_program_counter += 1
            return

        if os.path.exists(os.path.join(program_dir, "metadata.yaml")):
            metadata_path = "metadata.yaml"
        elif os.path.exists(os.path.join(program_dir, "metadata")):
            metadata_path = "metadata"
        else:
            # Display a warning in logs when there is no metadata file in submission/program dir
            if kind == "program":
                logger.warning(
                    "Program directory missing metadata, assuming it's going to be handled by ingestion"
                )
                # Copy submission files into prediction output
                # This is useful for results submissions but wrongly uses storage
                shutil.copytree(program_dir, self.output_dir, dirs_exist_ok=True)
                return
            else:
                raise SubmissionException(
                    "Program directory missing 'metadata.yaml/metadata'"
                )

        logger.info(f"Metadata path is {os.path.join(program_dir, metadata_path)}")
        with open(os.path.join(program_dir, metadata_path), "r") as metadata_file:
            try:  # try to find a command in the metadata, in other cases set metadata to None
                metadata = yaml.load(metadata_file.read(), Loader=yaml.FullLoader)
                logger.info(f"Metadata contains:\n {metadata}")
                if isinstance(metadata, dict):  # command found
                    command = metadata.get("command")
                else:
                    command = None
            except yaml.YAMLError as e:
                logger.error("Error parsing YAML file: ", e)
                print("Error parsing YAML file: ", e)
                command = None
            if not command and kind == "ingestion":
                raise SubmissionException(
                    "Program directory missing 'command' in metadata"
                )
            elif not command:
                logger.warning(
                    f"Warning: {program_dir} has no command in metadata, continuing anyway "
                    f"(may be meant to be consumed by an ingestion program)"
                )
                return
        volumes_host = [
            self._get_host_path(program_dir),
            self._get_host_path(self.output_dir),
            self.data_dir,
        ]
        volumes_config = {
            volumes_host[0]: {
                "bind": "/app/program",
                "mode": "z",
            },
            volumes_host[1]: {
                "bind": "/app/output",
                "mode": "z",
            },
            volumes_host[2]: {
                "bind": "/app/data",
                "mode": "ro",
            },
        }

        if kind == "ingestion":
            # program here is either scoring program or submission, depends on if this ran during Prediction or Scoring
            if self.is_scoring and self.rolling_enabled and self.submission_data:
                ingested_program_location = "input/res"
            elif self.ingestion_only_during_scoring and self.is_scoring:
                # submission program moved to 'input/res' with shutil.move() above
                ingested_program_location = "input/res"
            else:
                ingested_program_location = "program"
            volumes_host.extend(
                [self._get_host_path(self.root_dir, ingested_program_location)]
            )
            tempvolumeConfig = {
                volumes_host[-1]: {
                    "bind": "/app/ingested_program",
                }
            }
            volumes_config.update(tempvolumeConfig)

        if self.is_scoring:
            # For scoring programs, we want to have a shared directory just in case we have an ingestion program.
            # This will add the share dir regardless of ingestion or scoring, as long as we're `is_scoring`
            volumes_host.extend([self._get_host_path(self.root_dir, "shared")])
            tempvolumeConfig = {
                volumes_host[-1]: {
                    "bind": "/app/shared",
                }
            }
            volumes_config.update(tempvolumeConfig)

            # Input from submission (or submission + ingestion combo)
            volumes_host.extend([self._get_host_path(self.input_dir)])
            tempvolumeConfig = {
                volumes_host[-1]: {
                    "bind": "/app/input",
                }
            }
            volumes_config.update(tempvolumeConfig)

        if self.input_data:
            input_data_dir = input_data_dir or os.path.join(self.root_dir, "input_data")
            volumes_host.extend([self._get_host_path(input_data_dir)])
            tempvolumeConfig = {
                volumes_host[-1]: {
                    "bind": "/app/input_data",
                }
            }
            volumes_config.update(tempvolumeConfig)

        if input_ref_dir:
            volumes_host.extend([self._get_host_path(input_ref_dir)])
            tempvolumeConfig = {
                volumes_host[-1]: {
                    "bind": "/app/input/ref",
                }
            }
            volumes_config.update(tempvolumeConfig)

        # Handle Legacy competitions by replacing anything in the run command
        command = replace_legacy_metadata_command(
            command=command,
            kind=kind,
            is_scoring=self.is_scoring,
            ingestion_only_during_scoring=self.ingestion_only_during_scoring,
        )

        cap_drop_list = [
            "AUDIT_WRITE",
            "CHOWN",
            "DAC_OVERRIDE",
            "FOWNER",
            "FSETID",
            "KILL",
            "MKNOD",
            "NET_BIND_SERVICE",
            "NET_RAW",
            "SETFCAP",
            "SETGID",
            "SETPCAP",
            "SETUID",
            "SYS_CHROOT",
        ]
        # Configure whether or not we use the GPU. Also setting auto_remove to False because
        if os.environ.get("CONTAINER_ENGINE_EXECUTABLE", "docker").lower() == "docker":
            security_options = ["no-new-privileges"]
        else:
            security_options = ["label=disable"]
        # Setting the device ID like this allows users to specify which gpu to use in the .env file, with all being the default if no value is given
        device_id = [os.environ.get("GPU_DEVICE", "nvidia.com/gpu=all")]
        if os.environ.get("USE_GPU", "false").lower() == "true":
            logger.info("Running the container with GPU capabilities")
            host_config = client.create_host_config(
                auto_remove=False,
                cap_drop=cap_drop_list,
                binds=volumes_config,
                userns_mode="host",
                security_opt=security_options,
                device_requests=[
                    {
                        "Driver": "cdi",
                        "DeviceIDs": device_id,
                    },
                ],
            )
        else:
            host_config = client.create_host_config(
                auto_remove=False,
                cap_drop=cap_drop_list,
                binds=volumes_config,
                userns_mode="host",
                security_opt=security_options,
            )

        logger.info("Running container with command " + command)
        container_name = (
            self.ingestion_container_name
            if kind == "ingestion"
            else self.program_container_name
        )
        container = client.create_container(
            self.container_image,
            name=container_name,
            host_config=host_config,
            detach=False,
            volumes=volumes_host,
            command=command,
            working_dir="/app/program",
            environment=["PYTHONUNBUFFERED=1"],
        )
        logger.debug("Created container : " + str(container))
        logger.info("Volume configuration of the container: ")
        pprint(volumes_config)
        # This runs the container engine command and asynchronously passes data back via websocket
        try:
            return await self._run_container_engine_cmd(container, kind=kind)
        except Exception as e:
            logger.error(e)
            if os.environ.get("LOG_LEVEL", "info").lower() == "debug":
                logger.exception(e)

    def _ensure_clean_dir(self, path):
        if os.path.exists(path):
            shutil.rmtree(path)
        os.makedirs(path, exist_ok=True)

    def _clean_output_dir(self, keep_dirs=None):
        keep_dirs = set(keep_dirs or [])
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
            return
        for name in os.listdir(self.output_dir):
            if name in keep_dirs:
                continue
            path = os.path.join(self.output_dir, name)
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)

    def _log_round_input_tree(self, round_input_dir, year):
        logger.info(f"ROLLING ROUND: {year}")
        try:
            logger.info(
                "input_data_round contents: "
                + ", ".join(sorted(os.listdir(round_input_dir)))
            )
        except FileNotFoundError:
            logger.info("input_data_round contents: MISSING")
            return

        for dirpath, _, filenames in os.walk(round_input_dir):
            rel_dir = os.path.relpath(dirpath, round_input_dir)
            rel_dir = "." if rel_dir == "." else rel_dir
            for filename in sorted(filenames):
                logger.info(f"input_data_round file: {rel_dir}/{filename}")

        train_matches = glob.glob(os.path.join(round_input_dir, "train*.csv"))
        logger.info(
            "input_data_round train matches (root only): "
            + (", ".join(sorted(train_matches)) if train_matches else "NONE")
        )

    def _list_files(self, root_dir):
        for dirpath, _, filenames in os.walk(root_dir):
            for filename in filenames:
                if filename.startswith("._"):
                    continue
                full_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(full_path, root_dir)
                yield full_path, rel_path

    def _available_columns_str(self, header, max_cols=20):
        if not header:
            return "[]"
        cols = header[:max_cols]
        suffix = " ..." if len(header) > max_cols else ""
        return "[" + ", ".join(cols) + "]" + suffix

    def _to_period_key(self, value, strategy):
        text = str(value).strip() if value is not None else ""
        if not text:
            return None

        if strategy == "numeric":
            try:
                return float(text)
            except (TypeError, ValueError):
                return None

        if strategy == "datetime":
            if pd is not None:
                parsed = pd.to_datetime([text], errors="coerce")
                if not parsed.isna().all():
                    return parsed.iloc[0].to_pydatetime()
                return None
            try:
                return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                return None

        return text

    def _detect_period_strategy(self, period_values):
        if not period_values:
            return "lexicographic"

        numeric_ok = True
        for value in period_values:
            try:
                float(str(value).strip())
            except (TypeError, ValueError):
                numeric_ok = False
                break
        if numeric_ok:
            return "numeric"

        if pd is not None:
            parsed = pd.to_datetime(period_values, errors="coerce")
            if not parsed.isna().any():
                return "datetime"
        else:
            parsed_ok = True
            for value in period_values:
                try:
                    dt.datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
                except ValueError:
                    parsed_ok = False
                    break
            if parsed_ok:
                return "datetime"

        return "lexicographic"

    def _normalize_boundary_key(self, boundary_value, strategy):
        if boundary_value is None:
            return None
        key = self._to_period_key(boundary_value, strategy)
        if key is not None:
            return key
        if strategy == "numeric" and isinstance(boundary_value, str):
            if pd is not None:
                parsed = pd.to_datetime([boundary_value], errors="coerce")
                if not parsed.isna().all():
                    return float(parsed.iloc[0].year)
        return None

    def _get_period_col_index(self, header, src_path):
        if self.rolling_period_col not in header:
            raise SubmissionException(
                f"Period column '{self.rolling_period_col}' not found in {src_path}. "
                f"Available columns: {self._available_columns_str(header)}"
            )
        return header.index(self.rolling_period_col)

    def _build_period_catalog(self):
        master_csv = self._find_first_csv(os.path.join(self.root_dir, "input_data"))
        if not master_csv:
            raise SubmissionException("Rolling enabled but no input data found.")

        with open(master_csv, newline="") as src_file:
            reader = csv.reader(src_file)
            header = next(reader, None)
            if not header:
                raise SubmissionException(f"Input data CSV is empty: {master_csv}")
            period_idx = self._get_period_col_index(header, master_csv)
            raw_values = []
            for row in reader:
                if len(row) <= period_idx:
                    continue
                raw_val = row[period_idx]
                if raw_val is None or str(raw_val).strip() == "":
                    continue
                raw_values.append(str(raw_val).strip())

        if not raw_values:
            raise SubmissionException(
                f"Could not infer rolling periods from column '{self.rolling_period_col}' in {master_csv}."
            )

        strategy = self._detect_period_strategy(raw_values)
        logger.info(
            "Rolling period strategy for column '%s': %s",
            self.rolling_period_col,
            strategy,
        )

        key_to_label = {}
        for raw_val in raw_values:
            key = self._to_period_key(raw_val, strategy)
            if key is None:
                continue
            if key not in key_to_label:
                key_to_label[key] = raw_val

        if not key_to_label:
            raise SubmissionException(
                f"Could not parse period values from column '{self.rolling_period_col}' in {master_csv}."
            )

        ordered_keys = sorted(key_to_label.keys())
        self.period_sort_strategy = strategy
        self.period_key_to_label = key_to_label
        self.period_keys_ordered = ordered_keys
        return ordered_keys

    def _slice_csv_by_period(self, src_path, dst_path, predicate):
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        with open(src_path, newline="") as src_file, open(
            dst_path, "w", newline=""
        ) as dst_file:
            reader = csv.reader(src_file)
            writer = csv.writer(dst_file)
            header = next(reader, None)
            if not header:
                return
            period_idx = self._get_period_col_index(header, src_path)
            writer.writerow(header)
            for row in reader:
                if len(row) <= period_idx:
                    continue
                period_val = self._to_period_key(row[period_idx], self.period_sort_strategy)
                if period_val is None:
                    continue
                if predicate(period_val):
                    writer.writerow(row)

    def _slice_input_data(self, round_input_dir, period_key):
        master_dir = os.path.join(self.root_dir, "input_data")
        files = list(self._list_files(master_dir))
        period_index = self.period_keys_ordered.index(period_key)
        train_keys = set(
            self.period_keys_ordered[
                max(0, period_index - self.rolling_window_size):period_index
            ]
        )
        test_keys = {period_key}
        has_split_markers = any(
            "train" in os.path.basename(path).lower()
            or "test" in os.path.basename(path).lower()
            for path, _ in files
            if path.lower().endswith(".csv")
        )

        for src_path, rel_path in files:
            lower_name = os.path.basename(src_path).lower()
            is_csv = src_path.lower().endswith(".csv")

            if not is_csv:
                dst_path = os.path.join(round_input_dir, rel_path)
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                shutil.copy2(src_path, dst_path)
                continue

            if has_split_markers:
                dst_path = os.path.join(round_input_dir, rel_path)
                if "train" in lower_name:
                    self._slice_csv_by_period(
                        src_path,
                        dst_path,
                        lambda p: p in train_keys,
                    )
                elif "test" in lower_name:
                    self._slice_csv_by_period(
                        src_path,
                        dst_path,
                        lambda p: p in test_keys,
                    )
                else:
                    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                    shutil.copy2(src_path, dst_path)
                continue

            base_dir = os.path.dirname(rel_path)
            base_name = os.path.basename(rel_path)
            train_name = f"train_{base_name}"
            test_name = f"test_{base_name}"
            train_path = os.path.join(round_input_dir, base_dir, train_name)
            test_path = os.path.join(round_input_dir, base_dir, test_name)
            self._slice_csv_by_period(
                src_path,
                train_path,
                lambda p: p in train_keys,
            )
            self._slice_csv_by_period(
                src_path, test_path, lambda p: p in test_keys
            )

    def _slice_input_data_by_predicates(
        self, round_input_dir, train_predicate, test_predicate
    ):
        master_dir = os.path.join(self.root_dir, "input_data")
        files = list(self._list_files(master_dir))
        has_split_markers = any(
            "train" in os.path.basename(path).lower()
            or "test" in os.path.basename(path).lower()
            for path, _ in files
            if path.lower().endswith(".csv")
        )

        for src_path, rel_path in files:
            lower_name = os.path.basename(src_path).lower()
            is_csv = src_path.lower().endswith(".csv")

            if not is_csv:
                dst_path = os.path.join(round_input_dir, rel_path)
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                shutil.copy2(src_path, dst_path)
                continue

            if has_split_markers:
                dst_path = os.path.join(round_input_dir, rel_path)
                if "train" in lower_name:
                    self._slice_csv_by_period(
                        src_path,
                        dst_path,
                        train_predicate,
                    )
                elif "test" in lower_name:
                    self._slice_csv_by_period(
                        src_path,
                        dst_path,
                        test_predicate,
                    )
                else:
                    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                    shutil.copy2(src_path, dst_path)
                continue

            base_dir = os.path.dirname(rel_path)
            base_name = os.path.basename(rel_path)
            train_name = f"train_{base_name}"
            test_name = f"test_{base_name}"
            train_path = os.path.join(round_input_dir, base_dir, train_name)
            test_path = os.path.join(round_input_dir, base_dir, test_name)
            self._slice_csv_by_period(
                src_path, train_path, train_predicate
            )
            self._slice_csv_by_period(
                src_path, test_path, test_predicate
            )

    def _slice_reference_data(self, round_ref_dir, period_key):
        master_dir = os.path.join(self.root_dir, "input", "ref")
        for src_path, rel_path in self._list_files(master_dir):
            if not src_path.lower().endswith(".csv"):
                dst_path = os.path.join(round_ref_dir, rel_path)
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                shutil.copy2(src_path, dst_path)
                continue

            dst_path = os.path.join(round_ref_dir, rel_path)
            self._slice_csv_by_period(
                src_path, dst_path, lambda p: p == period_key
            )

    def _prepare_round_data(self, period_key):
        round_input_dir = os.path.join(self.root_dir, "input_data_round")
        round_ref_dir = os.path.join(self.root_dir, "input_ref_round")
        self._ensure_clean_dir(round_input_dir)
        self._ensure_clean_dir(round_ref_dir)
        self._slice_input_data(round_input_dir, period_key)
        self._slice_reference_data(round_ref_dir, period_key)
        self._merge_train_with_labels(round_input_dir, round_ref_dir)
        return round_input_dir, round_ref_dir

    def _prepare_static_data(self, evaluation_period_keys):
        round_input_dir = os.path.join(self.root_dir, "input_data_static")
        round_ref_dir = os.path.join(self.root_dir, "input_ref_static")
        self._ensure_clean_dir(round_input_dir)
        self._ensure_clean_dir(round_ref_dir)

        first_eval_index = self.period_keys_ordered.index(evaluation_period_keys[0])
        train_keys = set(
            self.period_keys_ordered[
                max(0, first_eval_index - self.rolling_window_size):first_eval_index
            ]
        )
        eval_keys = set(evaluation_period_keys)
        self._slice_input_data_by_predicates(
            round_input_dir,
            lambda p: p in train_keys,
            lambda p: p in eval_keys,
        )
        self._merge_train_with_labels(round_input_dir, round_ref_dir)
        return round_input_dir, round_ref_dir

    def _has_static_split_config(self):
        return bool(self.static_split_column) and bool(self.static_split_value)

    def _prepare_static_split_data(self):
        if not self._has_static_split_config():
            raise SubmissionException(
                "Static split is not configured. Set both static_split_column and static_split_value."
            )

        round_input_dir = os.path.join(self.root_dir, "input_data_static_split")
        round_ref_dir = os.path.join(self.root_dir, "input_ref_static_split")
        self._ensure_clean_dir(round_input_dir)
        self._ensure_clean_dir(round_ref_dir)

        # Preserve rolling configuration; static split temporarily reuses the same slicing helpers.
        prev_period_col = self.rolling_period_col
        prev_strategy = self.period_sort_strategy
        prev_key_to_label = dict(self.period_key_to_label)
        prev_period_keys_ordered = list(self.period_keys_ordered)
        try:
            self.rolling_period_col = self.static_split_column
            period_keys = self._build_period_catalog()
            split_key = self._normalize_boundary_key(
                self.static_split_value, self.period_sort_strategy
            )
            if split_key is None:
                raise SubmissionException(
                    f"Could not parse static split value '{self.static_split_value}' "
                    f"for column '{self.static_split_column}'."
                )

            train_predicate = lambda p: p < split_key
            test_predicate = lambda p: p >= split_key
            self._slice_input_data_by_predicates(
                round_input_dir, train_predicate, test_predicate
            )

            # Pass through full reference directory for scoring stage compatibility.
            master_ref_dir = os.path.join(self.root_dir, "input", "ref")
            for src_path, rel_path in self._list_files(master_ref_dir):
                dst_path = os.path.join(round_ref_dir, rel_path)
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                shutil.copy2(src_path, dst_path)

            self._merge_train_with_labels(round_input_dir, round_ref_dir)

            train_candidates = glob.glob(os.path.join(round_input_dir, "train*.csv"))
            test_candidates = glob.glob(os.path.join(round_input_dir, "test*.csv"))
            train_rows = (
                self._count_csv_rows(train_candidates[0]) if train_candidates else 0
            )
            test_rows = (
                self._count_csv_rows(test_candidates[0]) if test_candidates else 0
            )
            if train_rows <= 0:
                raise SubmissionException(
                    "Static split produced an empty train set. Adjust static split settings."
                )
            if test_rows <= 0:
                raise SubmissionException(
                    "Static split produced an empty test set. Adjust static split settings."
                )
            if len(period_keys) < 2:
                raise SubmissionException(
                    "Static split requires at least two distinct period values."
                )

            split_label = self.period_key_to_label.get(split_key, str(self.static_split_value))
            return round_input_dir, round_ref_dir, {
                "split_column": self.static_split_column,
                "split_value": split_label,
                "train_rows": train_rows,
                "test_rows": test_rows,
            }
        finally:
            self.rolling_period_col = prev_period_col
            self.period_sort_strategy = prev_strategy
            self.period_key_to_label = prev_key_to_label
            self.period_keys_ordered = prev_period_keys_ordered

    def _count_csv_rows(self, path):
        if not os.path.exists(path):
            return 0
        with open(path, newline="") as src_file:
            reader = csv.reader(src_file)
            header = next(reader, None)
            if header is None:
                return 0
            return sum(1 for _ in reader)

    def _pick_one_csv(self, paths, kind):
        paths = [p for p in paths if os.path.basename(p) and not os.path.basename(p).startswith("._")]
        if not paths:
            raise SubmissionException(
                f"No {kind} CSV file found. Expected something like '{kind}*.csv'."
            )
        paths = sorted(paths, key=lambda p: (len(os.path.basename(p)), os.path.basename(p)))
        return paths[0]

    def _is_label_like_col(self, name):
        lowered = (name or "").lower()
        return "y_" in lowered or "label" in lowered

    def _infer_join_cols_from_fields(self, left_fields, right_fields, excluded_cols=None):
        excluded = set(excluded_cols or [])
        join_cols = [
            col for col in left_fields
            if col in right_fields and col not in excluded
        ]
        if not join_cols:
            raise SubmissionException("No shared non-label columns found to join input and reference data.")
        return join_cols

    def _merge_train_with_labels(self, round_input_dir, round_ref_dir):
        train_candidates = glob.glob(os.path.join(round_input_dir, "train*.csv"))
        master_ref_dir = os.path.join(self.root_dir, "input", "ref")
        master_ref_candidates = glob.glob(os.path.join(master_ref_dir, "*.csv"))
        ref_candidates = master_ref_candidates or glob.glob(
            os.path.join(round_ref_dir, "*.csv")
        )
        if not train_candidates or not ref_candidates:
            logger.warning("Skipping train/label merge due to missing inputs.")
            return

        train_path = self._pick_one_csv(train_candidates, "train")
        ref_path = self._pick_one_csv(ref_candidates, "label")
        if master_ref_candidates:
            logger.info("Using full reference labels for train merge: %s", ref_path)

        with open(train_path, newline="") as train_file:
            train_reader = csv.DictReader(train_file)
            train_fields = train_reader.fieldnames or []
            if not train_fields:
                raise SubmissionException(f"Train file is empty: {train_path}")

            train_label_fields = [
                name
                for name in train_fields
                if self._is_label_like_col(name)
            ]
            if train_label_fields:
                dst_path = os.path.join(round_input_dir, "train.csv")
                if os.path.abspath(train_path) != os.path.abspath(dst_path):
                    shutil.copy2(train_path, dst_path)
                logger.info(f"Using existing labeled train file: {dst_path}")
                return

            with open(ref_path, newline="") as ref_file:
                ref_reader = csv.DictReader(ref_file)
                ref_fields = ref_reader.fieldnames or []
                label_cols = [
                    name
                    for name in ref_fields
                    if self._is_label_like_col(name)
                ]
                if not label_cols:
                    raise SubmissionException(
                        f"Could not identify label columns in {ref_path}"
                    )

                join_cols = self._infer_join_cols_from_fields(
                    train_fields, ref_fields, excluded_cols=label_cols
                )
                logger.info("Joining train and reference data using columns: %s", join_cols)

                ref_map = {}
                for row in ref_reader:
                    key = tuple(row.get(col) for col in join_cols)
                    ref_map[key] = {label_col: row.get(label_col) for label_col in label_cols}

        dst_path = os.path.join(round_input_dir, "train.csv")
        written = 0
        skipped = 0
        with open(train_path, newline="") as train_file, open(
            dst_path, "w", newline=""
        ) as out_file:
            train_reader = csv.DictReader(train_file)
            out_fields = list(train_reader.fieldnames or [])
            out_fields.extend(
                label_col for label_col in label_cols if label_col not in out_fields
            )
            writer = csv.DictWriter(out_file, fieldnames=out_fields)
            writer.writeheader()
            for row in train_reader:
                key = tuple(row.get(col) for col in join_cols)
                label_vals = ref_map.get(key)
                if not label_vals:
                    skipped += 1
                    continue
                missing_labels = [
                    label_col
                    for label_col in label_cols
                    if label_vals.get(label_col) in (None, "")
                ]
                if missing_labels:
                    skipped += 1
                    continue
                for label_col in label_cols:
                    row[label_col] = label_vals[label_col]
                writer.writerow(row)
                written += 1

        logger.info(
            f"Wrote labeled train file: {dst_path} (rows={written}, skipped={skipped}, label_cols={len(label_cols)})"
        )

    def _find_first_csv(self, root_dir):
        for dirpath, _, filenames in os.walk(root_dir):
            for filename in filenames:
                if filename.lower().endswith(".csv"):
                    return os.path.join(dirpath, filename)
        return None

    def _find_submission_file(self):
        preferred_files = ("predictions.csv", "submission.csv")
        for name in preferred_files:
            direct_path = os.path.join(self.output_dir, name)
            if os.path.exists(direct_path):
                return direct_path
        for dirpath, _, filenames in os.walk(self.output_dir):
            for filename in filenames:
                if (
                    filename.lower().endswith(".csv")
                    and "predictions" in filename.lower()
                ):
                    return os.path.join(dirpath, filename)
        for dirpath, _, filenames in os.walk(self.output_dir):
            for filename in filenames:
                if (
                    filename.lower().endswith(".csv")
                    and "submission" in filename.lower()
                ):
                    return os.path.join(dirpath, filename)
        return self._find_first_csv(self.output_dir)

    def _select_column(self, candidates, preferred_tokens):
        for token in preferred_tokens:
            for name in candidates:
                if token in name.lower():
                    return name
        if len(candidates) == 1:
            return candidates[0]
        return None

    def _load_csv_header(self, path):
        with open(path, newline="") as src_file:
            reader = csv.reader(src_file)
            return next(reader, [])

    def _extract_labels_and_predictions(self, pred_path, ref_path):
        pred_cols = self._load_csv_header(pred_path)
        ref_cols = self._load_csv_header(ref_path)

        pred_only = [col for col in pred_cols if col not in ref_cols]
        ref_only = [col for col in ref_cols if col not in pred_cols]
        join_cols = [col for col in pred_cols if col in ref_cols]

        pred_col = "p1" if "p1" in pred_only else None
        if pred_col is None:
            pred_col = self._select_column(pred_only, ["pred", "score", "prob"])
        label_col = self._select_column(ref_only, ["label", "target", "y_"])

        if not join_cols and self.rolling_period_col in pred_cols:
            join_cols = [self.rolling_period_col]

        if not pred_col or not label_col or not join_cols:
            raise SubmissionException(
                f"Could not infer prediction/label columns for {pred_path} and {ref_path}"
            )

        ref_map = {}
        with open(ref_path, newline="") as ref_file:
            reader = csv.DictReader(ref_file)
            for row in reader:
                key = tuple(row.get(col) for col in join_cols)
                ref_map[key] = row.get(label_col)

        y_true = []
        y_score = []
        with open(pred_path, newline="") as pred_file:
            reader = csv.DictReader(pred_file)
            for row in reader:
                key = tuple(row.get(col) for col in join_cols)
                if key not in ref_map:
                    continue
                try:
                    y_true_val = int(float(ref_map[key]))
                    y_score_val = float(row.get(pred_col))
                except (TypeError, ValueError):
                    continue
                y_true.append(y_true_val)
                y_score.append(y_score_val)

        return y_true, y_score

    def _roc_auc_score(self, y_true, y_score):
        n = len(y_true)
        if n == 0:
            return math.nan
        pairs = sorted(zip(y_score, y_true), key=lambda x: x[0])
        n_pos = sum(1 for _, y in pairs if y == 1)
        n_neg = n - n_pos
        if n_pos == 0 or n_neg == 0:
            return math.nan

        rank_sum = 0.0
        i = 0
        rank = 1
        while i < n:
            j = i
            score = pairs[i][0]
            while j < n and pairs[j][0] == score:
                j += 1
            avg_rank = (rank + (rank + (j - i) - 1)) / 2.0
            for k in range(i, j):
                if pairs[k][1] == 1:
                    rank_sum += avg_rank
            rank += j - i
            i = j

        u = rank_sum - (n_pos * (n_pos + 1)) / 2.0
        return u / (n_pos * n_neg)

    def _infer_join_cols(self, pred_cols, ref_cols):
        label_cols = [col for col in ref_cols if self._is_label_like_col(col)]
        return self._infer_join_cols_from_fields(
            pred_cols, ref_cols, excluded_cols=label_cols
        )

    def _infer_label_col(self, ref_cols):
        if "y_12m" in ref_cols:
            return "y_12m"
        for name in ref_cols:
            lowered = name.lower()
            if "y_" in lowered or "label" in lowered or "target" in lowered:
                return name
        return None

    def _infer_pred_col(self, pred_cols):
        if "p1" in pred_cols:
            return "p1"
        for name in pred_cols:
            lowered = name.lower()
            if "pred" in lowered or "score" in lowered or "prob" in lowered:
                return name
        return None

    def _compute_metrics_from_predictions(self, pred_path, ref_path, evaluation_period_keys):
        pred_cols = self._load_csv_header(pred_path)
        ref_cols = self._load_csv_header(ref_path)

        join_cols = self._infer_join_cols(pred_cols, ref_cols)
        if not join_cols:
            raise SubmissionException(
                f"No join columns found between {pred_path} and {ref_path}. "
                f"Pred cols={pred_cols} Ref cols={ref_cols}"
            )

        label_col = self._infer_label_col(ref_cols)
        if not label_col:
            raise SubmissionException(
                f"Could not identify label column in {ref_path}. Ref cols={ref_cols}"
            )

        pred_col = self._infer_pred_col(pred_cols)
        if not pred_col:
            logger.warning(
                "Could not identify a single prediction column in %s (Pred cols=%s). "
                "This file contains multi-horizon risk columns — skipping worker-side AUC. "
                "Scores will be computed by the scoring program.",
                pred_path,
                pred_cols,
            )
            return {
                "overall_auc": None,
                "mean_yearly_auc": None,
                "yearly_auc": [],
            }

        ref_map = {}
        eval_period_set = set(evaluation_period_keys)
        period_idx = self._get_period_col_index(ref_cols, ref_path)
        with open(ref_path, newline="") as ref_file:
            reader = csv.DictReader(ref_file)
            for row in reader:
                key = tuple(row.get(col) for col in join_cols)
                if len(ref_cols) <= period_idx:
                    continue
                period_key = self._to_period_key(
                    row.get(self.rolling_period_col), self.period_sort_strategy
                )
                if period_key is None or period_key not in eval_period_set:
                    continue
                ref_map[key] = (row.get(label_col), period_key)

        yearly = {period_key: {"y_true": [], "y_score": []} for period_key in evaluation_period_keys}
        overall_y_true = []
        overall_y_score = []

        with open(pred_path, newline="") as pred_file:
            reader = csv.DictReader(pred_file)
            for row in reader:
                key = tuple(row.get(col) for col in join_cols)
                if key not in ref_map:
                    continue
                label_raw, period_key = ref_map[key]
                try:
                    label_val = int(float(label_raw))
                    score_val = float(row.get(pred_col))
                except (TypeError, ValueError):
                    continue
                y_true = 1 if label_val == 1 else 0
                yearly[period_key]["y_true"].append(y_true)
                yearly[period_key]["y_score"].append(score_val)
                overall_y_true.append(y_true)
                overall_y_score.append(score_val)

        yearly_auc = []
        valid_aucs = []
        for period_key in evaluation_period_keys:
            period_label = self.period_key_to_label.get(period_key, str(period_key))
            y_true = yearly[period_key]["y_true"]
            y_score = yearly[period_key]["y_score"]
            n_total = len(y_true)
            n_pos = sum(1 for y in y_true if y == 1)
            n_neg = n_total - n_pos
            if n_total == 0:
                yearly_auc.append(
                    {
                        "period": period_label,
                        "year": period_label,
                        "auc": None,
                        "n_total": 0,
                        "n_pos": 0,
                        "reason": "no_matches",
                    }
                )
                continue
            if n_pos == 0 or n_neg == 0:
                yearly_auc.append(
                    {
                        "period": period_label,
                        "year": period_label,
                        "auc": None,
                        "n_total": n_total,
                        "n_pos": n_pos,
                        "reason": "zero_positive_or_negative",
                    }
                )
                continue
            auc = self._roc_auc_score(y_true, y_score)
            yearly_auc.append(
                {
                    "period": period_label,
                    "year": period_label,
                    "auc": auc,
                    "n_total": n_total,
                    "n_pos": n_pos,
                }
            )
            if not math.isnan(auc):
                valid_aucs.append(auc)

        mean_yearly_auc = sum(valid_aucs) / len(valid_aucs) if valid_aucs else math.nan
        overall_auc = self._roc_auc_score(overall_y_true, overall_y_score)

        return {
            "overall_auc": overall_auc,
            "mean_yearly_auc": mean_yearly_auc,
            "yearly_auc": yearly_auc,
        }

    def _write_yearly_auc_csv(self, path, yearly_auc):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="") as out_file:
            writer = csv.writer(out_file)
            writer.writerow(["period", "auc", "n_total", "n_pos", "reason"])
            for row in yearly_auc:
                writer.writerow(
                    [
                        row.get("period", row.get("year")),
                        row.get("auc"),
                        row.get("n_total"),
                        row.get("n_pos"),
                        row.get("reason"),
                    ]
                )

    def _load_output_scores_file(self):
        scores_json_path = os.path.join(self.output_dir, "scores.json")
        if os.path.exists(scores_json_path):
            with open(scores_json_path) as scores_file:
                try:
                    return json.load(scores_file)
                except json.decoder.JSONDecodeError as e:
                    raise SubmissionException(
                        f"Could not decode scores json properly, it contains an error.\n{e.msg}"
                    )

        scores_txt_path = os.path.join(self.output_dir, "scores.txt")
        if os.path.exists(scores_txt_path):
            with open(scores_txt_path) as scores_file:
                return yaml.load(scores_file, yaml.Loader)

        return None

    def _run_programs_once(
        self, program_dir, ingestion_program_dir, input_data_dir=None, input_ref_dir=None
    ):
        loop = asyncio.new_event_loop()
        try:
            async def run_with_watch():
                watch_task = asyncio.create_task(self.watch_detailed_results())
                try:
                    await asyncio.gather(
                        self._run_program_directory(
                            program_dir,
                            kind="program",
                            input_data_dir=input_data_dir,
                            input_ref_dir=input_ref_dir,
                        ),
                        self._run_program_directory(
                            ingestion_program_dir,
                            kind="ingestion",
                            input_data_dir=input_data_dir,
                            input_ref_dir=input_ref_dir,
                        ),
                    )
                finally:
                    watch_task.cancel()
                    try:
                        await watch_task
                    except asyncio.CancelledError:
                        pass

            loop.run_until_complete(run_with_watch())
        finally:
            loop.close()

    def _run_programs_sequential(
        self, program_dir, ingestion_program_dir, input_data_dir=None, input_ref_dir=None
    ):
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                self._run_program_directory(
                    ingestion_program_dir,
                    kind="ingestion",
                    input_data_dir=input_data_dir,
                    input_ref_dir=input_ref_dir,
                )
            )
            self._sync_predictions_to_input_res()

            async def run_with_watch():
                watch_task = asyncio.create_task(self.watch_detailed_results())
                try:
                    await self._run_program_directory(
                        program_dir,
                        kind="program",
                        input_data_dir=input_data_dir,
                        input_ref_dir=input_ref_dir,
                    )
                finally:
                    watch_task.cancel()
                    try:
                        await watch_task
                    except asyncio.CancelledError:
                        pass

            loop.run_until_complete(run_with_watch())
        finally:
            loop.close()

    def _sync_predictions_to_input_res(self):
        pred_path = self._find_submission_file()
        if not pred_path:
            logger.warning("No predictions file found to stage in input/res.")
            return
        res_dir = os.path.join(self.input_dir, "res")
        os.makedirs(res_dir, exist_ok=True)
        dst_path = os.path.join(res_dir, "predictions.csv")
        shutil.copy2(pred_path, dst_path)

    def _finalize_run_logs(self):
        self.watch = False
        for kind, logs in self.logs.items():
            if logs["end"] is not None:
                elapsed_time = logs["end"] - logs["start"]
            else:
                elapsed_time = self.execution_time_limit
            return_code = logs["returncode"]
            if return_code is None:
                logger.warning("No return code from Process. Killing it")
                if kind == "ingestion":
                    containers_to_kill = self.ingestion_container_name
                else:
                    containers_to_kill = self.program_container_name
                try:
                    client.kill(containers_to_kill)
                    client.remove_container(containers_to_kill, force=True)
                except docker.errors.APIError as e:
                    logger.error(e)
                except Exception as e:
                    logger.error(
                        "There was a problem killing " + str(containers_to_kill) + e
                    )
                    if os.environ.get("LOG_LEVEL", "info").lower() == "debug":
                        logger.exception(e)
            if kind == "program":
                self.program_exit_code = return_code
                self.program_elapsed_time = elapsed_time
            elif kind == "ingestion":
                self.ingestion_program_exit_code = return_code
                self.ingestion_elapsed_time = elapsed_time
            logger.info(f"[exited with {logs['returncode']}]")
            for key, value in logs.items():
                if key not in ["stdout", "stderr"]:
                    continue
                if value["data"]:
                    logger.info(f"[{key}]\n{value['data']}")
                    self._put_file(value["location"], raw_data=value["data"])

            logger.info("Program finished")

    def _resolve_rolling_periods(self):
        period_keys = self._build_period_catalog()
        if len(period_keys) <= self.rolling_window_size:
            raise SubmissionException(
                "Rolling window size exceeds available history for evaluation."
            )

        start_key = self._normalize_boundary_key(self.rolling_start_period, self.period_sort_strategy)
        end_key = self._normalize_boundary_key(self.rolling_end_period, self.period_sort_strategy)

        if start_key is None and self.rolling_start_year is not None:
            start_key = self._normalize_boundary_key(self.rolling_start_year, self.period_sort_strategy)
        if end_key is None and self.rolling_end_year is not None:
            end_key = self._normalize_boundary_key(self.rolling_end_year, self.period_sort_strategy)

        if start_key is not None and end_key is not None and start_key > end_key:
            raise SubmissionException("Rolling start period is greater than end period.")

        valid_indices = []
        for idx, key in enumerate(period_keys):
            if start_key is not None and key < start_key:
                continue
            if end_key is not None and key > end_key:
                continue
            valid_indices.append(idx)

        if not valid_indices:
            raise SubmissionException(
                "No rolling periods match the configured rolling start/end bounds."
            )

        start_idx = max(valid_indices[0], self.rolling_window_size)
        end_idx = valid_indices[-1]
        if start_idx > end_idx:
            raise SubmissionException(
                "Rolling start period exceeds end period after window-size adjustment."
            )

        evaluation_keys = period_keys[start_idx:end_idx + 1]
        logger.info(
            "Resolved rolling periods (%s): %s",
            len(evaluation_keys),
            [self.period_key_to_label.get(k, str(k)) for k in evaluation_keys],
        )
        return evaluation_keys

    def _run_static_baseline(self, ingestion_program_dir, evaluation_period_keys):
        first_eval = self.period_key_to_label.get(evaluation_period_keys[0], str(evaluation_period_keys[0]))
        last_eval = self.period_key_to_label.get(evaluation_period_keys[-1], str(evaluation_period_keys[-1]))
        logger.info(
            "Running static baseline: test periods %s -> %s",
            first_eval,
            last_eval,
        )
        round_input_dir, round_ref_dir = self._prepare_static_data(evaluation_period_keys)
        self._log_round_input_tree(round_input_dir, first_eval)

        train_candidates = glob.glob(os.path.join(round_input_dir, "train*.csv"))
        test_candidates = glob.glob(os.path.join(round_input_dir, "test*.csv"))
        if train_candidates:
            logger.info(
                "Static train rows: %s", self._count_csv_rows(train_candidates[0])
            )
        if test_candidates:
            logger.info(
                "Static test rows: %s", self._count_csv_rows(test_candidates[0])
            )

        self.logs = {}
        self.completed_program_counter = 0
        self.watch = True
        try:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(
                    self._run_program_directory(
                        ingestion_program_dir,
                        kind="ingestion",
                        input_data_dir=round_input_dir,
                        input_ref_dir=round_ref_dir,
                    )
                )
            finally:
                loop.close()
        finally:
            self._finalize_run_logs()

        self._sync_predictions_to_input_res()
        pred_path = self._find_submission_file()
        if not pred_path:
            raise SubmissionException("Static baseline produced no predictions.")

        static_pred_path = os.path.join(self.output_dir, "static_predictions.csv")
        shutil.copy2(pred_path, static_pred_path)
        logger.info("Wrote static predictions: %s", static_pred_path)

        ref_path = self._find_first_csv(os.path.join(self.root_dir, "input", "ref"))
        static_metrics = self._compute_metrics_from_predictions(
            static_pred_path, ref_path, evaluation_period_keys
        )
        self._write_yearly_auc_csv(
            os.path.join(self.output_dir, "yearly_aucs_static.csv"),
            static_metrics["yearly_auc"],
        )
        return static_metrics

    def _run_rolling_window(self, ingestion_program_dir, evaluation_period_keys):
        logger.info(
            "Running rolling window for periods: %s",
            [self.period_key_to_label.get(k, str(k)) for k in evaluation_period_keys],
        )
        full_ref_path = self._find_first_csv(os.path.join(self.root_dir, "input", "ref"))
        combined_pred_path = os.path.join(self.root_dir, "rolling_predictions.csv")
        if os.path.exists(combined_pred_path):
            os.remove(combined_pred_path)
        combined_header = None
        combined_rows = 0

        for period_key in evaluation_period_keys:
            period_label = self.period_key_to_label.get(period_key, str(period_key))
            logger.info("Rolling round for period %s", period_label)
            round_input_dir, round_ref_dir = self._prepare_round_data(period_key)
            self._log_round_input_tree(round_input_dir, period_label)

            train_candidates = glob.glob(os.path.join(round_input_dir, "train*.csv"))
            test_candidates = glob.glob(os.path.join(round_input_dir, "test*.csv"))
            if train_candidates:
                logger.info(
                    "Rolling train rows (%s): %s",
                    period_label,
                    self._count_csv_rows(train_candidates[0]),
                )
            if test_candidates:
                logger.info(
                    "Rolling test rows (%s): %s",
                    period_label,
                    self._count_csv_rows(test_candidates[0]),
                )

            self.logs = {}
            self.completed_program_counter = 0
            self.watch = True
            try:
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(
                        self._run_program_directory(
                            ingestion_program_dir,
                            kind="ingestion",
                            input_data_dir=round_input_dir,
                            input_ref_dir=round_ref_dir,
                        )
                    )
                finally:
                    loop.close()
            finally:
                self._finalize_run_logs()

            self._sync_predictions_to_input_res()
            round_pred_path = self._find_submission_file()
            if not round_pred_path:
                raise SubmissionException(
                    f"Rolling round {period_label} produced no predictions."
                )

            with open(round_pred_path, newline="") as pred_file:
                reader = csv.reader(pred_file)
                file_header = next(reader, None)
                if not file_header:
                    raise SubmissionException(
                        f"Predictions file is empty for rolling round {period_label}."
                    )
                mode = "w" if combined_header is None else "a"
                with open(combined_pred_path, mode, newline="") as out_file:
                    writer = csv.writer(out_file)
                    if combined_header is None:
                        combined_header = file_header
                        writer.writerow(combined_header)
                    elif file_header != combined_header:
                        raise SubmissionException(
                            f"Predictions header mismatch in rolling round {period_label}."
                        )
                    for row in reader:
                        writer.writerow(row)
                        combined_rows += 1

        if combined_header is None or combined_rows == 0:
            raise SubmissionException("No combined predictions collected in rolling.")

        rolling_pred_path = os.path.join(self.output_dir, "rolling_predictions.csv")
        shutil.copy2(combined_pred_path, rolling_pred_path)
        logger.info("Wrote rolling predictions: %s", rolling_pred_path)

        rolling_metrics = self._compute_metrics_from_predictions(
            rolling_pred_path, full_ref_path, evaluation_period_keys
        )
        self._write_yearly_auc_csv(
            os.path.join(self.output_dir, "yearly_aucs_rolling.csv"),
            rolling_metrics["yearly_auc"],
        )
        return rolling_metrics

    def _run_static_and_rolling(self, program_dir, ingestion_program_dir):
        if not os.path.exists(ingestion_program_dir):
            raise SubmissionException(
                "Rolling requires an ingestion program during scoring; ingestion_program is missing."
            )
        evaluation_period_keys = self._resolve_rolling_periods()
        first_eval = self.period_key_to_label.get(evaluation_period_keys[0], str(evaluation_period_keys[0]))
        last_eval = self.period_key_to_label.get(evaluation_period_keys[-1], str(evaluation_period_keys[-1]))
        logger.info(
            "Evaluating static + rolling: start_period=%s end_period=%s window=%s period_col=%s",
            first_eval,
            last_eval,
            self.rolling_window_size,
            self.rolling_period_col,
        )

        static_results = self._run_static_baseline(
            ingestion_program_dir, evaluation_period_keys
        )
        rolling_results = self._run_rolling_window(
            ingestion_program_dir, evaluation_period_keys
        )

        # Generate detailed results for rolling predictions
        res_dir = os.path.join(self.input_dir, "res")
        os.makedirs(res_dir, exist_ok=True)
        shutil.copy2(
            os.path.join(self.output_dir, "rolling_predictions.csv"),
            os.path.join(res_dir, "predictions.csv"),
        )
        self.logs = {}
        self.completed_program_counter = 0
        self.watch = True
        loop = asyncio.new_event_loop()
        try:
            async def run_scoring_with_watch():
                watch_task = asyncio.create_task(self.watch_detailed_results())
                try:
                    await self._run_program_directory(
                        program_dir,
                        kind="program",
                        input_data_dir=None,
                        input_ref_dir=os.path.join(self.root_dir, "input", "ref"),
                    )
                finally:
                    watch_task.cancel()
                    try:
                        await watch_task
                    except asyncio.CancelledError:
                        pass

            loop.run_until_complete(run_scoring_with_watch())
        finally:
            loop.close()
            self._finalize_run_logs()

        scoring_scores = self._load_output_scores_file()
        if scoring_scores is None:
            logger.warning(
                "Rolling scoring program did not produce scores.json/scores.txt; "
                "falling back to worker-computed AUC keys."
            )
            scoring_scores = {
                "mean_yearly_auc": rolling_results.get("mean_yearly_auc"),
                "overall_auc": rolling_results.get("overall_auc"),
            }
        elif not isinstance(scoring_scores, dict):
            raise SubmissionException(
                "Rolling scoring program scores must be a JSON/YAML object."
            )

        final_scores = {
            "config": {
                "rolling_start_period": first_eval,
                "rolling_end_period": last_eval,
                "period_col": self.rolling_period_col,
                "window_size": self.rolling_window_size,
            },
            "static": static_results,
            "rolling": rolling_results,
            "yearly_scores": [
                {
                    "year": row.get("period", row.get("year")),
                    "scores": {},
                    "year_auc": row.get("auc"),
                }
                for row in rolling_results.get("yearly_auc", [])
            ],
        }
        final_scores.update(scoring_scores)
        self.combined_scores = final_scores

    def _put_dir(self, url, directory):
        """Zip the directory and send it to the given URL using _put_file."""
        logger.info("Putting dir %s in %s" % (directory, url))
        retries, max_retries = (0, 3)
        while retries < max_retries:
            # Zip the directory
            start_time = time.time()
            zip_path = make_archive(
                os.path.join(self.root_dir, str(uuid.uuid4())), "zip", directory
            )
            duration = time.time() - start_time
            logger.info(f"Time needed to zip archive: {duration} seconds.")
            if is_valid_zip(zip_path):  # Check zip integrity
                self._put_file(url, file=zip_path)  # Send the file
                break  # Leave the loop in case of success
            else:
                retries += 1
                if retries >= max_retries:
                    raise Exception("ZIP file is corrupted or incomplete.")
                else:
                    logger.info("Failed. Retrying in 30 seconds...")
                    time.sleep(30)  # Wait 30 seconds before retrying

    def _put_file(self, url, file=None, raw_data=None, content_type="application/zip"):
        """Send the file in the storage."""
        if file and raw_data:
            raise Exception("Cannot put both a file and raw_data")

        headers = {
            # For Azure only, other systems ignore these headers
            "x-ms-blob-type": "BlockBlob",
            "x-ms-version": "2018-03-28",
        }
        if content_type:
            headers["Content-Type"] = content_type
        if file:
            logger.info("Putting file %s in %s" % (file, url))
            data = open(file, "rb")
            headers["Content-Length"] = str(os.path.getsize(file))
        elif raw_data:
            logger.info("Putting raw data %s in %s" % (raw_data, url))
            data = raw_data
        else:
            raise SubmissionException(
                "Must provide data, both file and raw_data cannot be empty"
            )

        resp = self.requests_session.put(
            url,
            data=data,
            headers=headers,
        )
        logger.info("*** PUT RESPONSE: ***")
        logger.info(f"response: {resp}")
        logger.info(f"content: {resp.content}")

    def _prep_cache_dir(self, max_size=MAX_CACHE_DIR_SIZE_GB):
        if not os.path.exists(CACHE_DIR):
            os.mkdir(CACHE_DIR)
        logger.info("Checking if cache directory needs to be pruned...")
        if get_folder_size_in_gb(CACHE_DIR) > max_size:
            logger.info("Pruning cache directory")
            delete_files_in_folder(CACHE_DIR)
        else:
            logger.info("Cache directory does not need to be pruned!")

    def prepare(self):
        if not self.is_scoring:
            # Only during prediction step do we want to announce "preparing"
            self._update_status(STATUS_PREPARING)

        # Setup cache and prune if it's out of control
        self._prep_cache_dir()

        # A run *may* contain the following bundles, let's grab them and dump them in the appropriate
        # sub folder.
        bundles = [
            # (url to file, relative folder destination)
            (self.program_data, "program"),
            (self.ingestion_program_data, "ingestion_program"),
            (self.input_data, "input_data"),
            (self.reference_data, "input/ref"),
        ]
        if self.is_scoring:
            # Send along submission result so scoring_program can get access
            if self.rolling_enabled and self.submission_data:
                bundles += [(self.submission_data, "input/res")]
            else:
                bundles += [(self.prediction_result, "input/res")]

        for url, path in bundles:
            if url is not None:
                # At the moment let's just cache input & reference data
                cache_this_bundle = path in ("input_data", "input/ref")
                zip_file = self._get_bundle(url, path, cache=cache_this_bundle)

                # TODO: When we have `is_scoring_only` this needs to change...
                if url == self.program_data and not self.is_scoring:
                    # We want to get a checksum of submissions so we can check if they are
                    # a solution, or maybe match them against other submissions later
                    logger.info(f"Beginning MD5 checksum of submission: {zip_file}")
                    checksum = md5(zip_file)
                    logger.info(f"Checksum result: {checksum}")
                    self._update_submission({"md5": checksum})

        # For logging purposes let's dump file names
        for filename in glob.iglob(self.root_dir + "**/*.*", recursive=True):
            logger.info(filename)

        # Before the run starts we want to download images, they may take a while to download
        # and to do this during the run would subtract from the participants time.
        self._get_container_image(self.container_image)

    def start(self):
        hostname = utils.nodenames.gethostname()
        if self.is_scoring:
            self._update_status(
                STATUS_RUNNING, extra_information=f"scoring_hostname-{hostname}"
            )
        else:
            self._update_status(
                STATUS_RUNNING, extra_information=f"ingestion_hostname-{hostname}"
            )
        program_dir = os.path.join(self.root_dir, "program")
        ingestion_program_dir = os.path.join(self.root_dir, "ingestion_program")

        signal.signal(signal.SIGALRM, alarm_handler)
        signal.alarm(self.execution_time_limit)
        try:
            if self.is_scoring:
                if self.rolling_enabled:
                    self._run_static_and_rolling(program_dir, ingestion_program_dir)
                    if self.combined_scores is not None:
                        scores_path = os.path.join(self.output_dir, "scores.json")
                        with open(scores_path, "w") as scores_file:
                            json.dump(self.combined_scores, scores_file, indent=2)
                        logger.info("Wrote combined scores.json: %s", scores_path)
                else:
                    logger.info("Running static scoring pipeline")
                    self.logs = {}
                    self.completed_program_counter = 0
                    self.watch = True
                    if self._has_static_split_config():
                        round_input_dir, round_ref_dir, split_meta = self._prepare_static_split_data()
                        logger.info(
                            "Running static scoring with configured split: column=%s split_value=%s",
                            split_meta["split_column"],
                            split_meta["split_value"],
                        )
                        logger.info(
                            "Static split rows: train=%s test=%s",
                            split_meta["train_rows"],
                            split_meta["test_rows"],
                        )
                        self._log_round_input_tree(
                            round_input_dir, f"static-{split_meta['split_value']}"
                        )
                        self._run_programs_sequential(
                            program_dir,
                            ingestion_program_dir,
                            input_data_dir=round_input_dir,
                            input_ref_dir=round_ref_dir,
                        )
                    else:
                        logger.info(
                            "Static split config not set; using legacy static scoring pipeline."
                        )
                        # Keep rolling behavior unchanged; only static scoring runs sequentially
                        # so ingestion can materialize predictions before scoring consumes input/res.
                        self._run_programs_sequential(program_dir, ingestion_program_dir)
            else:
                logger.info("Running scoring program, and then ingestion program")
                self.logs = {}
                self.completed_program_counter = 0
                self.watch = True
                self._run_programs_once(program_dir, ingestion_program_dir)
        except ExecutionTimeLimitExceeded:
            error_message = f"Execution Time Limit exceeded. Limit was {self.execution_time_limit} seconds"
            logger.error(error_message)
            # Prepare data to be sent to submissions api
            execution_time_limit_exceeded_data = {
                "type": "Execution_Time_Limit_Exceeded",
                "error_message": error_message,
                "is_scoring": self.is_scoring,
            }
            # Some cleanup
            for kind, logs in self.logs.items():
                containers_to_kill = []
                containers_to_kill.append(self.ingestion_container_name)
                containers_to_kill.append(self.program_container_name)
                logger.debug(
                    "Trying to kill and remove container " + str(containers_to_kill)
                )
                for container in containers_to_kill:
                    try:
                        client.remove_container(str(container), force=True)
                    except docker.errors.APIError as e:
                        logger.error(e)
                    except Exception as e:
                        logger.error(
                            "There was a problem killing " + str(containers_to_kill) + e
                        )
                        if os.environ.get("LOG_LEVEL", "info").lower() == "debug":
                            logger.exception(e)
            # Send data to be written to ingestion/scoring std_err
            self._update_submission(execution_time_limit_exceeded_data)
            # Send error through web socket to the frontend
            asyncio.run(self._send_data_through_socket(error_message))
            raise SubmissionException(error_message)
        finally:
            if not self.is_scoring:
                self._finalize_run_logs()
        signal.alarm(0)

        if self.is_scoring:
            self._update_status(STATUS_FINISHED)
        else:
            self._update_status(STATUS_SCORING)

    def push_scores(self):
        """This is only ran at the end of the scoring step"""
        # POST to some endpoint:
        # {
        #     "correct": 1.0
        # }
        if os.path.exists(os.path.join(self.output_dir, "scores.json")):
            scores_file = os.path.join(self.output_dir, "scores.json")
            with open(scores_file) as f:
                try:
                    scores = json.load(f)
                except json.decoder.JSONDecodeError as e:
                    raise SubmissionException(
                        f"Could not decode scores json properly, it contains an error.\n{e.msg}"
                    )

        elif os.path.exists(os.path.join(self.output_dir, "scores.txt")):
            scores_file = os.path.join(self.output_dir, "scores.txt")
            with open(scores_file) as f:
                scores = yaml.load(f, yaml.Loader)
        else:
            raise SubmissionException(
                "Could not find scores file, did the scoring program output it?"
            )

        # Replace float NaN/Inf with None so the payload is valid JSON.
        # NaN arises when scoring fails (e.g. ingestion timeout) and the
        # scoring program writes placeholder scores; None serialises as null.
        def _sanitise(obj):
            if isinstance(obj, dict):
                return {k: _sanitise(v) for k, v in obj.items()}
            if isinstance(obj, float) and (obj != obj or obj == float("inf") or obj == float("-inf")):
                return None
            return obj

        scores = _sanitise(scores)

        url = (
            f"{self.submissions_api_url}/upload_submission_scores/{self.submission_id}/"
        )
        data = {
            "secret": self.secret,
            "scores": scores,
        }
        logger.info(f"Submitting these scores to {url}: {scores} with data = {data}")
        resp = self.requests_session.post(url, json=data)
        logger.info(resp)
        logger.info(str(resp.content))

    def push_output(self):
        """Output is pushed at the end of both prediction and scoring steps."""
        # V1.5 compatibility, write program statuses to metadata file
        prog_status = {
            "exitCode": self.program_exit_code,
            # for v1.5 compat, send `ingestion_elapsed_time` if no `program_elapsed_time`
            "elapsedTime": self.program_elapsed_time or self.ingestion_elapsed_time,
            "ingestionExitCode": self.ingestion_program_exit_code,
            "ingestionElapsedTime": self.ingestion_elapsed_time,
            "jobId": self.submission_id,
            "competitionId": self.competition_id,
            "trainingMode": self.training_mode,
        }
        if self.rolling_enabled:
            prog_status["rollingWindowSize"] = self.rolling_window_size
            prog_status["rollingStartYear"] = self.rolling_start_year
            prog_status["rollingEndYear"] = self.rolling_end_year
            prog_status["rollingStartPeriod"] = self.rolling_start_period
            prog_status["rollingEndPeriod"] = self.rolling_end_period
            prog_status["periodCol"] = self.rolling_period_col
            prog_status["periodSortStrategy"] = self.period_sort_strategy
        elif self._has_static_split_config():
            prog_status["staticSplitColumn"] = self.static_split_column
            prog_status["staticSplitValue"] = self.static_split_value

        logger.info(f"Metadata output: {prog_status}")

        metadata_path = os.path.join(self.output_dir, "metadata")

        if os.path.exists(metadata_path):
            raise SubmissionException(
                "Error, the output directory already contains a metadata file. This file is used "
                "to store exitCode and other data, do not write to this file manually."
            )

        with open(metadata_path, "w") as f:
            f.write(yaml.dump(prog_status, default_flow_style=False))

        if not self.is_scoring:
            self._put_dir(self.prediction_result, self.output_dir)
        else:
            self._put_dir(self.scoring_result, self.output_dir)

    def clean_up(self):
        if os.environ.get("CODALAB_IGNORE_CLEANUP_STEP"):
            logger.warning(
                f"CODALAB_IGNORE_CLEANUP_STEP mode enabled, ignoring clean up of: {self.root_dir}"
            )
            return

        logger.info(f"Destroying submission temp dir: {self.root_dir}")
        shutil.rmtree(self.root_dir)
