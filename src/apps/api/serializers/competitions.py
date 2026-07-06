from drf_writable_nested import WritableNestedModelSerializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from api.fields import NamedBase64ImageField, StorageImageURLField
from api.mixins import DefaultUserCreateMixin
from api.serializers.datasets import DataDetailSerializer
from api.serializers.leaderboards import LeaderboardSerializer, ColumnSerializer
from api.serializers.profiles import CollaboratorSerializer
from api.serializers.submissions import SubmissionScoreSerializer
from api.serializers.tasks import PhaseTaskInstanceSerializer
from competitions.models import (
    Competition,
    Phase,
    Page,
    CompetitionCreationTaskStatus,
    CompetitionParticipant,
    CompetitionWhiteListEmail,
)
from forums.models import Forum
from leaderboards.models import Leaderboard
from profiles.models import User
from queues.models import Queue
from tasks.models import Task

from api.serializers.queues import QueueSerializer
from datetime import datetime
from django.utils.timezone import now


class PhaseSerializer(WritableNestedModelSerializer):
    tasks = serializers.SlugRelatedField(
        queryset=Task.objects.all(),
        required=True,
        allow_null=False,
        slug_field='key',
        many=True
    )
    status = serializers.SerializerMethodField()
    is_final_phase = serializers.SerializerMethodField()

    class Meta:
        model = Phase
        fields = (
            'id',
            'index',
            'start',
            'end',
            'name',
            'description',
            'status',
            'execution_time_limit',
            'tasks',
            'has_max_submissions',
            'max_submissions_per_day',
            'max_submissions_per_person',
            'auto_migrate_to_this_phase',
            'hide_output',
            'hide_prediction_output',
            'hide_score_output',
            'leaderboard',
            'public_data',
            'starting_kit',
            'is_final_phase',
        )

    def get_is_final_phase(self, obj):
        if len(obj.competition.phases.all()) > 1:
            return obj.is_final_phase
        elif len(obj.competition.phases.all()) == 1:
            obj.is_final_phase = True
            obj.save()
            return obj.is_final_phase

    def get_status(self, obj):
        now_dt = datetime.now().replace(tzinfo=None)
        start = obj.start.replace(tzinfo=None)
        end = obj.end.replace(tzinfo=None) if obj.end else obj.end

        phase_started = start <= now_dt
        phase_ended = False

        if phase_started:
            if end:
                phase_ended = end < now_dt
            else:
                phase_ended = False

        if phase_started and phase_ended:
            return Phase.PREVIOUS
        elif phase_started and (not phase_ended):
            return Phase.CURRENT
        else:
            return Phase.NEXT

    def validate_leaderboard(self, value):
        if not value:
            raise ValidationError("Phases require a leaderboard")
        return value


class PhaseDetailSerializer(serializers.ModelSerializer):
    tasks = PhaseTaskInstanceSerializer(source='task_instances', many=True)
    status = serializers.SerializerMethodField()
    public_data = DataDetailSerializer(read_only=True)
    starting_kit = DataDetailSerializer(read_only=True)
    used_submissions_per_day = serializers.SerializerMethodField()
    used_submissions_per_person = serializers.SerializerMethodField()

    class Meta:
        model = Phase
        fields = (
            'id',
            'index',
            'start',
            'end',
            'name',
            'description',
            'status',
            'execution_time_limit',
            'tasks',
            'has_max_submissions',
            'max_submissions_per_day',
            'max_submissions_per_person',
            'auto_migrate_to_this_phase',
            'hide_output',
            'hide_prediction_output',
            'hide_score_output',
            # no leaderboard
            'public_data',
            'starting_kit',
            'is_final_phase',
            'used_submissions_per_day',
            'used_submissions_per_person'
        )

    def get_status(self, obj):
        now_dt = datetime.now().replace(tzinfo=None)
        start = obj.start.replace(tzinfo=None)
        end = obj.end.replace(tzinfo=None) if obj.end else obj.end

        phase_started = start <= now_dt
        phase_ended = False

        if phase_started:
            if end:
                phase_ended = end < now_dt
            else:
                phase_ended = False

        if phase_started and phase_ended:
            return Phase.PREVIOUS
        elif phase_started and (not phase_ended):
            return Phase.CURRENT
        else:
            return Phase.NEXT

    def get_used_submissions_per_day(self, obj):
        if 'request' in self.context:
            user = self.context['request'].user
            if user.is_authenticated:
                qs = obj.submissions.filter(owner=user, parent__isnull=True).exclude(status='Failed')
                return qs.filter(created_when__date=now().date()).count()
        return 0

    def get_used_submissions_per_person(self, obj):
        if 'request' in self.context:
            user = self.context['request'].user
            if user.is_authenticated:
                qs = obj.submissions.filter(owner=user, parent__isnull=True).exclude(status='Failed')
                return qs.count()
        return 0


