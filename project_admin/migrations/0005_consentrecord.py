# Generated by Django 2.1.2 on 2019-05-21 22:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('project_admin', '0004_auto_20180228_0616'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConsentRecord',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('project_member_id', models.CharField(max_length=20)),
            ],
        ),
    ]