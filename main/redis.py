# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging

from django.conf import settings
from django_redis import get_redis_connection


logger = logging.getLogger(__name__)


class LatestViewedStudies(object):
    """ Interfaces with Redis to keep a list of latest viewed studies """

    def __init__(self, user, n=5, *args, **kwargs):
        super(LatestViewedStudies, self).__init__(*args, **kwargs)
        self._end = n - 1
        self._redis = get_redis_connection(settings.EDD_LATEST_CACHE)
        self._user = user

    def __iter__(self):
        return iter(self._redis.lrange(self._key(), 0, self._end))

    def _key(self):
        return '%(module)s.%(klass)s:%(user)s' % {
            'module': __name__,
            'klass': self.__class__.__name__,
            'user': self._user.username,
        }

    def viewed_study(self, study):
        key = self._key()
        if study:
            # Don't want to put duplicates in the list
            self._redis.lrem(key, 0, study.pk)
            # Push study pk to front of list
            self._redis.lpush(key, study.pk)
            # Trim list to size
            self._redis.ltrim(key, 0, self._end)