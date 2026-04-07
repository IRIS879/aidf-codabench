import asyncio
import logging
import re
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

logger = logging.getLogger(__name__)


def ensure_submission_leaderboard(submission):
    phase = getattr(submission, "phase", None)
    phase_leaderboard = getattr(phase, "leaderboard", None) if phase else None

    if phase_leaderboard and submission.leaderboard_id != phase_leaderboard.id:
        submission.leaderboard = phase_leaderboard
        submission.save(update_fields=["leaderboard"])


def _has_meaningful_model_card_value(value):
    if not value:
        return False

    normalized = " ".join(str(value).split()).strip().lower().rstrip(".")
    placeholder_values = {
        "",
        "n/a",
        "na",
        "none",
        "null",
        "tbd",
        "todo",
        "unknown",
    }

    if normalized in placeholder_values:
        return False

    if normalized.startswith("briefly describe the purpose of the model"):
        return False

    return True


MODEL_CARD_OVERVIEW_PROMPT = (
    "Briefly describe the purpose of the model and the problem it is designed to solve."
)


def _extract_model_card_section(text, heading, next_headings):
    heading_pattern = re.escape(heading)
    next_heading_pattern = "|".join(re.escape(item) for item in next_headings)
    match = re.search(
        rf"{heading_pattern}\s*(?P<section>.*?)(?=^\s*(?:{next_heading_pattern})\s*$|\Z)",
        text,
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    if not match:
        return ""
    return match.group("section").strip()


def _extract_model_card_section_fallback(text, heading, next_headings):
    normalized_text = " ".join(text.split())
    heading_pattern = re.escape(heading)
    next_heading_pattern = "|".join(re.escape(item) for item in next_headings)
    match = re.search(
        rf"{heading_pattern}\s*(?P<section>.*?)(?=\s+(?:{next_heading_pattern})\b|$)",
        normalized_text,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    return match.group("section").strip()


def _section_needs_fallback(section_text, next_headings):
    if not section_text:
        return True

    for heading in next_headings:
        if re.search(rf"\b{re.escape(heading)}\b", section_text, flags=re.IGNORECASE):
            return True

    return False


def _trim_field_value(candidate, stop_labels):
    trimmed_candidate = candidate.strip()
    if not trimmed_candidate:
        return ""

    stop_pattern = "|".join(rf"{label}\s*:" for label in stop_labels)
    match = re.search(rf"^(?P<value>.*?)(?=\s+(?:{stop_pattern})|$)", trimmed_candidate, flags=re.IGNORECASE)
    if not match:
        return trimmed_candidate
    return match.group("value").strip()


def _extract_model_information_fields(model_information):
    extracted_fields = {
        "model_name": "",
        "task": "",
        "output": "",
    }

    for raw_line in model_information.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = re.match(r"(model\s*name|task|output)\s*:\s*(.*)$", line, flags=re.IGNORECASE)
        if not match:
            continue

        label = re.sub(r"\s+", "_", match.group(1).strip().lower())
        stop_labels = ["model name", "task", "output"]
        stop_labels = [item for item in stop_labels if item.replace(" ", "_") != label]
        candidate = _trim_field_value(match.group(2), stop_labels)
        if not candidate:
            extracted_fields[label] = ""
            continue

        if re.match(r"^(model\s*name|task|output)\s*:", candidate, flags=re.IGNORECASE):
            extracted_fields[label] = ""
            continue

        extracted_fields[label] = candidate

    if all(extracted_fields.values()):
        return extracted_fields

    normalized_information = " ".join(model_information.split())
    field_patterns = {
        "model_name": r"model\s*name\s*:\s*(?P<value>.*?)(?=\s+task\s*:|\s+output\s*:|\s+overview\b|$)",
        "task": r"task\s*:\s*(?P<value>.*?)(?=\s+output\s*:|\s+overview\b|$)",
        "output": r"output\s*:\s*(?P<value>.*?)(?=\s+overview\b|$)",
    }

    for field_name, pattern in field_patterns.items():
        if extracted_fields[field_name]:
            continue

        match = re.search(pattern, normalized_information, flags=re.IGNORECASE)
        if not match:
            continue

        candidate = match.group("value").strip()
        if not candidate:
            continue

        if re.match(r"^(model\s*name|task|output)\s*:", candidate, flags=re.IGNORECASE):
            continue

        extracted_fields[field_name] = candidate

    return extracted_fields


def _extract_meaningful_overview(overview):
    cleaned_overview = overview.strip()
    if not cleaned_overview:
        return ""

    prompt_pattern = re.escape(MODEL_CARD_OVERVIEW_PROMPT)
    cleaned_overview = re.sub(prompt_pattern, "", cleaned_overview, flags=re.IGNORECASE).strip()
    return cleaned_overview


def extract_model_card_metadata_debug(uploaded_file):
    if not uploaded_file:
        return {
            "model_name": None,
            "parsed_json": None,
            "failure_reasons": ["missing file"],
            "extracted_text_preview": "",
        }

    reader_cls = None

    try:
        from pypdf import PdfReader as reader_cls  # type: ignore
    except Exception:
        try:
            from PyPDF2 import PdfReader as reader_cls  # type: ignore
        except Exception:
            reader_cls = None

    if reader_cls is None:
        return {
            "model_name": None,
            "parsed_json": None,
            "failure_reasons": ["pdf reader unavailable"],
            "extracted_text_preview": "",
        }

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
        extracted_text_preview = full_text[:2000]

        model_information = _extract_model_card_section(
            full_text,
            "Model Information",
            ["Overview"],
        )
        if _section_needs_fallback(model_information, ["Overview"]):
            model_information = _extract_model_card_section_fallback(
                full_text,
                "Model Information",
                ["Overview"],
            )

        overview = _extract_model_card_section(
            full_text,
            "Overview",
            ["Data", "Model", "Evaluation", "Interpretability", "Limitations", "Intended Use", "Author"],
        )
        if _section_needs_fallback(
            overview,
            ["Data", "Model", "Evaluation", "Interpretability", "Limitations", "Intended Use", "Author"],
        ):
            overview = _extract_model_card_section_fallback(
                full_text,
                "Overview",
                ["Data", "Model", "Evaluation", "Interpretability", "Limitations", "Intended Use", "Author"],
            )
        model_information_fields = _extract_model_information_fields(model_information)
        overview_content = _extract_meaningful_overview(overview)

        failure_reasons = []
        if not _has_meaningful_model_card_value(model_information):
            failure_reasons.append('missing "Model Information" section')
        if not _has_meaningful_model_card_value(model_information_fields["model_name"]):
            failure_reasons.append('missing "Model Name" value')
        if not _has_meaningful_model_card_value(model_information_fields["task"]):
            failure_reasons.append('missing "Task" value')
        if not _has_meaningful_model_card_value(model_information_fields["output"]):
            failure_reasons.append('missing "Output" value')
        if not _has_meaningful_model_card_value(overview_content):
            failure_reasons.append('missing meaningful "Overview" content')

        if failure_reasons:
            uploaded_file.seek(0)
            return {
                "model_name": None,
                "parsed_json": None,
                "failure_reasons": failure_reasons,
                "extracted_text_preview": extracted_text_preview,
            }

        parsed_json = {
            "extracted_text_preview": extracted_text_preview,
            "model_information": model_information,
            "model_name": model_information_fields["model_name"],
            "task": model_information_fields["task"],
            "output": model_information_fields["output"],
            "overview": overview_content,
        }

        uploaded_file.seek(0)
        return {
            "model_name": model_information_fields["model_name"],
            "parsed_json": parsed_json,
            "failure_reasons": [],
            "extracted_text_preview": extracted_text_preview,
        }

    except Exception:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
        return {
            "model_name": None,
            "parsed_json": None,
            "failure_reasons": ["pdf text extraction failed"],
            "extracted_text_preview": "",
        }


def extract_model_card_metadata(uploaded_file):
    """
    Extract structured metadata from the visible PDF text.

    Successful parsing requires:
        - a Model Information section
        - non-empty Model Name, Task, and Output values
        - a non-empty Overview section with real content

    Returns:
        (model_name, parsed_json)
    """
    debug_result = extract_model_card_metadata_debug(uploaded_file)
    return debug_result["model_name"], debug_result["parsed_json"]


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
            raise serializers.ValidationError({
                "model_card_file": "This competition requires a model card PDF."
            })

        filename = getattr(uploaded_file, "name", "") or ""
        if not filename.lower().endswith(".pdf"):
            raise serializers.ValidationError({
                "model_card_file": "Model card file must be a .pdf."
            })

        content_type = getattr(uploaded_file, "content_type", "") or ""
        if content_type and "pdf" not in content_type.lower():
            raise serializers.ValidationError({
                "model_card_file": "Uploaded model card must be a PDF."
            })

        debug_result = extract_model_card_metadata_debug(uploaded_file)
        model_name = debug_result["model_name"]
        parsed_json = debug_result["parsed_json"]
        if not parsed_json:
            logger.warning(
                "Model card parsing failed for %s. Reasons=%s Preview=%r",
                filename,
                debug_result["failure_reasons"],
                debug_result["extracted_text_preview"],
            )
            raise serializers.ValidationError({
                "model_card_file": (
                    "Model card parsing failed: "
                    + "; ".join(debug_result["failure_reasons"])
                )
            })

        self._parsed_model_card_name = model_name
        self._parsed_model_card_json = parsed_json

    def create(self, validated_data):
        tasks = validated_data.pop('tasks', None)
        model_card_file = validated_data.pop('model_card_file', None)

        sub = super().create(validated_data)

        uploaded_pdf = getattr(self, "_uploaded_model_card_file", None) or model_card_file
        if uploaded_pdf:
            sub.model_card_file.save(uploaded_pdf.name, uploaded_pdf, save=False)
            model_name = getattr(self, "_parsed_model_card_name", None)
            parsed_json = getattr(self, "_parsed_model_card_json", None)

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
