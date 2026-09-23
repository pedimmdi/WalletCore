from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from django_filters.rest_framework import DjangoFilterBackend

from .filters import TransactionFilter
from .models import Transaction
from .exceptions import (
    InsufficientFunds,
    InactiveWallet,
    InvalidAmount,
    InvalidIdempotencyKey,
)
from .serializers import WalletSerializer, TransactionListSerializer
from .services import (
    deposit_idempotent,
    get_or_create_user_wallet,
    transfer,
    withdraw_idempotent,
)
from .pagination import StandardResultsSetPagination


User = get_user_model()


class WalletView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        wallet = get_or_create_user_wallet(request.user)
        serializer = WalletSerializer(wallet)
        return Response(serializer.data)


class DepositView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        idempotency_key = request.headers.get("Idempotency-Key")

        if not idempotency_key:
            return Response(
                {
                    "detail": "Idempotency-Key header is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_amount = request.data.get("amount")

        if raw_amount is None:
            return Response(
                {
                    "detail": "Amount is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            amount = Decimal(str(raw_amount))
        except (InvalidOperation, ValueError):
            return Response(
                {
                    "detail": "Invalid amount."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            response_body, response_status = deposit_idempotent(
                user=request.user,
                amount=amount,
                idempotency_key=idempotency_key,
            )

        except ValidationError as exc:
            return Response(
                {
                    "detail": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            response_body,
            status=response_status,
        )


class WithdrawView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        idempotency_key = request.headers.get(
            "Idempotency-Key"
        )

        if not idempotency_key:
            return Response(
                {
                    "detail": "Idempotency-Key header is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_amount = request.data.get("amount")

        if raw_amount is None:
            return Response(
                {
                    "detail": "Amount is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            amount = Decimal(str(raw_amount))
        except (InvalidOperation, ValueError):
            return Response(
                {
                    "detail": "Invalid amount."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            response_body, response_status = withdraw_idempotent(
                user=request.user,
                amount=amount,
                idempotency_key=idempotency_key,
            )

        except (
            InsufficientFunds,
            InactiveWallet,
            InvalidAmount,
            InvalidIdempotencyKey,
            ValidationError,
        ) as exc:
            return Response(
                {
                    "detail": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            response_body,
            status=response_status,
        )


class TransferView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        raw_to_user_id = request.data.get("to_user_id")
        raw_amount = request.data.get("amount")

        if raw_to_user_id is None:
            return Response(
                {
                    "detail": "to_user_id is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if raw_amount is None:
            return Response(
                {
                    "detail": "Amount is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            to_user_id = int(raw_to_user_id)
        except (TypeError, ValueError):
            return Response(
                {
                    "detail": "Invalid to_user_id."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            amount = Decimal(str(raw_amount))
        except (InvalidOperation, ValueError):
            return Response(
                {
                    "detail": "Invalid amount."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            to_user = User.objects.get(pk=to_user_id)

            tx = transfer(
                from_user=request.user,
                to_user=to_user,
                amount=amount,
            )

        except User.DoesNotExist:
            return Response(
                {
                    "detail": "Receiver user does not exist."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except (
            InsufficientFunds,
            InactiveWallet,
            InvalidAmount,
            ValidationError,
        ) as exc:
            return Response(
                {
                    "detail": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "id": str(tx.id),
                "type": tx.type,
                "status": tx.status,
                "amount": str(tx.amount),
            },
            status=status.HTTP_201_CREATED,
        )


class TransactionListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TransactionListSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = TransactionFilter
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return (
            Transaction.objects
            .filter(initiated_by=self.request.user)
            .order_by("-created_at")
        )
