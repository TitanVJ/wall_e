# Generated by Django 3.2.14 on 2022-07-15 22:32

import WalleModels.customFields
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('WalleModels', '0004_auto_20220206_1142'),
    ]

    operations = [
        migrations.AlterField(
            model_name='banrecords',
            name='ban_id',
            field=WalleModels.customFields.GeneratedIdentityField(primary_key=True, serialize=False),
        ),
    ]