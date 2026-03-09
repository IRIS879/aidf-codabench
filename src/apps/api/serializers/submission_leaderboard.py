from rest_framework import serializers

from api.serializers.profiles import SimpleOrganizationSerializer
from competitions.models import Submission
from leaderboards.models import SubmissionScore


class SubmissionScoreSerializer(serializers.ModelSerializer):
    index = serializers.IntegerField(source='column.index', read_only=True)
    column_key = serializers.CharField(source='column.key', read_only=True)

    class Meta:
        model = SubmissionScore
        fields = ('id', 'index', 'score', 'column_key')


class SubmissionLeaderBoardSerializer(serializers.ModelSerializer):
    scores = SubmissionScoreSerializer(many=True)
    owner = serializers.CharField(source='owner.username')
    display_name = serializers.SerializerMethodField()
    slug_url = serializers.CharField(source='owner.slug_url')
    organization = SimpleOrganizationSerializer(allow_null=True)
    created_when = serializers.DateTimeField()
    model_name = serializers.SerializerMethodField()
    model_card_url = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = (
            'id',
            'parent',
            'owner',
            'leaderboard_id',
            'fact_sheet_answers',
            'task',
            'scores',
            'display_name',
            'slug_url',
            'organization',
            'detailed_result',
            'created_when',
            'model_name',
            'model_card_url',
        )

    def get_display_name(self, obj):
        comp = getattr(getattr(obj, 'phase', None), 'competition', None)
        if comp and getattr(comp, 'leaderboard_use_model_name', False):
            return (obj.name or '').strip() or obj.owner.display_name
        return obj.owner.display_name

    def get_model_name(self, obj):
        if obj.name and obj.name.strip():
            return obj.name.strip()

        if obj.data and obj.data.data_file:
            filename = obj.data.data_file.name.split('/')[-1]
            if filename.lower().endswith('.zip'):
                filename = filename[:-4]
            return filename

        return 'Model'

    def get_model_card_url(self, obj):
        if obj.model_card_file and obj.model_card_file.name:
            try:
                return obj.model_card_file.url
            except Exception:
                return None
        return None