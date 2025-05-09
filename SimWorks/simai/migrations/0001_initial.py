# Generated by Django 5.2 on 2025-04-21 19:14

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Response',
            fields=[
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('raw', models.TextField(verbose_name='OpenAI Raw Response')),
                ('id', models.CharField(max_length=255, primary_key=True, serialize=False, verbose_name='OpenAI Response ID')),
                ('order', models.PositiveIntegerField(editable=False)),
                ('type', models.CharField(choices=[('I', 'initial'), ('R', 'reply'), ('F', 'feedback')], default='R', max_length=2)),
                ('input_tokens', models.PositiveIntegerField(default=0)),
                ('output_tokens', models.PositiveIntegerField(default=0)),
                ('reasoning_tokens', models.PositiveIntegerField(default=0)),
            ],
            options={
                'ordering': ('simulation', 'order'),
            },
        ),
        migrations.CreateModel(
            name='Prompt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('modified_at', models.DateTimeField(auto_now=True)),
                ('fingerprint', models.CharField(db_index=True, editable=False, max_length=64, unique=True)),
                ('is_archived', models.BooleanField(default=False)),
                ('title', models.CharField(max_length=255, unique=True)),
                ('content', models.TextField(help_text='The scenario prompt sent to OpenAI.')),
                ('summary', models.TextField(help_text='The prompt summary.')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_prompts', to=settings.AUTH_USER_MODEL)),
                ('modified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='modified_prompts', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
