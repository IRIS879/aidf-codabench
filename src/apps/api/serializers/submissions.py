import asyncio
import json
import logging
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
from utils.model_card_parser import (
    parse_model_card,
    parse_model_card_form_data,
    # backward-compat re-exports so existing tests keep working
    extract_model_card_metadata_debug,
    extract_model_card_metadata,
    ACCEPTED_EXTENSIONS as MODEL_CARD_ACCEPTED_EXTENSIONS,
)
from tasks.models import Task
from queues.models import Queue

logger = logging.getLogger(__name__)


def ensure_submission_leaderboard(submission):
    phase = getattr(submission, "phase", None)
    phase_leaderboard = getattr(phase, "leaderboard", None) if phase else None

    if phase_leaderboard and submission.leaderboard_id != phase_leaderboard.id:
        submission.leaderboard = phase_leaderboard
        submission.save(update_fields=["leaderboard"])


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
    # JSON-encoded dict from the in-page form fill mode
    model_card_form_data = serializers.CharField(required=False, write_only=True, allow_blank=True)
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
            'model_card_form_data',
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

    def _validate_model_card_file(self, uploaded_file):
        """Validate an uploaded model card file (PDF / JSON / Markdown)."""
        if not uploaded_file:
            raise serializers.ValidationError({
                "model_card_file": (
                    "This competition requires a model card. "
                    "Upload a .pdf, .json, or .md file, or fill in the form."
                )
            })

        filename = getattr(uploaded_file, "name", "") or ""
        ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
        if ext not in MODEL_CARD_ACCEPTED_EXTENSIONS:
            raise serializers.ValidationError({
                "model_card_file": (
                    f"Unsupported model card format '{ext}'. "
                    "Accepted: .pdf, .json, .md, .markdown"
                )
            })

        result = parse_model_card(uploaded_file, filename)
        if not result["parsed_json"]:
            logger.warning(
                "Model card parsing failed for %s. Reasons=%s Preview=%r",
                filename,
                result["failure_reasons"],
                result.get("extracted_text_preview", ""),
            )
            raise serializers.ValidationError({
                "model_card_file": (
                    "Model card parsing failed: "
                    + "; ".join(result["failure_reasons"])
                )
            })

        self._parsed_model_card_name = result["model_name"]
        self._parsed_model_card_json = result["parsed_json"]

    # Backward-compat alias — existing tests call this name directly.
    _validate_model_card_pdf = _validate_model_card_file

    def create(self, validated_data):
        tasks = validated_data.pop('tasks', None)
        model_card_file = validated_data.pop('model_card_file', None)
        validated_data.pop('model_card_form_data', None)  # consumed during validate()

        sub = super().create(validated_data)

        # Determine source: uploaded file wins over form data
        uploaded_file = getattr(self, "_uploaded_model_card_file", None) or model_card_file
        parsed_json = getattr(self, "_parsed_model_card_json", None)
        model_name = getattr(self, "_parsed_model_card_name", None)

        if uploaded_file:
            # Save the physical file and its parsed metadata
            sub.model_card_file.save(uploaded_file.name, uploaded_file, save=False)
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

        elif parsed_json:
            # Form-fill mode: no physical file, only the parsed dict
            sub.model_card_status = Submission.MODEL_CARD_PARSED
            sub.model_card_parsed_json = parsed_json
            sub.model_card_uploaded_at = timezone.now()
            if model_name:
                sub.name = model_name.strip()
            sub.save(update_fields=[
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

            competition = data["phase"].competition
            if getattr(competition, "enable_model_card_submission", False):
                # Model card is required — accept either an uploaded file or form data.
                uploaded_file = self.initial_data.get("model_card_file")
                form_data_raw = self.initial_data.get("model_card_form_data", "")

                if form_data_raw:
                    # Form-fill path: parse the JSON payload sent by the browser.
                    try:
                        form_dict = json.loads(form_data_raw)
                    except Exception:
                        raise serializers.ValidationError(
                            {"model_card_form_data": "Invalid JSON in model card form data."}
                        )
                    result = parse_model_card_form_data(form_dict)
                    if not result["parsed_json"]:
                        raise serializers.ValidationError({
                            "model_card_form_data": (
                                "Model card form data invalid: "
                                + "; ".join(result["failure_reasons"])
                            )
                        })
                    self._parsed_model_card_name = result["model_name"]
                    self._parsed_model_card_json = result["parsed_json"]
                    self._uploaded_model_card_file = None

                elif uploaded_file:
                    # File-upload path: validate and parse the uploaded file.
                    self._validate_model_card_file(uploaded_file)
                    self._uploaded_model_card_file = uploaded_file

                else:
                    raise serializers.ValidationError({
                        "model_card_file": (
                            "This competition requires a model card. "
                            "Upload a .pdf, .json, or .md file, or fill in the form."
                        )
                    })
            else:
                # Model card not required — accept an optional file silently.
                uploaded_file = self.initial_data.get("model_card_file")
                if uploaded_file:
                    self._validate_model_card_file(uploaded_file)
                    self._uploaded_model_card_file = uploaded_file
                else:
                    self._uploaded_model_card_file = None

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
