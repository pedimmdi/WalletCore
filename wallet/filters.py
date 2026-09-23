import django_filters

from .models import Transaction


class TransactionFilter(django_filters.FilterSet):
    type = django_filters.ChoiceFilter(
        choices=Transaction.TransactionType.choices
    )

    status = django_filters.ChoiceFilter(
        choices=Transaction.TransactionStatus.choices
    )

    class Meta:
        model = Transaction
        fields = ["type", "status"]