import io
import yaml
import zipfile
from collections import defaultdict

from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import transaction
from django.db.models import Q, Value, BooleanField

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from api.pagination import BasicPagination
from api.serializers import tasks as serializers
from competitions.models import Phase
from datasets.models import Data
from profiles.models import User
from tasks.models import Task
from utils.data import pretty_bytes, gb_to_bytes


# NOTE:
# - We explicitly enable SessionAuthentication here so the web UI (cookie login)
#   can successfully call /api/tasks/ without returning 403.
# - TokenAuthentication is kept for API/token flows.
class TaskViewSet(ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = serializers.TaskSerializer

    authentication_classes = (SessionAuthentication, TokenAuthentication)
    permission_classes = (IsAuthenticated,)

    filter_fields = ("created_by", "is_public")
    filter_backends = (DjangoFilterBackend, SearchFilter)
    search_fields = ("name", "description")
    pagination_class = BasicPagination

    def get_queryset(self):
        qs = super().get_queryset()

        # For safety: if somehow unauthenticated slips through, return empty
        if not getattr(self.request, "user", None) or not self.request.user.is_authenticated:
            return qs.none()

        if self.request.method == "GET":
            qs = qs.select_related(
                "input_data",
                "reference_data",
                "ingestion_program",
                "scoring_program",
            ).prefetch_related(
                "solutions",
                "solutions__data",
            )

            task_filter = Q(created_by=self.request.user) | Q(shared_with=self.request.user)

            # If front-end passes ?public=true OR retrieving a specific task
            if self.request.query_params.get("public") or self.action == "retrieve":
                task_filter |= Q(is_public=True)

            qs = qs.filter(task_filter)

            # task validation removed upstream; keep annotated field for compatibility
            qs = qs.annotate(validated=Value(False, output_field=BooleanField()))

        return qs.order_by("-created_when").distinct()

    def get_serializer_class(self):
        if self.request.method == "GET":
            if self.action == "list":
                return serializers.TaskListSerializer
            return serializers.TaskDetailSerializer
        return serializers.TaskSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        qs = self.get_queryset()

        phases = Phase.objects.filter(tasks__pk__in=qs.values_list("pk", flat=True))
        context["task_titles"] = defaultdict(list)
        for task in phases.values("tasks__pk", "competition__title"):
            context["task_titles"][task["tasks__pk"]].append(task["competition__title"])

        users = User.objects.filter(shared_tasks__pk__in=qs.values_list("pk", flat=True))
        context["shared_with"] = defaultdict(list)
        for user in users.values("username", "shared_tasks__pk"):
            context["shared_with"][user["shared_tasks__pk"]].append(user["username"])

        return context

    def update(self, request, *args, **kwargs):
        task = self.get_object()

        # Only creator or superuser can update
        if request.user != task.created_by and not request.user.is_superuser:
            raise PermissionDenied("Cannot update a task that is not yours")

        # If only toggling is_public, just update normally
        if "is_public" in request.data:
            super().update(request, *args, **kwargs)
        else:
            # If keys not present, null them out (except scoring_program which is required)
            if "ingestion_program" not in request.data:
                task.ingestion_program = None
            if "input_data" not in request.data:
                task.input_data = None
            if "reference_data" not in request.data:
                task.reference_data = None

            task.save()
            super().update(request, *args, **kwargs)

        task.refresh_from_db()

        # Return full serializer (matches existing behavior)
        task_detail_serializer = serializers.TaskSerializer(task)
        return Response(task_detail_serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        error = self.check_delete_permissions(request, instance)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=("POST",))
    def delete_many(self, request):
        qs = Task.objects.filter(id__in=request.data)
        errors = {}

        for task in qs:
            error = self.check_delete_permissions(request, task)
            if error:
                errors[task.name] = error

        if not errors:
            qs.delete()

        return Response(
            errors if errors else {"detail": "Tasks deleted successfully"},
            status=status.HTTP_400_BAD_REQUEST if errors else status.HTTP_200_OK,
        )

    @action(detail=False, methods=("POST",))
    def upload_task(self, request):
        """
        Upload a task as a zip containing:
          - task.yaml (required)
          - ingestion_program.zip (optional)
          - scoring_program.zip (required in yaml)
          - input_data.zip (optional)
          - reference_data.zip (optional)

        task.yaml example:
            name: Task Name
            description: Task Description
            is_public: true/false
            input_data:
                key: <dataset key> OR zip: input_data.zip
            reference_data:
                key: <dataset key> OR zip: reference_data.zip
            scoring_program:
                key: <program key> OR zip: scoring_program.zip
            ingestion_program:
                key: <program key> OR zip: ingestion_program.zip
        """

        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response(
                {"error": "No attached file found, please try again!"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Quota check
        storage_used = float(request.user.get_used_storage_space())
        quota_gb = float(request.user.quota)
        quota_bytes = gb_to_bytes(quota_gb)

        file_size = uploaded_file.size
        if storage_used + file_size > quota_bytes:
            return Response(
                {
                    "error": "Insufficient space! Please free up some space and try again. "
                             "You can manage your files in the Resources page."
                },
                status=status.HTTP_507_INSUFFICIENT_STORAGE,
            )

        try:
            with zipfile.ZipFile(uploaded_file, "r") as zip_file:
                if "task.yaml" not in zip_file.namelist():
                    return Response(
                        {"error": "task.yaml not found in the zip file"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                with zip_file.open("task.yaml") as task_file:
                    try:
                        task_data = yaml.safe_load(task_file)
                    except yaml.YAMLError as e:
                        return Response(
                            {"error": f"Error parsing task.yaml: {str(e)}"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                # Required checks
                if "name" not in task_data:
                    return Response(
                        {"error": "Missing: name, task must have a name"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if "description" not in task_data:
                    return Response(
                        {"error": "Missing: description, task must have a description"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if Data.SCORING_PROGRAM not in task_data:
                    return Response(
                        {"error": "Missing: scoring_program, task must have a scoring_program"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                with transaction.atomic():
                    task_kwargs = {
                        "name": task_data.get("name"),
                        "description": task_data.get("description"),
                        "created_by": request.user,
                        "is_public": task_data.get("is_public", False),
                        "ingestion_only_during_scoring": task_data.get(
                            "ingestion_only_during_scoring", False
                        ),
                    }

                    def create_or_get_data(data_type, data_info):
                        # data_info can be {} or None
                        data_info = data_info or {}

                        key = data_info.get("key")
                        zip_name = data_info.get("zip")

                        if key:
                            try:
                                return Data.objects.get(
                                    key=key, created_by=request.user, type=data_type
                                )
                            except Data.DoesNotExist:
                                raise ValueError(f"{data_type} with key '{key}' not found.")

                        if zip_name:
                            if zip_name not in zip_file.namelist():
                                raise ValueError(
                                    f"Dataset file '{zip_name}' not found in the uploaded zip file."
                                )
                            if not zip_name.endswith(".zip"):
                                raise ValueError(
                                    f"Dataset file '{zip_name}' should be a zip file."
                                )

                            with zip_file.open(zip_name) as data_zip_file:
                                file_content = data_zip_file.read()
                            file_size_bytes = len(file_content)

                            data_file = InMemoryUploadedFile(
                                file=io.BytesIO(file_content),
                                field_name="data_file",
                                name=zip_name,
                                content_type="application/zip",
                                size=file_size_bytes,
                                charset=None,
                            )

                            return Data.objects.create(
                                name=zip_name,
                                created_by=request.user,
                                data_file=data_file,
                                type=data_type,
                            )

                        # scoring program must exist
                        if data_type == Data.SCORING_PROGRAM:
                            raise ValueError(f"{data_type} must have either a key or zip")
                        return None

                    datasets_and_programs = [
                        Data.INGESTION_PROGRAM,
                        Data.SCORING_PROGRAM,
                        Data.INPUT_DATA,
                        Data.REFERENCE_DATA,
                    ]
                    for dataset in datasets_and_programs:
                        task_kwargs[dataset] = create_or_get_data(
                            data_type=dataset, data_info=task_data.get(dataset)
                        )

                    task = Task.objects.create(**task_kwargs)
                    return Response(
                        {"message": f"Task '{task.name}' created successfully!"},
                        status=status.HTTP_201_CREATED,
                    )

        except zipfile.BadZipFile:
            return Response(
                {"error": "Uploaded file is not a valid zip file."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"An error occurred while creating the task.\n {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def check_delete_permissions(self, request, task):
        if request.user != task.created_by:
            return "Cannot delete a task that is not yours"
        if task.phases.exists():
            return "Cannot delete task: task is being used by a phase"
        return None