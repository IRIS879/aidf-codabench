# api/serializers/submission_leaderboard.py
from rest_framework import serializers
from competitions.models import Submission
from leaderboards.models import SubmissionScore
from api.serializers.profiles import SimpleOrganizationSerializer


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

    def get_display_name(self, obj):
        # If enabled, show Model Name (stored in Submission.name) instead of user display name
        comp = getattr(getattr(obj, "phase", None), "competition", None)
        if comp and getattr(comp, "leaderboard_use_model_name", False):
            return (obj.name or "").strip() or obj.owner.display_name
        return obj.owner.display_name

    class Meta:
        model = Submission
        fields = (
            'id', 'parent', 'owner', 'leaderboard_id', 'fact_sheet_answers',
            'task', 'scores', 'display_name', 'slug_url', 'organization',
            'detailed_result', 'created_when'
        )
