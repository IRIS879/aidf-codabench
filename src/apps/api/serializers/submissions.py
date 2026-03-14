import asyncio
from os.path import basename

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from api.mixins import DefaultUserCreateMixin
from api.serializers import leaderboards
from api.serializers.tasks import TaskSerializer
from api.serializers.submission_leaderboard import SubmissionScoreSerializer
from competitions.models import Submission, SubmissionDetails, CompetitionParticipant, Phase
from datasets.models import Data
from utils.data import make_url_sassy
from tasks.models import Task
from queues.models import Queue


def ensure_submission_leaderboard(submission):
    phase = getattr(submission, "phase", None)
    phase_leaderboard = getattr(phase, "leaderboard", None) if phase else None

    if phase_leaderboard and submission.leaderboard_id != phase_leaderboard.id:
        submission.leaderboard = phase_leaderboard
        submission.save(update_fields=["leaderboard"])


def extract_model_card_metadata(uploaded_file):
    """
    Extract model name from the visible PDF text.

    Expected format in the model card:
        Model name: <actual model name>

    Returns:
        (model_name, parsed_json)
    """
    if not uploaded_file:
        return None, None

    reader_cls = None

    try:
        from pypdf import PdfReader as reader_cls  # type: ignore
    except Exception:
        try:
            from PyPDF2 import PdfReader as reader_cls  # type: ignore
        except Exception:
            reader_cls = None

    if reader_cls is None:
        return None, None

    try:
        uploaded_file.seek(0)
        reader = reader_cls(uploaded_file)

        extracted_text = []
        for page in reader.pages[:2]:
            try:
                page_text = page.extract_text() or ""
                extracted_text.append(page_text)
            except Exception:
                continue

        full_text = "\n".join(extracted_text)

        import re

        model_name = None
        normalized_text = " ".join(full_text.split())

        match = re.search(
            r"model\s*name\s*:\s*(.+?)(?=\s+(task|output|overview|data|model|evaluation|interpretability|limitations|intended use|author)\s*:?\s|$)",
            normalized_text,
            flags=re.IGNORECASE,
        )

        if match:
            model_name = match.group(1).strip()

        parsed_json = {
            "extracted_text_preview": full_text[:2000],
            "model_name": model_name or "",
        }

        uploaded_file.seek(0)
        return model_name, parsed_json

    except Exception:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
        return None, None


class SubmissionSerializer(serializers.ModelSerializer):
    scores = SubmissionScoreSerializer(many=True)
    filename = serializers.SerializerMethodField(read_only=True)
    owner = serializers.CharField(source='owner.username')
    phase_name = serializers.CharField(source='phase.name')
    on_leaderboard = serializers.BooleanField(read_only=True)
    task = TaskSerializer()
    created_when = serializers.DateTimeField()
    auto_run = serializers.SerializerMethodField(read_only=True)
    can_make_submissions_public = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Submission
        fields = (
            'phase_name',
            'name',
            'filename',
            'description',
            'created_when',
            'is_public',
            'is_specific_task_re_run',
            'status',
            'status_details',
            'owner',
            'has_children',
            'parent',
            'children',
            'pk',
            'id',
            'phase',
            'scores',
            'fact_sheet_answers',
            'leaderboard',
            'on_leaderboard',
            'task',
            'auto_run',
            'can_make_submissions_public',
            'is_soft_deleted',
        )
        read_only_fields = (
            'pk',
            'phase',
            'scores',
            'is_specific_task_re_run',
            'leaderboard',
            'on_leaderboard',
        )

    def get_filename(self, instance):
        if instance.data and instance.data.data_file:
            return basename(instance.data.data_file.name)
        return "Deleted File"

    def get_auto_run(self, instance):
        return instance.phase.competition.auto_run_submissions

    def get_can_make_submissions_public(self, instance):
        return instance.phase.competition.can_participants_make_submissions_public


