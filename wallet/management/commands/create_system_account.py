from django.core.management.base import BaseCommand
from wallet.models import Account


class Command(BaseCommand):
    def handle(self, *args, **options):
        account, created = Account.objects.get_or_create(
            account_type = Account.AccountType.SYSTEM,
            defaults={
                "name": "System Account",
            }
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    'System account created successfully'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    'System account already exists'
                )
            )
