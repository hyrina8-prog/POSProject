# api_helper.py
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# Pull from settings so it works in every environment
API_BASE_URL = getattr(settings, 'API_BASE_URL', 'http://127.0.0.1:8000')

# Sensible timeout: (connect_timeout, read_timeout)
REQUEST_TIMEOUT = (5, 15)


def api_call(method, endpoint, data=None, token=None):
    """
    A helper to call your own DRF API.

    Returns:
        requests.Response on success.
        None on connection / timeout errors (caller should handle it).
    """
    url = f"{API_BASE_URL}{endpoint}"

    headers = {}
    if token:
        headers['Authorization'] = f'Token {token}'

    try:
        if method == 'GET':
            return requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        elif method == 'POST':
            return requests.post(url, json=data, headers=headers, timeout=REQUEST_TIMEOUT)
        elif method == 'PATCH':
            return requests.patch(url, json=data, headers=headers, timeout=REQUEST_TIMEOUT)
        elif method == 'DELETE':
            return requests.delete(url, headers=headers, timeout=REQUEST_TIMEOUT)
        else:
            logger.error(f"Unsupported HTTP method: {method}")
            return None

    except requests.exceptions.ConnectionError:
        logger.error(f"API ConnectionError: Could not reach {url}")
        return None
    except requests.exceptions.Timeout:
        logger.error(f"API Timeout: {url} did not respond in time")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"API RequestException: {e}")
        return None