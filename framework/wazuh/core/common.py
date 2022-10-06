# Copyright (C) 2015, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is free software; you can redistribute it and/or modify it under the terms of GPLv2
import json
import os
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from contextvars import ContextVar
from copy import deepcopy
from functools import lru_cache, wraps
from grp import getgrnam
from multiprocessing import Event
from pwd import getpwnam
from typing import Any, Dict


# ===================================================== Functions ======================================================
@lru_cache(maxsize=None)
def find_wazuh_path() -> str:
    """
    Get the Wazuh installation path.

    Returns
    -------
    str
        Path where Wazuh is installed or empty string if there is no framework in the environment.
    """
    abs_path = os.path.abspath(os.path.dirname(__file__))
    allparts = []
    while 1:
        parts = os.path.split(abs_path)
        if parts[0] == abs_path:  # sentinel for absolute paths.
            allparts.insert(0, parts[0])
            break
        elif parts[1] == abs_path:  # sentinel for relative paths.
            allparts.insert(0, parts[1])
            break
        else:
            abs_path = parts[0]
            allparts.insert(0, parts[1])

    wazuh_path = ''
    try:
        for i in range(0, allparts.index('framework')):
            wazuh_path = os.path.join(wazuh_path, allparts[i])
    except ValueError:
        pass

    return wazuh_path


def wazuh_uid():
    """Retrieve the numerical user ID for the wazuh user.

    Returns
    -------
    int
        Numerical user ID.
    """
    return getpwnam(USER_NAME).pw_uid if globals()['_WAZUH_UID'] is None else globals()['_WAZUH_UID']


def wazuh_gid():
    """Retrieve the numerical group ID for the wazuh group.

    Returns
    -------
    int
        Numerical group ID.
    """
    return getgrnam(GROUP_NAME).gr_gid if globals()['_WAZUH_GID'] is None else globals()['_WAZUH_GID']


def context_cached(key: str = '') -> Any:
    """Save the result of the decorated function in a cache.

    Next calls to the decorated function returns the saved result saving time and resources. The cache gets
    invalidated at the end of the request.

    Parameters
    ----------
    key : str
        Part of the cache entry identifier. The identifier will be the key + args + kwargs.

    Returns
    -------
    Any
        The result of the first call to the decorated function.

    Notes
    -----
    The returned object will be a deep copy of the cached one.
    """

    def decorator(func) -> Any:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            cached_key = json.dumps({'key': key, 'args': args, 'kwargs': kwargs})
            if cached_key not in _context_cache:
                _context_cache[cached_key] = ContextVar(cached_key, default=None)
            if _context_cache[cached_key].get() is None:
                result = func(*args, **kwargs)
                _context_cache[cached_key].set(result)
            return deepcopy(_context_cache[cached_key].get())

        return wrapper

    return decorator


def reset_context_cache() -> None:
    """Reset context cache."""

    for context_var in _context_cache.values():
        context_var.set(None)


def get_context_cache() -> dict:
    """Get the context cache.

    Returns
    -------
    dict
        Dictionary with the context variables representing the cache.
    """

    return _context_cache


# ================================================= Context variables ==================================================
rbac: ContextVar[Dict] = ContextVar('rbac', default={'rbac_mode': 'black'})
current_user: ContextVar[str] = ContextVar('current_user', default='')
broadcast: ContextVar[bool] = ContextVar('broadcast', default=False)
cluster_nodes: ContextVar[list] = ContextVar('cluster_nodes', default=list())
origin_module: ContextVar[str] = ContextVar('origin_module', default='framework')
try:
    mp_pools: ContextVar[Dict] = ContextVar('mp_pools', default={
        'process_pool': ProcessPoolExecutor(max_workers=1),
        'authentication_pool': ProcessPoolExecutor(max_workers=1)
    })
# Handle exception when the user running Wazuh cannot access /dev/shm.
except (FileNotFoundError, PermissionError):
    mp_pools: ContextVar[Dict] = ContextVar('mp_pools', default={
        'thread_pool': ThreadPoolExecutor(max_workers=1)
    })
_context_cache = dict()


# =========================================== Wazuh constants and variables ============================================
# Clear cache event.
cache_event = Event()
_WAZUH_UID = None
_WAZUH_GID = None
GROUP_NAME = 'wazuh'
USER_NAME = 'wazuh'
WAZUH_PATH = find_wazuh_path()


# ============================================= Wazuh constants - Commands =============================================
CHECK_CONFIG_COMMAND = 'check-manager-configuration'
RESTART_WAZUH_COMMAND = 'restart-wazuh'


# =========================================== Wazuh constants - Date format ============================================
DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
DECIMALS_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


# ============================================ Wazuh constants - Extensions ============================================
RULES_EXTENSION = '.xml'
DECODERS_EXTENSION = '.xml'
LISTS_EXTENSION = ''
COMPILED_LISTS_EXTENSION = '.cdb'


# ============================================ Wazuh constants - Metadata  =============================================
try:
    here = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(here, 'wazuh.json'), 'r') as f:
        metadata = json.load(f)
