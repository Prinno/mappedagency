# Generated manually for DailyCollectorSummary model

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_user_daily_target_user_national_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="DailyCollectorSummary",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("sent_at", models.DateTimeField(auto_now_add=True)),
                (
                    "collector",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="daily_summaries",
                        to=settings.AUTH_USER_MODEL,
                        limit_choices_to={"role": "data_collector"},
                    ),
                ),
            ],
            options={
                "ordering": ["-date", "-sent_at"],
                "unique_together": {("collector", "date")},
            },
        ),
    ]