class PhaseUpdateSerializer(PhaseSerializer):
    tasks = PhaseTaskInstanceSerializer(source='task_instances', many=True)


class PageSerializer(WritableNestedModelSerializer):
    # *NOTE* The competition property has to be replicated at the end of the file
    # after the CompetitionSerializer class is declared
    # competition = CompetitionSerializer(many=True)

    class Meta:
        model = Page
        fields = (
            'id',
            'title',
            'content',
            'index',
        )


class CompetitionWhitelistSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompetitionWhiteListEmail
        fields = ['email']


class CompetitionSerializer(DefaultUserCreateMixin, WritableNestedModelSerializer):
    created_by = serializers.CharField(source='created_by.username', read_only=True)
    pages = PageSerializer(many=True)
    phases = PhaseSerializer(many=True)
    collaborators = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        many=True,
        required=False
    )
    queue = QueueSerializer(required=False, allow_null=True)

    # NOTE: allow_null True because some flows create first, upload later.
    logo = NamedBase64ImageField(required=False, allow_null=True)

    whitelist_emails = CompetitionWhitelistSerializer(many=True, required=False)

    class Meta:
        model = Competition
        user_field = 'created_by'
        fields = (
            'id',
            'title',
            'published',
            'secret_key',
            'created_by',
            'created_when',
            'logo',
            'docker_image',
            'pages',
            'phases',
            'collaborators',
            'description',
            'terms',
            'registration_auto_approve',
            'queue',
            'enable_detailed_results',
            'show_detailed_results_in_submission_panel',
            'show_detailed_results_in_leaderboard',
            'auto_run_submissions',
            'can_participants_make_submissions_public',
            'make_programs_available',
            'make_input_data_available',
            'docker_image',
            'allow_robot_submissions',
            'competition_type',
            'fact_sheet',
            'reward',
            'contact_email',
            'report',
            'whitelist_emails',
            'forum_enabled',
            'training_mode',
            'period_col',
            'rolling_start_period',
            'rolling_end_period',
            'rolling_window_size',
            'rolling_window_start_date',
            'rolling_window_end_date',
            'static_split_column',
            'static_split_value',
            'runtime_limit_seconds',
            'enable_model_card_submission',
            'model_card_is_public',
            'model_card_template_json',
            'leaderboard_use_model_name',
        )

    # ------------------------------------------------------------
    # FIX: Your frontend payload is missing root-level "title".
    # It DOES include leaderboards[0].title/key, so we backfill.
    # This prevents 400 "title required" and unblocks creation.
    # ------------------------------------------------------------
    def validate(self, attrs):
        if attrs.get('title'):
            return attrs

        initial = getattr(self, 'initial_data', {}) or {}

        # Some UIs may send details.title
        details = initial.get('details')
        if isinstance(details, dict):
            dt = details.get('title')
            if dt:
                attrs['title'] = dt
                return attrs

        # Your payload contains leaderboards[0].title/key
        lbs = initial.get('leaderboards')
        if isinstance(lbs, list) and len(lbs) > 0 and isinstance(lbs[0], dict):
            fallback = lbs[0].get('title') or lbs[0].get('key')
            if fallback:
                attrs['title'] = fallback
                return attrs

        attrs['title'] = 'Untitled Competition'
        return attrs

    def validate_phases(self, phases):
        if not phases or len(phases) <= 0:
            raise ValidationError("Competitions must have at least one phase")
        if len(phases) == 1 and phases[0].get('auto_migrate_to_this_phase'):
            raise ValidationError("You cannot auto migrate in a competition with one phase")
        if phases[0].get('auto_migrate_to_this_phase') is True:
            raise ValidationError("You cannot auto migrate to the first phase of a competition")
        return phases

    def validate_fact_sheet(self, fact_sheet):
        if not bool(fact_sheet):
            return None
        if not isinstance(fact_sheet, dict):
            raise ValidationError("Not valid JSON")

        expected_keys = {"key", "type", "title", "selection", "is_required", "is_on_leaderboard"}
        valid_question_types = {"checkbox", "text", "select"}
        for key, value in fact_sheet.items():
            missing_keys = expected_keys.symmetric_difference(set(value.keys()))
            if missing_keys:
                raise ValidationError(f'Missing {missing_keys} values for {key}')
            if key != value['key']:
                raise ValidationError(f"key:{value['key']}  does not match JSON key:{key}")
            if value['type'] not in valid_question_types:
                raise ValidationError(f"{value['type']} is not a valid question type")
        return fact_sheet

    def validate(self, attrs):
        attrs = super().validate(attrs)
        training_mode = attrs.get('training_mode')
        if training_mode is None and self.instance is not None:
            training_mode = self.instance.training_mode
        if training_mode is None:
            training_mode = Competition.TRAINING_MODE_STATIC

        runtime_limit_seconds = attrs.get('runtime_limit_seconds')
        if runtime_limit_seconds is None and self.instance is not None:
            runtime_limit_seconds = self.instance.runtime_limit_seconds
        if runtime_limit_seconds is not None and runtime_limit_seconds <= 0:
            raise ValidationError({"runtime_limit_seconds": "Runtime limit must be a positive integer."})

        rolling_window_size = attrs.get('rolling_window_size')
        period_col = attrs.get('period_col')
        rolling_start_period = attrs.get('rolling_start_period')
        rolling_end_period = attrs.get('rolling_end_period')
        rolling_window_start_date = attrs.get('rolling_window_start_date')
        rolling_window_end_date = attrs.get('rolling_window_end_date')
        static_split_column = attrs.get('static_split_column')
        static_split_value = attrs.get('static_split_value')
        if self.instance is not None:
            if period_col is None:
                period_col = self.instance.period_col
            if rolling_start_period is None:
                rolling_start_period = self.instance.rolling_start_period
            if rolling_end_period is None:
                rolling_end_period = self.instance.rolling_end_period
            if rolling_window_size is None:
                rolling_window_size = self.instance.rolling_window_size
            if rolling_window_start_date is None:
                rolling_window_start_date = self.instance.rolling_window_start_date
            if rolling_window_end_date is None:
                rolling_window_end_date = self.instance.rolling_window_end_date
            if static_split_column is None:
                static_split_column = self.instance.static_split_column
            if static_split_value is None:
                static_split_value = self.instance.static_split_value

        if training_mode == Competition.TRAINING_MODE_ROLLING:
            if not period_col:
                if self.instance is not None:
                    # Backward compatibility for existing rolling competitions.
                    attrs['period_col'] = 'yyyy'
                    period_col = 'yyyy'
                else:
                    raise ValidationError({"period_col": "This field is required for rolling window mode."})
            if not rolling_start_period and rolling_window_start_date:
                rolling_start_period = rolling_window_start_date.isoformat()
                attrs['rolling_start_period'] = rolling_start_period
            if not rolling_end_period and rolling_window_end_date:
                rolling_end_period = rolling_window_end_date.isoformat()
                attrs['rolling_end_period'] = rolling_end_period
            if not rolling_start_period:
                raise ValidationError({"rolling_start_period": "This field is required for rolling window mode."})
            if not rolling_end_period:
                raise ValidationError({"rolling_end_period": "This field is required for rolling window mode."})
            if rolling_window_size is None:
                raise ValidationError({"rolling_window_size": "This field is required for rolling window mode."})
            if rolling_window_size <= 0:
                raise ValidationError({"rolling_window_size": "Window size must be a positive integer."})
        else:
            attrs['period_col'] = None
            attrs['rolling_start_period'] = None
            attrs['rolling_end_period'] = None
            attrs['rolling_window_size'] = None
            attrs['rolling_window_start_date'] = None
            attrs['rolling_window_end_date'] = None
            has_static_col = bool((static_split_column or '').strip())
            has_static_val = bool((static_split_value or '').strip())
            if has_static_col ^ has_static_val:
                raise ValidationError(
                    {
                        "static_split_column": "Provide both static split column and split value, or leave both empty.",
                        "static_split_value": "Provide both static split column and split value, or leave both empty.",
                    }
                )
        if training_mode == Competition.TRAINING_MODE_ROLLING:
            attrs['static_split_column'] = None
            attrs['static_split_value'] = None
        return attrs

    def create(self, validated_data):
        instance = super().create(validated_data)
        Forum.objects.create(competition=instance)
        return instance

    def update(self, instance, validated_data):
        updated_whitelist_emails = validated_data.get('whitelist_emails', [])

        instance.whitelist_emails.all().delete()

        for whitelist_email in updated_whitelist_emails:
            CompetitionWhiteListEmail.objects.create(
                competition=instance,
                email=whitelist_email["email"]
            )

        validated_data.pop('whitelist_emails', None)

        collaborators = validated_data.get('collaborators', None)
        instance = super(CompetitionSerializer, self).update(instance, validated_data)

        if collaborators is not None:
            instance.collaborators.set(collaborators)
            for collaborator in collaborators:
                CompetitionParticipant.objects.get_or_create(
                    user=collaborator,
                    competition=instance,
                    defaults={'status': 'pending'}
                )

        return instance


