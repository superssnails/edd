# -*- coding: utf-8 -*-
# Generated by Django 1.9.4 on 2016-09-07 17:20
from __future__ import unicode_literals

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0020_everyonepermission'),
    ]

    operations = [
        migrations.AddField(
            model_name='eddobject',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, unique=True),
        ),
        migrations.AddField(
            model_name='study',
            name='slug',
            field=models.SlugField(null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='measurement',
            name='compartment',
            field=models.CharField(choices=[('0', 'N/A'), ('1', 'Intracellular/Cytosol (Cy)'), ('2', 'Extracellular')], default=0', max_length=1),
        ),
        migrations.AlterField(
            model_name='measurement',
            name='measurement_format',
            field=models.CharField(choices=[('0', 'scalar'), ('1', 'vector'), ('2', 'histogram'), ('3', 'sigma')], default=0', max_length=2),
        ),
    ]
