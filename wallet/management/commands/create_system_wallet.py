from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from wallet.models import Wallet


class Command(BaseCommand):
    def handle(self, *args, **options):
        User = get_user_model()

        user, created = User.objects.get_or_create(
            username='__system__',
            defaults={'is_active': False}
        )
        if created:
            user.set_unusable_password()
            user.save()
            self.stdout.write('System user created')
        else:
            self.stdout.write('It was already a system user')

        wallet, w_created = Wallet.objects.get_or_create(user=user)
        if w_created:
            self.stdout.write(f'System wallet was created: id={wallet.id}')
        else:
            self.stdout.write(f'The system wallet already existed: id={wallet.id}')