class CompetitionUpdateSerializer(CompetitionSerializer):
    phases = PhaseUpdateSerializer(many=True)
    queue = serializers.PrimaryKeyRelatedField(queryset=Queue.objects.all(), required=False, allow_null=True)


class CompetitionCreateSerializer(CompetitionSerializer):
    queue = serializers.PrimaryKeyRelatedField(queryset=Queue.objects.all(), required=False, allow_null=True)


class CompetitionDetailSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source='created_by.username', read_only=True)
    owner_display_name = serializers.SerializerMethodField()
    logo = StorageImageURLField(read_only=True, allow_null=True)
    logo_icon = NamedBase64ImageField(allow_null=True)
    pages = PageSerializer(many=True)
    phases = PhaseDetailSerializer(many=True)
    leaderboards = serializers.SerializerMethodField()
    collaborators = CollaboratorSerializer(many=True)
    participant_status = serializers.CharField(read_only=True)
    participants_count = serializers.IntegerField(read_only=True)
    submissions_count = serializers.IntegerField(read_only=True)
    queue = QueueSerializer(read_only=True)
    whitelist_emails = serializers.SerializerMethodField()

    class Meta:
        model = Competition
        fields = (
            'id',
            'title',
            'published',
            'secret_key',
            'created_by',
            'owner_display_name',
            'created_when',
            'logo',
            'logo_icon',
            'terms',
            'pages',
            'phases',
            'leaderboards',
            'collaborators',
            'participant_status',
            'registration_auto_approve',
            'description',
            'participants_count',
            'submissions_count',
            'queue',
            'enable_detailed_results',
            'show_detailed_results_in_submission_panel',
            'show_detailed_results_in_leaderboard',
            'auto_run_submissions',
            'can_participants_make_submissions_public',
            'make_programs_available',
            'make_input_data_available',
            'docker_image',
            'allow_robot_submissions',
            'competition_type',
            'fact_sheet',
            'forum',
            'reward',
            'contact_email',
            'report',
            'whitelist_emails',
            'forum_enabled',
            'training_mode',
            'period_col',
            'rolling_start_period',
            'rolling_end_period',
            'rolling_window_size',
            'rolling_window_start_date',
            'rolling_window_end_date',
            'static_split_column',
            'static_split_value',
            'runtime_limit_seconds',
            'enable_model_card_submission',
            'model_card_is_public',
            'model_card_template_json',
            'leaderboard_use_model_name',
        )

    def get_leaderboards(self, instance):
        try:
            if instance.user_has_admin_permission(self.context['request'].user):
                qs = Leaderboard.objects.filter(phases__competition=instance).distinct('id')
            else:
                qs = Leaderboard.objects.filter(phases__competition=instance, hidden=False).distinct('id')
        except KeyError:
            raise Exception(f'KeyError on context. Context: {self.context}')
        return LeaderboardSerializer(qs, many=True).data

    def get_whitelist_emails(self, instance):
        whitelist_emails_query = instance.whitelist_emails.all()
        return [entry.email for entry in whitelist_emails_query]

    def get_owner_display_name(self, obj):
        return obj.created_by.display_name if obj.created_by.display_name else obj.created_by.username

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        user = self.context['request'].user

        if not instance.user_has_admin_permission(user):
            representation.pop('secret_key', None)
            representation.pop('whitelist_emails', None)

        return representation


