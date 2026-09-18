from django.db import migrations


def create_system_account(apps, schema_editor):
    Account = apps.get_model("wallet", "Account")

    Account.objects.get_or_create(
        account_type="system",
        defaults={
            "name": "System Account",
            "is_active": True,
        },
    )


def remove_system_account(apps, schema_editor):
    Account = apps.get_model("wallet", "Account")

    Account.objects.filter(
        account_type="system"
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("wallet", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            create_system_account,
            remove_system_account,
        ),
    ]
