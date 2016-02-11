# -*- coding: utf-8 -*-
# Generated by Django 1.9 on 2016-02-11 00:53
from __future__ import unicode_literals

import django.contrib.postgres.fields.hstore
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0010_fix-metabolite-names'),
    ]

    operations = [
        migrations.AddField(
            model_name='measurement',
            name='meta_store',
            field=django.contrib.postgres.fields.hstore.HStoreField(blank=True, default=dict),
        ),
    ]
