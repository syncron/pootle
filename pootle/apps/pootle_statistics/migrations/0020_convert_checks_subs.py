# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-03-02 12:44
from __future__ import unicode_literals

from django.db import migrations


MUTE_FLAG = 6
UNMUTE_FLAG = 7

MUTED = 0
UNMUTED = 1

CHECK_FIELD_FLAG = 5
WEB_FLAG = 1


def convert_check_subs(apps, schema_editor):
    subs = apps.get_model("pootle_statistics.Submission").objects
    subs.filter(type=MUTE_FLAG).update(
        field=CHECK_FIELD_FLAG,
        type=WEB_FLAG,
        old_value=UNMUTED,
        new_value=MUTED)
    subs.filter(type=UNMUTE_FLAG).update(
        field=CHECK_FIELD_FLAG,
        type=WEB_FLAG,
        old_value=MUTED,
        new_value=UNMUTED)


class Migration(migrations.Migration):

    dependencies = [
        ('pootle_statistics', '0019_convert_accept_sugg_subs'),
    ]

    operations = [
        migrations.RunPython(convert_check_subs),
    ]