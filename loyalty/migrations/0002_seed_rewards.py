from django.db import migrations


def seed(apps, schema_editor):
    Reward = apps.get_model("loyalty", "Reward")
    items = [("🍧", "Sacolé", 50), ("🥟", "Empada", 100), ("🍰", "Fatia de bolo", 150)]
    for position, (emoji, name, cost) in enumerate(items, start=1):
        Reward.objects.get_or_create(
            name=name,
            defaults={"emoji": emoji, "points_cost": cost, "position": position, "active": True},
        )


class Migration(migrations.Migration):
    dependencies = [("loyalty", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
