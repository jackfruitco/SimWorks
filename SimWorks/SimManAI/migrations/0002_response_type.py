# Generated by Django 5.2 on 2025-04-19 03:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('SimManAI', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='response',
            name='type',
            field=models.CharField(choices=[('I', 'initial'), ('R', 'reply'), ('F', 'feedback')], default='R', max_length=2),
        ),
    ]
