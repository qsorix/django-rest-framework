"""
Handled exceptions raised by REST framework.

In addition Django's built in 403 and 404 exceptions are handled.
(`django.http.Http404` and `django.core.exceptions.PermissionDenied`)
"""
from __future__ import unicode_literals

import math

from django.utils import six
from django.utils.encoding import force_text
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ungettext

from rest_framework import status
from rest_framework.settings import api_settings


def _force_text_recursive(data):
    """
    Descend into a nested data structure, forcing any
    lazy translation strings into plain text.
    """
    if isinstance(data, list):
        return [
            _force_text_recursive(item) for item in data
        ]
    elif isinstance(data, tuple):
        return tuple([
            _force_text_recursive(item) for item in data
        ])
    elif isinstance(data, dict):
        return dict([
            (key, _force_text_recursive(value))
            for key, value in data.items()
        ])
    return force_text(data)


class APIException(Exception):
    """
    Base class for REST framework exceptions.
    Subclasses should provide `.status_code` and `.default_detail` properties.
    """
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = _('A server error occurred.')

    def __init__(self, detail=None):
        if detail is not None:
            self.detail = force_text(detail)
        else:
            self.detail = force_text(self.default_detail)

    def __str__(self):
        return self.detail


def build_error_from_django_validation_error(exc_info):
    code = exc_info.code or 'invalid'
    return [
        build_error(msg, error_code=code) for msg in exc_info.messages
    ]


def build_error(detail, error_code=None):
    assert not isinstance(detail, dict) and not isinstance(detail, list), (
        'Use `build_error` only with single error messages. Dictionaries and '
        'lists should be passed directly to ValidationError.'
    )

    if api_settings.REQUIRE_ERROR_CODES:
        assert error_code is not None, (
            'The `error_code` argument is required for single errors. Strict '
            'checking of error_code is enabled with REQUIRE_ERROR_CODES '
            'settings key.'
        )

    return api_settings.ERROR_BUILDER(detail, error_code)


def default_error_builder(detail, error_code=None):
    return (detail, error_code)


# The recommended style for using `ValidationError` is to keep it namespaced
# under `serializers`, in order to minimize potential confusion with Django's
# built in `ValidationError`. For example:
#
# from rest_framework import serializers
# raise serializers.ValidationError('Value was invalid')

class ValidationError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, detail, error_code=None):
        # For validation errors the 'detail' key is always required.
        # The details should always be coerced to a list if not already.
        if not isinstance(detail, dict) and not isinstance(detail, list):
            detail = [build_error(detail, error_code=error_code)]
        else:
            if api_settings.REQUIRE_ERROR_CODES:
                assert error_code is None, (
                    'The `error_code` argument must not be set for compound '
                    'errors. Strict checking of error_code is enabled with '
                    'REQUIRE_ERROR_CODES settings key.'
                )

        self.detail = _force_text_recursive(detail)
        self.error_code = error_code

    def __str__(self):
        return six.text_type(self.detail)


class ParseError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('Malformed request.')


class AuthenticationFailed(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = _('Incorrect authentication credentials.')


class NotAuthenticated(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = _('Authentication credentials were not provided.')


class PermissionDenied(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('You do not have permission to perform this action.')


class NotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _('Not found.')


class MethodNotAllowed(APIException):
    status_code = status.HTTP_405_METHOD_NOT_ALLOWED
    default_detail = _('Method "{method}" not allowed.')

    def __init__(self, method, detail=None):
        if detail is not None:
            self.detail = force_text(detail)
        else:
            self.detail = force_text(self.default_detail).format(method=method)


class NotAcceptable(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    default_detail = _('Could not satisfy the request Accept header.')

    def __init__(self, detail=None, available_renderers=None):
        if detail is not None:
            self.detail = force_text(detail)
        else:
            self.detail = force_text(self.default_detail)
        self.available_renderers = available_renderers


class UnsupportedMediaType(APIException):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    default_detail = _('Unsupported media type "{media_type}" in request.')

    def __init__(self, media_type, detail=None):
        if detail is not None:
            self.detail = force_text(detail)
        else:
            self.detail = force_text(self.default_detail).format(
                media_type=media_type
            )


class Throttled(APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = _('Request was throttled.')
    extra_detail_singular = 'Expected available in {wait} second.'
    extra_detail_plural = 'Expected available in {wait} seconds.'

    def __init__(self, wait=None, detail=None):
        if detail is not None:
            self.detail = force_text(detail)
        else:
            self.detail = force_text(self.default_detail)

        if wait is None:
            self.wait = None
        else:
            self.wait = math.ceil(wait)
            self.detail += ' ' + force_text(ungettext(
                self.extra_detail_singular.format(wait=self.wait),
                self.extra_detail_plural.format(wait=self.wait),
                self.wait
            ))