class CompetitionSerializerSimple(serializers.ModelSerializer):
    created_by = serializers.CharField(source='created_by.username', read_only=True)
    owner_display_name = serializers.SerializerMethodField()
    participants_count = serializers.IntegerField(read_only=True)
    public_participants_count = serializers.SerializerMethodField()
    logo = StorageImageURLField(read_only=True, allow_null=True)
    logo_icon = StorageImageURLField(read_only=True, allow_null=True)

    class Meta:
        model = Competition
        fields = (
            'id',
            'title',
            'created_by',
            'owner_display_name',
            'created_when',
            'published',
            'participants_count',
            'public_participants_count',
            'logo',
            'logo_icon',
            'description',
            'competition_type',
            'reward',
            'contact_email',
            'report',
            'is_featured',
            'submissions_count',
            'participants_count'
        )

    def get_created_by(self, obj):
        return obj.created_by.display_name if obj.created_by.display_name else obj.created_by.username

    def get_owner_display_name(self, obj):
        return obj.created_by.display_name if obj.created_by.display_name else obj.created_by.username

    def get_public_participants_count(self, obj):
        collaborator_ids = obj.collaborators.values_list('id', flat=True)
        return obj.participants.filter(
            status=CompetitionParticipant.APPROVED
        ).exclude(
            user_id=obj.created_by_id
        ).exclude(
            user_id__in=collaborator_ids
        ).count()


