# Generated by Django 3.2.7 on 2022-02-04 05:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('WalleModels', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Level',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.PositiveBigIntegerField()),
                ('total_points_required', models.PositiveBigIntegerField()),
                ('xp_needed_to_level_up_to_next_level', models.PositiveBigIntegerField()),
                ('role_id', models.PositiveBigIntegerField(null=True)),
                ('role_name', models.CharField(max_length=500, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='UserPoint',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user_id', models.PositiveBigIntegerField()),
                ('points', models.PositiveBigIntegerField()),
                ('level_up_specific_points', models.PositiveBigIntegerField()),
                ('message_count', models.PositiveBigIntegerField()),
                ('latest_time_xp_was_earned_epoch', models.BigIntegerField(default=0)),
                ('level_number', models.PositiveBigIntegerField()),
            ],
        ),
        migrations.AlterField(
            model_name='commandstat',
            name='day',
            field=models.IntegerField(default=3),
        ),
        migrations.AlterField(
            model_name='commandstat',
            name='hour',
            field=models.IntegerField(default=21),
        ),
        migrations.AlterField(
            model_name='commandstat',
            name='month',
            field=models.IntegerField(default=2),
        ),
        migrations.AlterField(
            model_name='commandstat',
            name='year',
            field=models.IntegerField(default=2022),
        ),
    ]
