# coding: utf-8
from __future__ import absolute_import, unicode_literals

"""
Factory classes used to generate objects under test.
"""

import factory

from .. import models


class StudyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Study
    name = factory.Faker('catch_phrase')
    description = factory.Faker('text', max_nb_chars=300)


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.User
    username = factory.Sequence(lambda n: 'user%03d' % n)  # username is unique