class SubmissionCreationSerializer(DefaultUserCreateMixin, serializers.ModelSerializer):
    """Used for creation and status updates."""
    data = serializers.SlugRelatedField(
        queryset=Data.objects.all(),
        required=False,
        allow_null=True,
        slug_field='key'
    )
    model_card_file = serializers.FileField(required=False, write_only=True)
    filename = serializers.SerializerMethodField(read_only=True)
    tasks = serializers.PrimaryKeyRelatedField(
        queryset=Task.objects.all(),
        required=False,
        write_only=True,
        many=True
    )
    phase = serializers.PrimaryKeyRelatedField(queryset=Phase.objects.all(), required=True)
    queue = serializers.PrimaryKeyRelatedField(queryset=Queue.objects.all(), required=False, allow_null=True)
    created_when = serializers.DateTimeField(format="%Y-%m-%d %H:%M", required=False)
    scores = SubmissionScoreSerializer(many=True, required=False)

    class Meta:
        model = Submission
        user_field = 'owner'
        fields = (
            'id',
            'data',
            'model_card_file',
            'phase',
            'status',
            'status_details',
            'filename',
            'description',
            'secret',
            'md5',
            'tasks',
            'fact_sheet_answers',
            'organization',
            'queue',
            'created_when',
            'scores',
        )
        extra_kwargs = {
            'secret': {"write_only": True},
            'description': {"read_only": True},
        }

    def get_filename(self, instance):
        if instance.data and instance.data.data_file:
            return basename(instance.data.data_file.name)
        return None

    def _validate_model_card_pdf(self, uploaded_file):
        if not uploaded_file:
            raise ValidationError("This competition requires a model card PDF.")

        filename = getattr(uploaded_file, "name", "") or ""
        if not filename.lower().endswith(".pdf"):
            raise ValidationError("Model card file must be a .pdf.")

        content_type = getattr(uploaded_file, "content_type", "") or ""
        if content_type and "pdf" not in content_type.lower():
            raise ValidationError("Uploaded model card must be a PDF.")

    def create(self, validated_data):
        tasks = validated_data.pop('tasks', None)
        model_card_file = validated_data.pop('model_card_file', None)

        sub = super().create(validated_data)

        uploaded_pdf = getattr(self, "_uploaded_model_card_file", None) or model_card_file
        if uploaded_pdf:
            sub.model_card_file.save(uploaded_pdf.name, uploaded_pdf, save=False)

            model_name, parsed_json = extract_model_card_metadata(uploaded_pdf)

            if parsed_json:
                sub.model_card_status = Submission.MODEL_CARD_PARSED
                sub.model_card_parsed_json = parsed_json
            else:
                sub.model_card_status = Submission.MODEL_CARD_UPLOADED
                sub.model_card_parsed_json = None

            sub.model_card_uploaded_at = timezone.now()

            if model_name:
                sub.name = model_name.strip()

            sub.save(update_fields=[
                "model_card_file",
                "model_card_status",
                "model_card_parsed_json",
                "model_card_uploaded_at",
                "name",
            ])

        if sub.phase.competition.auto_run_submissions:
            sub.start(tasks=tasks)

        return sub

    def validate(self, attrs):
        data = super().validate(attrs)

        if attrs.get('fact_sheet_answers'):
            fact_sheet_answers = data['fact_sheet_answers']
            fact_sheet = data['phase'].competition.fact_sheet

            if set(fact_sheet_answers.keys()) != set(fact_sheet.keys()):
                raise ValidationError("Fact Sheet keys do not match Answer keys")

            for key, value in fact_sheet_answers.items():
                if not fact_sheet[key] and not isinstance(value, str):
                    raise ValidationError(f'{value} should be string not {type(value)}')
                elif value not in fact_sheet[key]['selection'] and fact_sheet[key]['selection']:
                    raise ValidationError(f'{key}: {value} is not a valid selection from {fact_sheet[key]}')
                elif not value and fact_sheet[key]['is_required'] == 'true' and not isinstance(value, bool):
                    raise ValidationError(f'{fact_sheet[key]["title"]}({key}) requires an answer')

        if not self.instance:
            if not data.get("data"):
                raise ValidationError("This competition requires a submission zip (data).")

            uploaded_pdf = self.initial_data.get("model_card_file")
            self._validate_model_card_pdf(uploaded_pdf)
            self._uploaded_model_card_file = uploaded_pdf

        if attrs.get('tasks'):
            if not all(_ in attrs['phase'].tasks.all() for _ in attrs['tasks']):
                raise ValidationError("All tasks must be part of the current phase.")

        if not self.instance:
            is_in_competition = data["phase"].competition.participants.filter(
                user=self.context["request"].user,
                status=CompetitionParticipant.APPROVED
            ).exists()

            if not is_in_competition:
                raise PermissionDenied("You do not have access to this competition to make a submission")

        return data

    def update(self, submission, validated_data):
        if submission.secret != validated_data.get('secret'):
            raise PermissionDenied("Submission secret invalid")

        if "task" in validated_data:
            raise PermissionDenied("Task of a submission cannot be update")

        if "status" in validated_data:
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()

            loop.run_until_complete(channel_layer.group_send(
                f"submission_listening_{submission.owner.pk}",
                {
                    'type': 'submission.message',
                    'text': {
                        "kind": "status_update",
                        "status": validated_data["status"],
                    },
                    'submission_id': submission.id,
                }
            ))

        if (
            validated_data.get('status') == Submission.RUNNING
            and self.instance.parent is not None
            and self.instance.parent.status is not Submission.RUNNING
        ):
            self.instance.parent.status = Submission.RUNNING
            self.instance.parent.save(update_fields=["status"])

        if validated_data.get("status") == Submission.SCORING:
            from competitions.tasks import run_submission
            run_submission(submission.pk, tasks=[submission.task], is_scoring=True)

        elif validated_data.get("status") == Submission.FINISHED:
            cache.delete(f"submission-{submission.pk}-log")

            # Ensure finished submission is linked to its phase leaderboard
            ensure_submission_leaderboard(submission)

            # If this is a child submission, ensure the parent is linked too
            if submission.parent:
                ensure_submission_leaderboard(submission.parent)

        resp = super().update(submission, validated_data)

        # Re-assert after update in case save/update logic changed fields
        if validated_data.get("status") == Submission.FINISHED:
            resp.refresh_from_db()
            ensure_submission_leaderboard(resp)

            if resp.parent:
                resp.parent.refresh_from_db()
                ensure_submission_leaderboard(resp.parent)

        if submission.parent:
            submission.parent.check_child_submission_statuses()

        return resp


