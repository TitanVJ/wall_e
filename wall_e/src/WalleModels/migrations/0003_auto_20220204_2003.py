# Generated by Django 3.2.7 on 2022-02-05 04:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('WalleModels', '0002_auto_20220203_2111'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commandstat',
            name='day',
            field=models.IntegerField(default=4),
        ),
        migrations.AlterField(
            model_name='commandstat',
            name='hour',
            field=models.IntegerField(default=20),
        ),
        migrations.AlterField(
            model_name='level',
            name='number',
            field=models.PositiveBigIntegerField(unique=True),
        ),
        migrations.AlterField(
            model_name='level',
            name='role_id',
            field=models.PositiveBigIntegerField(null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='level',
            name='role_name',
            field=models.CharField(max_length=500, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='userpoint',
            name='user_id',
            field=models.PositiveBigIntegerField(unique=True),
        ),
    ]
