# Generated by Django 5.2 on 2025-04-06 23:27
import django.db.models.deletion
import MedLab.models
from django.conf import settings
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("MedLab", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="sender",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.AddField(
            model_name="prompt",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_prompts",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="prompt",
            name="modified_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="modified_prompts",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="simulation",
            name="prompt",
            field=models.ForeignKey(
                blank=True,
                default=MedLab.models.get_default_prompt,
                help_text="The prompt to use as AI instructions.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="MedLab.prompt",
            ),
        ),
        migrations.AddField(
            model_name="simulation",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.AddField(
            model_name="message",
            name="simulation",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="MedLab.simulation"
            ),
        ),
        migrations.AddField(
            model_name="simulationmetafield",
            name="simulation",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="metadata",
                to="MedLab.simulation",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="message",
            unique_together={("simulation", "order")},
        ),
    ]
