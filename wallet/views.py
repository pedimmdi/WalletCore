from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from django_filters.rest_framework import DjangoFilterBackend

from .filters import TransactionFilter
from .models import Account, Transaction, Wallet
from .exceptions import (
    InsufficientFunds,
    InactiveWallet,
    InvalidAmount,
    InvalidIdempotencyKey,
)
from .permissions import IsStaff
from .serializers import (
    WalletSerializer,
    TransactionListSerializer,
    AdminWalletSerializer,
    DepositRequestSerializer,
    WithdrawRequestSerializer,
    TransferRequestSerializer,
    TransactionResponseSerializer,
)
from .services import (
    deposit_idempotent,
    get_or_create_user_wallet,
    transfer_idempotent,
    withdraw_idempotent,
)
from .pagination import StandardResultsSetPagination
from .cache import get_wallet_cache, set_wallet_cache


User = get_user_model()

IDEMPOTENCY_KEY_PARAMETER = OpenApiParameter(
    name="Idempotency-Key",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.HEADER,
    required=True,
    description=(
        "Unique key that makes this request safely retryable. "
        "Reusing the same key with different request data returns an error."
    ),
)


class WalletView(APIView):
    """Return the authenticated user's wallet balance (cached for a short TTL)."""
    
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cached_data = get_wallet_cache(request.user.id)

        if cached_data is not None:
            return Response(cached_data, status=status.HTTP_200_OK)

        wallet, _ = Wallet.objects.get_or_create(
            user=request.user,
            defaults={
                "account": Account.objects.create(
                    name=f"Wallet Account - {request.user.username}",
                    account_type=Account.AccountType.USER,
                ),
            },
        )

        serializer = WalletSerializer(wallet)

        set_wallet_cache(request.user.id, serializer.data)

        return Response(serializer.data, status=status.HTTP_200_OK)


class DepositView(APIView):
    """Deposit an amount into the authenticated user's wallet."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
            request=DepositRequestSerializer,
            parameters=[IDEMPOTENCY_KEY_PARAMETER],
            responses={201: TransactionResponseSerializer},
        )
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


class WithdrawView(APIView):
    """Withdraw an amount from the authenticated user's wallet."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
            request=WithdrawRequestSerializer,
            parameters=[IDEMPOTENCY_KEY_PARAMETER],
            responses={201: TransactionResponseSerializer},
        )
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
    """Transfer an amount from the authenticated user to another user."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=TransferRequestSerializer,
        parameters=[IDEMPOTENCY_KEY_PARAMETER],
        responses={201: TransactionResponseSerializer},
    )
    def post(self, request):
        idempotency_key = request.headers.get("Idempotency-Key")

        if not idempotency_key:
            return Response(
                {
                    "detail": "Idempotency-Key header is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

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

            response_body, response_status = transfer_idempotent(
                from_user=request.user,
                to_user=to_user,
                amount=amount,
                idempotency_key=idempotency_key,
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


class TransactionListView(ListAPIView):
    """List the authenticated user's transactions, filterable by type and status."""

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


class AdminWalletListView(ListAPIView):
    """List all wallets. Staff only."""

    serializer_class = AdminWalletSerializer
    permission_classes = [IsAuthenticated, IsStaff]

    def get_queryset(self):
        return (
            Wallet.objects
            .select_related("user", "account")
            .order_by("-created_at")
        )


class AdminWalletFreezeView(APIView):
    """Freeze a wallet so it can no longer deposit, withdraw, or send transfers. Staff only."""

    permission_classes = [IsAuthenticated, IsStaff]

    @extend_schema(responses={200: AdminWalletSerializer})
    def post(self, request, pk):
        try:
            wallet = (
                Wallet.objects
                .select_related("user", "account")
                .get(pk=pk)
            )
        except Wallet.DoesNotExist:
            return Response(
                {"detail": "Wallet not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        wallet.is_active = False
        wallet.save(update_fields=["is_active", "updated_at"])

        serializer = AdminWalletSerializer(wallet)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )
