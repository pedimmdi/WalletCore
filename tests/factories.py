import factory
from decimal import Decimal
from django.contrib.auth import get_user_model
from wallet.models import Account, Wallet

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("username",)
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "testpass123")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")


class AccountFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Account

    name = factory.Sequence(lambda n: f"Account {n}")
    account_type = Account.AccountType.USER
    is_active = True


class SystemAccountFactory(AccountFactory):
    class Meta:
        model = Account
        django_get_or_create = ("account_type",)

    account_type = Account.AccountType.SYSTEM
    name = "System Account"


class WalletFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Wallet

    user = factory.SubFactory(UserFactory)
    account = factory.SubFactory(AccountFactory)
    balance = Decimal("0.00")
    is_active = True
