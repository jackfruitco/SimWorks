# Generated by Django 5.2 on 2025-04-19 17:49

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('ChatLab', '0002_initial'),
        ('SimManAI', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='sender',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='simulation',
            name='prompt',
            field=models.ForeignKey(help_text='The prompt to use as AI instructions.', on_delete=django.db.models.deletion.RESTRICT, to='SimManAI.prompt'),
        ),
        migrations.AddField(
            model_name='simulation',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='message',
            name='simulation',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ChatLab.simulation'),
        ),
        migrations.AddField(
            model_name='simulationmetadata',
            name='simulation',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='metadata', to='ChatLab.simulation'),
        ),
        migrations.AlterUniqueTogether(
            name='message',
            unique_together={('simulation', 'order')},
        ),
    ]
