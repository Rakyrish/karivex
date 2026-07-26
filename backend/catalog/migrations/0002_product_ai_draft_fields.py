from django.db import migrations, models


class Migration(migrations.Migration):
    """0001_initial's file content already declares these two Product fields
    (ai_draft, ai_draft_generated_at), but the live database was never
    actually migrated to add them — someone edited the already-applied
    0001_initial in place instead of adding a follow-up migration, so
    `makemigrations` sees no diff even though the real table is missing the
    columns. This migration reconciles the database with what the model (and
    0001_initial's file) already say should exist.
    """

    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="ai_draft",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="product",
            name="ai_draft_generated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