class SubmissionDetailSerializer(serializers.ModelSerializer):
    data_file = serializers.SerializerMethodField()

    class Meta:
        model = SubmissionDetails
        fields = (
            'name',
            'data_file',
        )

    def get_data_file(self, instance):
        return make_url_sassy(instance.data_file.name)


class SubmissionFilesSerializer(serializers.ModelSerializer):
    logs = serializers.SerializerMethodField()
    data_file = serializers.SerializerMethodField()
    prediction_result = serializers.SerializerMethodField()
    scoring_result = serializers.SerializerMethodField()
    detailed_result = serializers.SerializerMethodField()
    leaderboards = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = (
            'logs',
            'data_file',
            'prediction_result',
            'detailed_result',
            'scoring_result',
            'leaderboards',
            'fact_sheet_answers',
        )

    def get_logs(self, instance):
        if instance.phase.hide_output and not instance.phase.competition.user_has_admin_permission(self.context['request'].user):
            return []
        return SubmissionDetailSerializer(instance.details.all(), many=True).data

    def get_data_file(self, instance):
        return make_url_sassy(instance.data.data_file.name)

    def get_prediction_result(self, instance):
        if instance.prediction_result.name:
            if (
                (instance.phase.hide_output or instance.phase.hide_prediction_output)
                and not instance.phase.competition.user_has_admin_permission(self.context['request'].user)
            ):
                return None
            return make_url_sassy(instance.prediction_result.name)

    def get_detailed_result(self, instance):
        if instance.detailed_result.name:
            return make_url_sassy(instance.detailed_result.name)

    def get_scoring_result(self, instance):
        if instance.scoring_result.name:
            if (
                (instance.phase.hide_output or instance.phase.hide_score_output)
                and not instance.phase.competition.user_has_admin_permission(self.context['request'].user)
            ):
                return None
            return make_url_sassy(instance.scoring_result.name)

    def get_leaderboards(self, instance):
        if instance.phase.hide_output and not instance.phase.competition.user_has_admin_permission(self.context['request'].user):
            return None
        boards = list(set([
            score.column.leaderboard
            for score in instance.scores.all().select_related('column__leaderboard')
        ]))
        return [leaderboards.LeaderboardSerializer(lb).data for lb in boards]