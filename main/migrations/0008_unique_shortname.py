# -*- coding: utf-8 -*-
# Generated by Django 1.9.13 on 2017-08-09 17:32
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0007_add-pubchem-cid'),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE UNIQUE INDEX measurementtype_shortname_typegroup_uniq_idx "
                "ON measurement_type (short_name, type_group) "
                "WHERE short_name IS NOT NULL AND short_name != '';",
            reverse_sql="DROP INDEX measurementtype_shortname_typegroup_uniq_idx;",
        ),
    ]