PageSerializer.competition = CompetitionSerializer(many=True, source='competition')


class CompetitionCreationTaskStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompetitionCreationTaskStatus
        fields = (
            'status',
            'details',
            'resulting_competition',
            'created_by',
        )


class CompetitionParticipantSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username')
    is_bot = serializers.BooleanField(source='user.is_bot')
    email = serializers.CharField(source='user.email')
    is_deleted = serializers.BooleanField(source='user.is_deleted')

    class Meta:
        model = CompetitionParticipant
        fields = (
            'id',
            'username',
            'is_bot',
            'email',
            'status',
            'is_deleted',
        )


class FrontPageCompetitionsSerializer(serializers.Serializer):
    popular_comps = CompetitionSerializerSimple(many=True)
    recent_comps = CompetitionSerializerSimple(many=True)


class PhaseResultsSubmissionSerializer(serializers.Serializer):
    owner = serializers.CharField()
    scores = SubmissionScoreSerializer(many=True)


class PhaseResultsTaskSerializer(serializers.Serializer):
    colWidth = serializers.IntegerField()
    id = serializers.IntegerField()
    columns = ColumnSerializer(many=True)
    name = serializers.CharField()


class PhaseResultsSerializer(serializers.Serializer):
    title = serializers.CharField()
    id = serializers.IntegerField()
    tasks = PhaseResultsTaskSerializer(many=True, read_only=True)
    submissions = PhaseResultsSubmissionSerializer(many=True)
