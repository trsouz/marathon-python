import errno
from functools import wraps
import os
import signal
import sys
import re
import time

import requests
from compose.cli import command


class TimeoutError(Exception):
    pass


def timeout(seconds=10, error_message=os.strerror(errno.ETIME)):
    def decorator(func):
        def _handle_timeout(signum, frame):
            raise TimeoutError(error_message)

        def wrapper(*args, **kwargs):
            signal.signal(signal.SIGALRM, _handle_timeout)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
            return result

        return wraps(func)(wrapper)

    return decorator


@timeout(30)
def wait_for_marathon():
    """Blocks until marathon is up"""
    marathon_service = get_marathon_connection_string()
    while True:
        print 'Connecting to marathon on %s' % marathon_service
        try:
            response = requests.get(
                'http://%s/ping' % marathon_service, timeout=2)
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ):
            time.sleep(2)
            continue
        if response.status_code == 200:
            print "Marathon is up and running!"
            break


def get_compose_service(service_name):
    """Returns a compose object for the service"""
    cmd = command.Command()
    project = cmd.get_project(cmd.get_config_path())
    return project.get_service(service_name)


def get_marathon_connection_string():
    # only reliable way I can detect travis..
    if '/travis/' in os.environ.get('PATH'):
        return 'localhost:8080'
    else:
        service_port = get_service_internal_port('marathon')
        local_port = get_compose_service('marathon').get_container().get_local_port(service_port)

        # Check if we're at OSX. Use ip from DOCKER_HOST
        if sys.platform == 'darwin':
            m = re.match("(.*?)://(.*?):(\d+)", os.environ["DOCKER_HOST"])
            local_port = "{}:{}".format(m.group(2), local_port.split(":")[1])

        return local_port


def get_service_internal_port(service_name):
    """Gets the exposed port for service_name from docker-compose.yml. If there are
    multiple ports. It returns the first one."""
    return get_compose_service(service_name).options['ports'][0]
