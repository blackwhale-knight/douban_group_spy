# Generated by Django 2.2.28 on 2023-10-11 15:34

from django.db import migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('douban_group_spy', '0009_auto_20231011_2021'),
    ]

    operations = [
        migrations.AddField(
            model_name='doulistpost',
            name='comment_photo_list',
            field=jsonfield.fields.JSONField(default=[]),
        ),
    ]