except (FileNotFoundError, PermissionError):
    metadata = {
        'install_type': 'server',
        'installation_date': '',
        'wazuh_version': ''
    }
WAZUH_INSTALL_TYPE = metadata['install_type']
WAZUH_VERSION = metadata['wazuh_version']
WAZUH_INSTALLATION_DATE = metadata['installation_date']


# ========================================= Wazuh constants - Size and limits ==========================================
MAX_SOCKET_BUFFER_SIZE = 64 * 1024  # 64KB.
MAX_QUERY_FILTERS_RESERVED_SIZE = MAX_SOCKET_BUFFER_SIZE - 4 * 1024  # MAX_BUFFER_SIZE - 4KB.
AGENT_NAME_LEN_LIMIT = 128
DATABASE_LIMIT = 500
MAXIMUM_DATABASE_LIMIT = 100000
MAX_GROUPS_PER_MULTIGROUP = 128


# ============================================= Wazuh constants - Version ==============================================
# Agent upgrading variables.
WPK_REPO_URL_4_X = "packages.wazuh.com/4.x/wpk/"
# Agent component stats required version.
AGENT_COMPONENT_STATS_REQUIRED_VERSION = {'logcollector': 'v4.2.0', 'agent': 'v4.2.0'}
# Version variables (legacy, required, etc).
AR_LEGACY_VERSION = 'Wazuh v4.2.0'
ACTIVE_CONFIG_VERSION = 'Wazuh v3.7.0'


# ================================================ Wazuh path - Config =================================================
OSSEC_CONF = os.path.join(WAZUH_PATH, 'etc', 'ossec.conf')
INTERNAL_OPTIONS_CONF = os.path.join(WAZUH_PATH, 'etc', 'internal_options.conf')
LOCAL_INTERNAL_OPTIONS_CONF = os.path.join(WAZUH_PATH, 'etc', 'local_internal_options.conf')
AR_CONF = os.path.join(WAZUH_PATH, 'etc', 'shared', 'ar.conf')
CLIENT_KEYS = os.path.join(WAZUH_PATH, 'etc', 'client.keys')
SHARED_PATH = os.path.join(WAZUH_PATH, 'etc', 'shared')


# ================================================= Wazuh path - Misc ==================================================
OSSEC_LOG = os.path.join(WAZUH_PATH, 'logs', 'ossec.log')
DATABASE_PATH = os.path.join(WAZUH_PATH, 'var', 'db')
DATABASE_PATH_GLOBAL = os.path.join(DATABASE_PATH, 'global.db')
DATABASE_PATH_AGENTS = os.path.join(DATABASE_PATH, 'agents')
ANALYSISD_STATS = os.path.join(WAZUH_PATH, 'var', 'run', 'wazuh-analysisd.state')
REMOTED_STATS = os.path.join(WAZUH_PATH, 'var', 'run', 'wazuh-remoted.state')
OSSEC_TMP_PATH = os.path.join(WAZUH_PATH, 'tmp')
OSSEC_PIDFILE_PATH = os.path.join(WAZUH_PATH, 'var', 'run')
OS_PIDFILE_PATH = os.path.join('var', 'run')
WDB_PATH = os.path.join(WAZUH_PATH, 'queue', 'db')
STATS_PATH = os.path.join(WAZUH_PATH, 'stats')
BACKUP_PATH = os.path.join(WAZUH_PATH, 'backup')
MULTI_GROUPS_PATH = os.path.join(WAZUH_PATH, 'var', 'multigroups')


# ================================================ Wazuh path - Sockets ================================================
AR_SOCKET = os.path.join(WAZUH_PATH, 'queue', 'alerts', 'ar')
EXECQ_SOCKET = os.path.join(WAZUH_PATH, 'queue', 'alerts', 'execq')
AUTHD_SOCKET = os.path.join(WAZUH_PATH, 'queue', 'sockets', 'auth')
WCOM_SOCKET = os.path.join(WAZUH_PATH, 'queue', 'sockets', 'com')
LOGTEST_SOCKET = os.path.join(WAZUH_PATH, 'queue', 'sockets', 'logtest')
UPGRADE_SOCKET = os.path.join(WAZUH_PATH, 'queue', 'tasks', 'upgrade')
TASKS_SOCKET = os.path.join(WAZUH_PATH, 'queue', 'tasks', 'task')
WDB_SOCKET = os.path.join(WAZUH_PATH, 'queue', 'db', 'wdb')


# ================================================ Wazuh path - Ruleset ================================================
RULESET_PATH = os.path.join(WAZUH_PATH, 'ruleset')
RULES_PATH = os.path.join(RULESET_PATH, 'rules')
DECODERS_PATH = os.path.join(RULESET_PATH, 'decoders')
LISTS_PATH = os.path.join(RULESET_PATH, 'lists')
USER_LISTS_PATH = os.path.join(WAZUH_PATH, 'etc', 'lists')
USER_RULES_PATH = os.path.join(WAZUH_PATH, 'etc', 'rules')
USER_DECODERS_PATH = os.path.join(WAZUH_PATH, 'etc', 'decoders')
