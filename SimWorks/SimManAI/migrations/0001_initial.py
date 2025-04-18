# Generated by Django 5.2 on 2025-04-19 17:49

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Prompt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('modified_at', models.DateTimeField(auto_now=True)),
                ('fingerprint', models.CharField(db_index=True, editable=False, max_length=64, unique=True)),
                ('is_archived', models.BooleanField(default=False)),
                ('title', models.CharField(max_length=255, unique=True)),
                ('text', models.TextField(help_text='The scenario prompt sent to OpenAI.')),
                ('summary', models.TextField(help_text='The prompt summary.')),
            ],
        ),
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
    ]
